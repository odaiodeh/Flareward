"""Owned bodies use the enclosing Program's protection and publication lifecycle."""

import pytest
from support.application import make_application
from support.resource_snapshots import MemoryResourceSources, saved_resource_graph
from support.scenarios import publish
from support.secrets import MemorySecretStore, secret_definition

from flareward.elements.construction.secrets import ConfigurationSecrets
from flareward.elements.construction.snapshots import SavedResourceResolver
from flareward.programs.adapters.memory.program_repository import MemoryProgramRepository
from flareward.programs.authoring import ProgramIssueCode, ProgramResourceSelection
from flareward.programs.domain.models import ApplicationDefinition, GraphDefinition, ProgramBody
from flareward.programs.service import ProgramContractError, ProgramService
from flareward.resources.domain.bundles import ResourceKey
from flareward.resources.secrets import is_secret_reference
from flareward.services.identity.domain import Identity


async def test_owned_secrets_are_protected_before_save_and_remain_frozen():
    store = MemorySecretStore()
    application = make_application(store)
    definition = secret_definition("thread", "owned-private-value").model_copy(
        update={"owner": application.owner}
    )
    body = ProgramBody(implementation=definition.implementation)
    root = definition.model_copy(
        update={
            "implementation": ApplicationDefinition(
                implementation="composed", version="1", children={"greet": body}
            )
        }
    )
    draft = await application.programs.save(root, application.owner)
    assert "owned-private-value" not in draft.model_dump_json()
    protected = draft.definition.body_at(("greet",)).implementation.resources[1].config["api_key"]
    assert is_secret_reference(protected)
    revision = await application.programs.publish(
        root.program_id, application.owner, expected_version=draft.version
    )
    changed = root.model_copy(
        update={
            "implementation": ApplicationDefinition(
                implementation="composed",
                version="1",
                children={
                    "greet": ProgramBody(
                        implementation=ApplicationDefinition(implementation="greeting", version="1")
                    )
                },
            )
        }
    )
    await application.programs.save(changed, application.owner, expected_version=draft.version)
    assert await application.programs.revision(revision.reference, application.owner) == revision
    assert (
        revision.definition.body_at(("greet",)).implementation
        == draft.definition.body_at(("greet",)).implementation
    )
    assert len((await application.programs.list(application.owner)).programs) == 1
    with pytest.raises(PermissionError):
        await store.get(Identity.user("other"), protected)


async def test_incomplete_owned_graph_reports_its_source_and_cannot_publish(application):
    revision = await publish(
        application, "base", ApplicationDefinition(implementation="greeting", version="1")
    )
    root = revision.definition.model_copy(
        update={
            "program_id": "unfinished-owned",
            "implementation": ApplicationDefinition(
                implementation="composed",
                version="1",
                children={"greet": ProgramBody(implementation=GraphDefinition(steps=()))},
            ),
        }
    )
    draft = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        root.program_id, application.owner, expected_version=draft.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.TOPOLOGY
    assert report.issues[0].path == ("implementation", "children", "greet", "implementation")
    with pytest.raises(ProgramContractError):
        await application.programs.publish(
            root.program_id, application.owner, expected_version=draft.version
        )
    assert not (await application.programs.revisions(root.program_id, application.owner)).revisions


async def test_owned_body_cannot_hide_an_unauthorized_published_dependency(application):
    private = await publish(
        application, "private", ApplicationDefinition(implementation="greeting", version="1")
    )
    caller = Identity.user("other")
    root = private.definition.model_copy(
        update={
            "program_id": "unauthorized-owned",
            "owner": caller,
            "implementation": ApplicationDefinition(
                implementation="composed",
                version="1",
                children={
                    "greet": ProgramBody(
                        implementation=ApplicationDefinition(
                            implementation="composed",
                            version="1",
                            children={"greet": private.reference},
                        )
                    )
                },
            ),
        }
    )
    draft = await application.programs.save(root, caller)
    report = await application.programs.validate(
        root.program_id, caller, expected_version=draft.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.REFERENCE
    assert report.issues[0].path == (
        "implementation",
        "children",
        "greet",
        "implementation",
        "children",
        "greet",
    )
    with pytest.raises(ProgramContractError):
        await application.programs.publish(root.program_id, caller, expected_version=draft.version)


async def test_new_revision_can_call_a_finite_prior_revision_of_same_program(application):
    original = await publish(
        application, "versioned", ApplicationDefinition(implementation="greeting", version="1")
    )
    changed = await publish(
        application,
        "versioned",
        ApplicationDefinition(
            implementation="composed", version="1", children={"greet": original.reference}
        ),
    )
    assert changed.revision == 2
    assert changed.definition.implementation.children["greet"] == original.reference


async def test_saved_resource_selection_is_scoped_to_owned_graph(application):
    source = MemoryResourceSources(application.owner)
    configuration = ConfigurationSecrets(application.elements, None)
    programs = ProgramService(
        MemoryProgramRepository(),
        application.applications,
        application.elements,
        configuration,
        SavedResourceResolver(source, application.elements, configuration),
    )
    root = secret_definition("thread", "unused").model_copy(
        update={
            "owner": application.owner,
            "implementation": ApplicationDefinition(
                implementation="composed",
                version="1",
                children={"greet": ProgramBody(implementation=saved_resource_graph())},
            ),
        }
    )
    selection = ProgramResourceSelection(
        body_path=("greet",),
        source=source.reference(ResourceKey(category="operations", rid="work")),
    )
    draft = await programs.save(root, application.owner, resource_selections=(selection,))
    body = draft.definition.body_at(("greet",))
    assert len(body.implementation.resources) == 3
    revision = await programs.publish(
        root.program_id, application.owner, expected_version=draft.version
    )
    source.resources.clear()
    assert await programs.revision(revision.reference, application.owner) == revision
    for invalid_path in ((), ("missing",), ("greet", "missing")):
        with pytest.raises(ProgramContractError):
            await programs.save(
                root,
                application.owner,
                expected_version=draft.version,
                resource_selections=(selection.model_copy(update={"body_path": invalid_path}),),
            )
    assert (await programs.draft(root.program_id, application.owner)).version == draft.version
