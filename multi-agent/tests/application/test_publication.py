"""Publication invariants use application services without an execution host."""

import pytest
from mas.core.identity import Identity
from mas.programs.models import ApplicationDefinition, ProgramDefinition
from mas.programs.service import ProgramContractError
from support.scenarios import publish


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
        await application.programs.publish(definition.program_id, application.owner)


async def test_program_revision_is_not_visible_to_another_owner(application):
    revision = await publish(
        application,
        "private",
        ApplicationDefinition(implementation="greeting", version="1"),
    )
    with pytest.raises(PermissionError):
        await application.programs.revision(revision.reference, Identity.user("another-owner"))
