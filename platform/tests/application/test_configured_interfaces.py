"""Configuration-resolved constraints are frozen and applied to reusable callers."""

import pytest
from support.typed_programs import COORDINATORS, BoundedEchoConfig, definition

from lumora.programs.authoring import ProgramIssueCode
from lumora.programs.domain.bindings import LiteralBinding
from lumora.programs.domain.interfaces import ProgramSchemas
from lumora.programs.domain.models import GraphDefinition, ProgramBody, ProgramCallStep
from lumora.programs.service import ProgramContractError


@pytest.fixture
async def bounded(application):
    application.applications.register(COORDINATORS[-1])
    draft = await application.programs.save(
        definition(application.owner, implementation="bounded_echo"), application.owner
    )
    return await application.programs.publish(
        draft.definition.program_id, application.owner, expected_version=draft.version
    )


async def test_configured_contract_is_frozen_until_a_new_publication(application, bounded):
    saved = await application.programs.draft(bounded.definition.program_id, application.owner)
    changed = saved.definition.model_copy(
        update={
            "implementation": saved.definition.implementation.model_copy(
                update={"config": {"limit": 10}}
            )
        }
    )
    edited = await application.programs.save(
        changed, application.owner, expected_version=saved.version
    )
    newer = await application.programs.publish(
        changed.program_id, application.owner, expected_version=edited.version
    )
    assert bounded.interface.configured.input_schema["properties"]["value"]["maximum"] == 5
    assert newer.interface.configured.input_schema["properties"]["value"]["maximum"] == 10
    assert newer.content_digest != bounded.content_digest
    assert await application.programs.revision(bounded.reference, application.owner) == bounded


@pytest.mark.parametrize("owned", [False, True])
async def test_caller_literal_is_checked_against_configured_dependency_contract(
    application, bounded, owned
):
    graph = GraphDefinition(
        steps=(
            ProgramCallStep(
                uid="call",
                program=ProgramBody(implementation=bounded.definition.implementation)
                if owned
                else bounded.reference,
                inputs={"value": LiteralBinding(value=6)},
            ),
        ),
        entry="call",
        exit="call",
    )
    root = bounded.definition.model_copy(update={"program_id": "caller", "implementation": graph})
    draft = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        root.program_id, application.owner, expected_version=draft.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
    with pytest.raises(ProgramContractError):
        await application.programs.publish(
            root.program_id, application.owner, expected_version=draft.version
        )


async def test_disjoint_authored_and_configured_contracts_reject_publication(application, bounded):
    root = bounded.definition.model_copy(
        update={"program_id": "disjoint", "input_schema": {"type": "array"}}
    )
    draft = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        root.program_id, application.owner, expected_version=draft.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING


async def test_changed_configured_declaration_rejects_admission(application, bounded, monkeypatch):
    monkeypatch.setattr(
        BoundedEchoConfig,
        "program_interface",
        lambda self: ProgramSchemas(input_schema={"type": "array"}),
    )
    with pytest.raises(ProgramContractError, match="published contract"):
        await application.programs.validate_revision(bounded, application.owner)


async def test_invalid_configured_schema_has_safe_readiness_diagnostics(
    application, bounded, monkeypatch
):
    monkeypatch.setattr(
        BoundedEchoConfig,
        "program_interface",
        lambda self: ProgramSchemas(input_schema={"type": "private-invalid-type"}),
    )
    draft = await application.programs.draft(bounded.definition.program_id, application.owner)
    report = await application.programs.validate(
        draft.definition.program_id, application.owner, expected_version=draft.version
    )
    assert not report.valid and "private-invalid-type" not in report.model_dump_json()


@pytest.mark.parametrize("result", [None, {"input_schema": {"type": "object"}}])
async def test_configured_interface_requires_the_declared_value_contract(
    application, bounded, monkeypatch, result
):
    monkeypatch.setattr(BoundedEchoConfig, "program_interface", lambda self: result)
    draft = await application.programs.draft(bounded.definition.program_id, application.owner)
    report = await application.programs.validate(
        draft.definition.program_id, application.owner, expected_version=draft.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
