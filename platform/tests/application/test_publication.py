"""Publication invariants use application services without an execution host."""

import pytest
from support.scenarios import publish

from flareward.programs.authoring import CanvasPosition, ProgramConflict, ProgramPresentation
from flareward.programs.domain.models import ApplicationDefinition, ProgramDefinition
from flareward.programs.service import ProgramContractError
from flareward.services.identity.domain import Identity


async def test_published_configuration_remains_detached_from_drafts_and_readers(application):
    original = await publish(
        application,
        "revision",
        ApplicationDefinition(implementation="greeting", version="1"),
    )
    replacement = await publish(
        application,
        "revision",
        ApplicationDefinition(
            implementation="greeting",
            version="1",
            config={"prefix": "new "},
        ),
    )
    assert (original.revision, replacement.revision) == (1, 2)
    original_config = original.definition.implementation.config.copy()
    original.definition.implementation.config["prefix"] = "reader mutation"
    reread = await application.programs.revision(original.reference, application.owner)
    assert reread.definition.implementation.config == original_config
    assert reread.content_digest != replacement.content_digest


async def test_invalid_schema_is_an_application_contract_error(application):
    definition = ProgramDefinition(
        program_id="bad-schema",
        name="Invalid",
        owner=application.owner,
        implementation=ApplicationDefinition(implementation="greeting", version="1"),
        input_schema={"type": "unknown-json-type"},
    )
    with pytest.raises(ProgramContractError, match="Invalid program input schema"):
        await application.programs.save(definition, application.owner)
    with pytest.raises(KeyError):
        await application.programs.publish(
            definition.program_id,
            application.owner,
            expected_version=(
                await application.programs.draft(definition.program_id, application.owner)
            ).version,
        )


async def test_program_revision_is_not_visible_to_another_owner(application):
    revision = await publish(
        application,
        "private",
        ApplicationDefinition(implementation="greeting", version="1"),
    )
    with pytest.raises(PermissionError):
        await application.programs.revision(revision.reference, Identity.user("another-owner"))


async def test_edit_publish_and_retry_preserve_observed_source_and_presentation(application):
    definition = ProgramDefinition(
        program_id="versioned",
        name="First name",
        owner=application.owner,
        implementation=ApplicationDefinition(implementation="greeting", version="1"),
    )
    presentation = ProgramPresentation(positions={"call": CanvasPosition(x=12, y=34)})
    first = await application.programs.save(
        definition, application.owner, presentation=presentation
    )
    published = await application.programs.publish(
        "versioned", application.owner, expected_version=first.version
    )
    edited = await application.programs.save(
        first.definition.model_copy(update={"name": "Edited name"}),
        application.owner,
        expected_version=first.version,
    )
    assert edited.presentation == presentation
    # An uncertain publication acknowledgment can be retried after a later edit.
    assert (
        await application.programs.publish(
            "versioned", application.owner, expected_version=first.version
        )
        == published
    )
    newest = await application.programs.publish(
        "versioned", application.owner, expected_version=edited.version
    )
    assert newest.definition.name == "Edited name" and published.definition.name == "First name"
    assert "presentation" not in newest.model_dump()
    with pytest.raises(ProgramConflict):
        await application.programs.save(
            definition, application.owner, expected_version=first.version
        )
    with pytest.raises(ProgramConflict):
        await application.programs.publish("versioned", application.owner, expected_version=99)
    page = await application.programs.list(application.owner, limit=1)
    assert page.programs[0].draft_version == edited.version
    assert not (await application.programs.list(Identity.user("foreign"))).programs
    revisions = await application.programs.revisions("versioned", application.owner, limit=1)
    assert revisions.revisions[0].program == newest.reference
    older = await application.programs.revisions(
        "versioned", application.owner, before=revisions.next_cursor
    )
    assert [value.program for value in older.revisions] == [published.reference]
