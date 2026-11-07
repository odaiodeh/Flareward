"""Publication rejects provable binding errors; dynamic values retain runtime validation."""

import pytest
from mas.application.programs.authoring import ProgramIssueCode
from mas.application.programs.contracts import BindingProjection
from mas.application.programs.interfaces import BindingContractError, InterfaceContract
from mas.application.programs.service import ProgramContractError
from mas.domain.programs.models import (
    GraphDefinition,
    LiteralBinding,
    PathBinding,
    ProgramBody,
    ProgramCallStep,
    ProgramDefinition,
)
from pydantic import ValidationError
from support.draft_configuration import CredentialConfig
from support.operations import operation_graph
from support.value_operations import ELEMENT_SPECIFICATIONS, ArraySpec, value_graph


@pytest.mark.parametrize("segment", [-1, True, 1.5])
def test_binding_indices_require_nonnegative_integers(segment):
    with pytest.raises(ValidationError):
        PathBinding(path=("items", segment))


def test_local_references_arrays_and_nullable_branches_preserve_known_paths():
    schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": {"$ref": "#/$defs/Item"}}},
        "additionalProperties": False,
        "$defs": {
            "Item": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {"title": {"type": "string"}},
                        "additionalProperties": False,
                    },
                    {"type": "null"},
                ]
            }
        },
    }
    InterfaceContract.check_schema(schema)
    contract = InterfaceContract.root(schema)
    contract.select(("items", 0, "title")).validate_value("valid")
    for path in (("missing",), ("items", 0, "missing"), ("items", "title")):
        with pytest.raises(BindingContractError):
            contract.select(path)
    with pytest.raises(BindingContractError):
        contract.select(("items", 0, "title")).validate_value(1)


def test_scoped_bundled_references_keep_full_validation_without_static_guesses():
    schema = {
        "$id": "urn:test:root",
        "$ref": "urn:test:inner",
        "$defs": {
            "Inner": {
                "$id": "urn:test:inner",
                "type": "object",
                "$defs": {"Text": {"type": "string"}},
                "properties": {"value": {"$ref": "#/$defs/Text"}},
                "required": ["value"],
            }
        },
    }
    InterfaceContract.check_schema(schema)
    contract = InterfaceContract.root(schema)
    contract.validate_value({"value": "valid"})
    contract.select(("value",))
    with pytest.raises(BindingContractError):
        contract.validate_value({"value": 1})


def test_recursive_analysis_terminates_and_unbundled_references_are_refused():
    schema = {
        "$ref": "#/$defs/Loop",
        "$defs": {
            "Loop": {
                "required": ["bound"],
                "allOf": [{"$ref": "#/$defs/Loop"}, {"$ref": "#/$defs/Loop"}],
            }
        },
    }
    contract = InterfaceContract.root(schema)
    assert contract.required() == {"bound"}
    contract.select(("dynamic", "path"))
    with pytest.raises(BindingContractError, match="bundled"):
        InterfaceContract.check_schema({"$ref": "https://unavailable.invalid/private-reference"})
    InterfaceContract.check_schema({"enum": [{"$ref": "https://unavailable.invalid/data"}]})


@pytest.mark.parametrize(
    "dialect", ["http://json-schema.org/draft-07/schema#", "urn:private-dialect"]
)
def test_schema_dialects_cannot_silently_change_execution_semantics(dialect):
    with pytest.raises(BindingContractError):
        InterfaceContract.check_schema({"$schema": dialect, "type": "object"})
    InterfaceContract.check_schema(
        {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}
    )


@pytest.mark.parametrize(
    "key,value", [("token", "private"), ("apiKey", "private"), ("auth", {"key": "private"})]
)
def test_model_input_aliases_use_the_actual_invocation_contract(key, value):
    BindingProjection().validate(
        {key: LiteralBinding(value=value), "endpoint": LiteralBinding(value="local")},
        model=CredentialConfig,
    )
    with pytest.raises(BindingContractError, match="Required"):
        BindingProjection().validate({key: PathBinding(path=("dynamic",))}, model=CredentialConfig)


