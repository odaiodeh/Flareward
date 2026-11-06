"""Unfinished authoring is durable; only validated revisions become executable."""

import pytest
from mas.application.programs.authoring import ProgramConflict, ProgramIssueCode
from mas.application.programs.composition.programs import APPLICATION_PROGRAMS
from mas.application.programs.service import ProgramContractError
from mas.core.identity import Identity
from mas.core.secrets import is_secret_reference
from mas.domain.programs.models import (
    ApplicationDefinition,
    GraphDefinition,
    ProgramCallStep,
    ProgramDefinition,
    ProgramRevision,
)
from pydantic import ValidationError
from support.application import make_application
from support.operations import operation_graph
from support.scenarios import publish
from support.secrets import MemorySecretStore, secret_definition


@pytest.fixture(autouse=True)
def installed_controls(application):
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)


async def test_empty_graph_can_be_saved_reopened_and_completed_before_publication(application):
    definition = ProgramDefinition(
        program_id="unfinished",
        name="Work in progress",
        owner=application.owner,
        implementation=GraphDefinition(steps=(), entry="", exit=""),
    )
    draft = await application.programs.save(definition, application.owner)
    assert await application.programs.draft("unfinished", application.owner) == draft
    report = await application.programs.validate(
        "unfinished", application.owner, expected_version=draft.version
    )
    assert not report.valid and report.version == draft.version
    assert "entry and exit" in report.issues[0].message
    assert report.issues[0].code == ProgramIssueCode.TOPOLOGY
    assert report.issues[0].path == ("implementation",)
    with pytest.raises(ProgramContractError):
        await application.programs.publish(
            "unfinished", application.owner, expected_version=draft.version
        )
    assert not (await application.programs.revisions("unfinished", application.owner)).revisions
    with pytest.raises(ValidationError):
        ProgramRevision(definition=draft.definition, revision=1)

    child = await publish(
        application, "child", ApplicationDefinition(implementation="greeting", version="1")
    )
    completed = definition.model_copy(
        update={
            "implementation": GraphDefinition(
                steps=(ProgramCallStep(uid="work", program=child.reference),),
                entry="work",
                exit="work",
            )
        }
    )
    saved = await application.programs.save(
        completed, application.owner, expected_version=draft.version
    )
    assert (
        await application.programs.validate(
            "unfinished", application.owner, expected_version=saved.version
        )
    ).valid
    revision = await application.programs.publish(
        "unfinished", application.owner, expected_version=saved.version
    )
    assert revision.definition == saved.definition
    with pytest.raises(ProgramConflict):
        await application.programs.validate(
            "unfinished", application.owner, expected_version=draft.version
        )
    with pytest.raises(PermissionError):
        await application.programs.validate(
            "unfinished", Identity.user("other"), expected_version=saved.version
        )


async def test_registered_program_can_save_before_required_child_binding(application):
    definition = ProgramDefinition(
        program_id="incomplete-map",
        name="Map in progress",
        owner=application.owner,
        implementation=ApplicationDefinition(implementation="map", version="1"),
    )
    draft = await application.programs.save(definition, application.owner)
    report = await application.programs.validate(
        definition.program_id, application.owner, expected_version=draft.version
    )
    assert not report.valid
    with pytest.raises(ProgramContractError):
        await application.programs.publish(
            definition.program_id, application.owner, expected_version=draft.version
        )
    child = await publish(
        application, "body", ApplicationDefinition(implementation="greeting", version="1")
    )
    bound = definition.model_copy(
        update={
            "implementation": definition.implementation.model_copy(
                update={"children": {"body": child.reference}}
            )
        }
    )
    saved = await application.programs.save(
        bound, application.owner, expected_version=draft.version
    )
    assert (
        await application.programs.validate(
            definition.program_id, application.owner, expected_version=saved.version
        )
    ).valid


async def test_draft_shape_and_configuration_still_reject_invalid_values(application):
    with pytest.raises(ValidationError, match="unique"):
        GraphDefinition(
            steps=(ProgramCallStep(uid="same", program={"program_id": "child", "revision": 1}),)
            * 2,
            entry="",
            exit="",
        )
    definition = ProgramDefinition(
        program_id="invalid-config",
        name="Invalid",
        owner=application.owner,
        implementation=ApplicationDefinition(
            implementation="map", version="1", config={"concurrency": 0}
        ),
    )
    with pytest.raises(ProgramContractError):
        await application.programs.save(definition, application.owner)


async def test_unfinished_topology_still_protects_private_configuration():
    secrets = MemorySecretStore()
    application = make_application(secrets)
    original = secret_definition("thread", "private-draft-value")
    definition = original.model_copy(
        update={
            "owner": application.owner,
            "implementation": original.implementation.model_copy(update={"entry": ""}),
        }
    )
    saved = await application.programs.save(definition, application.owner)
    assert "private-draft-value" not in saved.model_dump_json()
    private = saved.definition.implementation.resources[1].config["api_key"]
    assert is_secret_reference(private)
    assert (
        await secrets.get(application.owner, private)
    ).get_secret_value() == "private-draft-value"
    report = await application.programs.validate(
        definition.program_id, application.owner, expected_version=saved.version
    )
    assert not report.valid and "private-draft-value" not in report.model_dump_json()


@pytest.mark.parametrize(
    "change,code",
    [
        ({"entry": ""}, ProgramIssueCode.TOPOLOGY),
        ({"edges": {"typed-work": ("not-added-yet",)}}, ProgramIssueCode.TOPOLOGY),
        ({"resources": ()}, ProgramIssueCode.CONSTRUCTION),
    ],
)
async def test_incomplete_references_are_saved_but_reported_before_publication(
    application, change, code
):
    definition = ProgramDefinition(
        program_id="incomplete-reference",
        name="Pending connections",
        owner=application.owner,
        implementation=operation_graph().model_copy(update=change),
    )
    draft = await application.programs.save(definition, application.owner)
    report = await application.programs.validate(
        definition.program_id, application.owner, expected_version=draft.version
    )
    assert not report.valid and report.issues[0].code == code
    with pytest.raises(ProgramContractError) as rejected:
        await application.programs.publish(
            definition.program_id, application.owner, expected_version=draft.version
        )
    assert rejected.value.issue == report.issues[0]


async def test_validation_of_foreign_children_returns_no_foreign_definition_details(application):
    other = Identity.user("other")
    foreign = ProgramDefinition(
        program_id="foreign-child",
        name="Private title",
        owner=other,
        implementation=ApplicationDefinition(implementation="greeting", version="1"),
    )
    saved = await application.programs.save(foreign, other)
    child = await application.programs.publish(
        foreign.program_id, other, expected_version=saved.version
    )
    caller = ProgramDefinition(
        program_id="caller",
        name="Caller",
        owner=application.owner,
        implementation=GraphDefinition(
            steps=(ProgramCallStep(uid="work", program=child.reference),), entry="work", exit="work"
        ),
    )
    draft = await application.programs.save(caller, application.owner)
    report = await application.programs.validate(
        caller.program_id, application.owner, expected_version=draft.version
    )
    assert report.issues[0].code == ProgramIssueCode.REFERENCE
    assert (
        "Private title" not in report.model_dump_json()
        and "foreign-child" not in report.model_dump_json()
    )
