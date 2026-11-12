"""Published contracts stay authoritative across authoring and installed-code changes."""

from dataclasses import replace
from unittest.mock import create_autospec

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from support.typed_programs import COORDINATORS, Numbers, TypedInput, definition

from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramBody, ProgramRevision
from lumora.programs.invocation import CoordinatorInvoker, ProgramInvocationContractError
from lumora.programs.ports import ProgramRuntime
from lumora.programs.service import ProgramContractError
from lumora.programs.signatures import ProgramInterfaces


@pytest.fixture
async def published(application):
    application.applications.register(COORDINATORS[0])
    draft = await application.programs.save(definition(application.owner), application.owner)
    return await application.programs.publish(
        draft.definition.program_id, application.owner, expected_version=draft.version
    )


async def test_publication_freezes_canonical_models_and_detaches_reader_mutations(
    application, published
):
    contract = published.interface
    assert "amountAlias" in contract.input_model_schema["properties"]
    assert "amount" in contract.normalized_input_schema["properties"]
    assert "amountAlias" not in contract.normalized_input_schema["properties"]
    assert "summary" in contract.normalized_output_schema["required"]
    assert "label" in contract.normalized_output_schema["properties"]
    contract.normalized_input_schema["properties"].clear()
    loaded = await application.programs.revision(published.reference, application.owner)
    assert "amount" in loaded.interface.normalized_input_schema["properties"]


async def test_owned_interfaces_do_not_expand_pinned_dependencies(application, published):
    root = ProgramBody(
        implementation=CustomCoordinatorDefinition(
            implementation="greeting",
            version="1",
            children={
                "owned": ProgramBody(implementation=published.definition.implementation),
                "pinned": published.reference,
            },
        )
    )
    snapshot = ProgramInterfaces(application.applications).snapshot(root)
    assert snapshot.at(("owned",)) == published.interface
    assert set(snapshot.children) == {"owned"}
    with pytest.raises(ValueError, match="owned Program"):
        snapshot.at(("pinned",))


@pytest.mark.parametrize("change", ["input", "output", "version"])
async def test_changed_worker_declaration_is_rejected_before_coordinator_effects(published, change):
    registration = COORDINATORS[0]
    updates = (
        {"input_model": Numbers}
        if change == "input"
        else ({"result_model": Numbers} if change == "output" else {"version": "2"})
    )
    runtime = create_autospec(ProgramRuntime, instance=True)
    with pytest.raises(ProgramInvocationContractError, match="published contract"):
        await CoordinatorInvoker(replace(registration, **updates), published.interface).invoke(
            runtime, {"amountAlias": "3", "label": "valid"}, {}
        )
    assert not runtime.mock_calls


async def test_admission_detects_schema_change_under_the_same_installed_identity(
    application, published, monkeypatch
):
    monkeypatch.setattr(TypedInput, "model_json_schema", Numbers.model_json_schema)
    with pytest.raises(ProgramContractError, match="published contract"):
        await application.programs.validate_revision(published, application.owner)


@pytest.mark.parametrize("mutation", ["normalization", "missing", "owned"])
async def test_revision_integrity_covers_the_interface(published, mutation):
    document = published.model_dump(mode="json")
    if mutation == "missing":
        del document["interface"]
    elif mutation == "normalization":
        document["interface"]["normalized_input_schema"] = {"type": "array"}
    else:
        document["interface"]["children"]["unexpected"] = published.interface.model_dump(
            mode="json"
        )
    with pytest.raises(ValidationError):
        ProgramRevision.model_validate(document)


@pytest.mark.parametrize("invalid", [False, True])
async def test_worker_rejects_changed_validation_schema_even_if_serialization_is_unchanged(
    published, monkeypatch, invalid
):
    schema = TypedInput.model_json_schema

    def changed_schema(**kwargs):
        document = schema(**kwargs)
        if kwargs.get("mode") == "validation":
            if invalid:
                document["type"] = "private-invalid-schema"
            else:
                document["properties"]["newAlias"] = document["properties"].pop("amountAlias")
        return document

    monkeypatch.setattr(TypedInput, "model_json_schema", changed_schema)
    with pytest.raises(ProgramInvocationContractError, match="published contract") as raised:
        CoordinatorInvoker(COORDINATORS[0], published.interface)
    assert "private-invalid-schema" not in str(raised.value)


def test_snapshot_preserves_local_reference_scopes_and_detaches_source(application):
    application.applications.register(COORDINATORS[0])
    body = ProgramBody(
        input_schema={"$defs": {"value": {"type": "string"}}, "$ref": "#/$defs/value"},
        output_schema={"$defs": {"value": {"type": "integer"}}, "$ref": "#/$defs/value"},
        implementation=CustomCoordinatorDefinition(implementation="typed_program", version="1"),
    )
    interface = ProgramInterfaces(application.applications).snapshot(body)
    Draft202012Validator(interface.input_schema).validate("text")
    Draft202012Validator(interface.output_schema).validate(3)
    body.input_schema["$defs"]["value"]["type"] = "null"
    assert interface.input_schema["$defs"]["value"]["type"] == "string"