@pytest.mark.parametrize(
    "problem", ["missing_input", "bad_literal", "result_path", "input_path", "missing_output"]
)
async def test_invalid_bindings_save_but_cannot_publish_and_have_safe_locations(
    application, problem
):
    graph = operation_graph()
    step = graph.steps[0]
    input_schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
    }
    if problem == "missing_input":
        graph = graph.model_copy(update={"steps": (step.model_copy(update={"inputs": {}}),)})
    elif problem == "bad_literal":
        graph = graph.model_copy(
            update={
                "steps": (
                    step.model_copy(
                        update={
                            "inputs": {"text": LiteralBinding(value={"secret": "private-literal"})}
                        }
                    ),
                )
            }
        )
    elif problem == "result_path":
        graph = graph.model_copy(
            update={
                "steps": (
                    step.model_copy(update={"outputs": {"values": PathBinding(path=("missing",))}}),
                )
            }
        )
    elif problem == "input_path":
        graph = graph.model_copy(update={"inputs": {"user_prompt": PathBinding(path=("missing",))}})
    else:
        graph = graph.model_copy(update={"outputs": {}})
    root = ProgramDefinition(
        program_id="binding",
        name="Binding",
        owner=application.owner,
        implementation=graph,
        input_schema=input_schema,
        output_schema=output_schema,
    )
    draft = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        "binding", application.owner, expected_version=draft.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
    assert report.issues[0].path[:1] == ("implementation",)
    assert "private-literal" not in report.model_dump_json()
    with pytest.raises(ProgramContractError) as raised:
        await application.programs.publish(
            "binding", application.owner, expected_version=draft.version
        )
    assert raised.value.issue == report.issues[0]
    assert not (await application.programs.revisions("binding", application.owner)).revisions


@pytest.mark.parametrize("owned", [True, False])
async def test_program_calls_use_owned_or_pinned_input_contracts(application, owned):
    body = ProgramBody(
        implementation=operation_graph(), input_schema={"type": "object", "required": ["name"]}
    )
    if owned:
        target = body
    else:
        definition = ProgramDefinition(
            program_id="child", name="Child", owner=application.owner, **body.model_dump()
        )
        saved = await application.programs.save(definition, application.owner)
        target = (
            await application.programs.publish(
                "child", application.owner, expected_version=saved.version
            )
        ).reference
    root = ProgramDefinition(
        program_id="caller",
        name="Caller",
        owner=application.owner,
        implementation=GraphDefinition(
            steps=(ProgramCallStep(uid="call", program=target),), entry="call", exit="call"
        ),
    )
    saved = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        "caller", application.owner, expected_version=saved.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
    assert report.issues[0].path == ("implementation", "steps", 0, "inputs")
    completed = root.model_copy(
        update={
            "implementation": root.implementation.model_copy(
                update={
                    "steps": (
                        ProgramCallStep(
                            uid="call",
                            program=target,
                            inputs={"name": PathBinding(path=("input", "name"))},
                        ),
                    )
                }
            )
        }
    )
    changed = await application.programs.save(
        completed, application.owner, expected_version=saved.version
    )
    assert (
        await application.programs.validate(
            "caller", application.owner, expected_version=changed.version
        )
    ).valid


async def test_unbundled_schema_reference_is_refused_safely_before_draft_storage(application):
    root = ProgramDefinition(
        program_id="unbundled",
        name="Unbundled",
        owner=application.owner,
        implementation=operation_graph(),
        input_schema={"$ref": "https://unavailable.invalid/private-schema"},
    )
    with pytest.raises(ProgramContractError) as raised:
        await application.programs.save(root, application.owner)
    assert "private-schema" not in str(raised.value)
    assert not (await application.programs.list(application.owner)).programs


@pytest.mark.parametrize(
    "problem", ["literal_input", "literal_output", "reserved_input", "reserved_output"]
)
async def test_whole_value_and_reserved_scope_errors_remain_draft_only(application, problem):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    graph = value_graph(ArraySpec)
    if problem == "literal_input":
        graph = graph.model_copy(
            update={
                "steps": (
                    graph.steps[0].model_copy(
                        update={"inputs": LiteralBinding(value="private-not-an-array")}
                    ),
                )
            }
        )
    elif problem == "literal_output":
        graph = graph.model_copy(update={"outputs": LiteralBinding(value="private-not-an-array")})
    elif problem == "reserved_input":
        graph = graph.model_copy(update={"inputs": {"input": LiteralBinding(value=[])}})
    else:
        graph = graph.model_copy(
            update={
                "steps": (
                    graph.steps[0].model_copy(
                        update={"outputs": {"results": PathBinding(path=())}}
                    ),
                )
            }
        )
    root = ProgramDefinition(
        program_id="root-value",
        name="Root value",
        owner=application.owner,
        implementation=graph,
        input_schema={"type": "array"},
        output_schema={"type": "array"},
    )
    saved = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        "root-value", application.owner, expected_version=saved.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
    assert "private-not-an-array" not in report.model_dump_json()
    with pytest.raises(ProgramContractError):
        await application.programs.publish(
            "root-value", application.owner, expected_version=saved.version
        )
