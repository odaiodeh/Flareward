"""Graph-local interfaces preserve schema scopes and require explicit producer ordering."""

import pytest
from mas.application.programs.authoring import ProgramIssueCode
from mas.application.programs.interfaces import BindingContractError, InterfaceContract
from mas.application.programs.service import ProgramContractError
from mas.domain.programs.models import (
    ApplicationDefinition,
    GraphDefinition,
    LiteralBinding,
    PathBinding,
    ProgramBody,
    ProgramCallStep,
    ProgramDefinition,
)
from support.typed_programs import APPLICATION_PROGRAMS


@pytest.fixture(autouse=True)
def installed(application):
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)


def identity(*, inputs=None, outputs=None):
    return ProgramBody(
        implementation=ApplicationDefinition(implementation="identity_program", version="1"),
        input_schema={} if inputs is None else inputs,
        output_schema={} if outputs is None else outputs,
    )


@pytest.mark.parametrize(
    "source,target,valid",
    [
        ("integer", "number", True),
        ("number", "integer", True),
        ("string", "integer", False),
        (["null", "string"], "string", True),
    ],
)
def test_type_overlap_is_conservative_and_preserves_integer_subtyping(source, target, valid):
    supplied, expected = (
        InterfaceContract.root({"type": source}),
        InterfaceContract.root({"type": target}),
    )
    if valid:
        supplied.check_overlap(expected)
    else:
        with pytest.raises(BindingContractError, match="types"):
            supplied.check_overlap(expected)


@pytest.mark.parametrize(
    "problem", ["unknown_producer", "self", "unordered", "result_path", "result_type", "input_path"]
)
async def test_invalid_graph_reads_save_but_cannot_publish(application, problem):
    producer = identity(
        outputs={
            "type": "object",
            "properties": {"score": {"type": "integer"}},
            "additionalProperties": False,
        }
    )
    consumer = identity(inputs={"type": "integer"})
    path = ("results", "produce", "score")
    if problem == "unknown_producer":
        path = ("results", "unknown", "score")
    elif problem == "self":
        path = ("results", "consume")
    elif problem == "result_path":
        path = ("results", "produce", "missing")
    elif problem == "result_type":
        consumer = identity(inputs={"type": "string"})
    elif problem == "input_path":
        path = ("input", "missing")
    graph = GraphDefinition(
        steps=(
            ProgramCallStep(
                uid="produce", program=producer, inputs=LiteralBinding(value={"score": 3})
            ),
            ProgramCallStep(uid="consume", program=consumer, inputs=PathBinding(path=path)),
        ),
        edges={} if problem == "unordered" else {"produce": ("consume",)},
        entry="produce",
        exit="consume",
    )
    root = ProgramDefinition(
        program_id="reads",
        name="Reads",
        owner=application.owner,
        implementation=graph,
        input_schema={"type": "object", "properties": {"known": {}}, "additionalProperties": False},
    )
    saved = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        "reads", application.owner, expected_version=saved.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
    assert report.issues[0].path[:4] == ("implementation", "steps", 1, "inputs")
    with pytest.raises(ProgramContractError) as refused:
        await application.programs.publish(
            "reads", application.owner, expected_version=saved.version
        )
    assert refused.value.issue == report.issues[0]


async def test_input_and_result_local_references_keep_their_original_documents(application):
    nested = {
        "type": "object",
        "properties": {"value": {"$ref": "#/$defs/Count"}},
        "required": ["value"],
        "additionalProperties": False,
        "$defs": {"Count": {"type": "integer"}},
    }
    graph = GraphDefinition(
        steps=(
            ProgramCallStep(
                uid="produce",
                program=identity(inputs=nested, outputs=nested),
                inputs={"value": PathBinding(path=("input", "value"))},
            ),
            ProgramCallStep(
                uid="consume",
                program=identity(inputs={"type": "integer"}),
                inputs=PathBinding(path=("results", "produce", "value")),
            ),
        ),
        edges={"produce": ("consume",)},
        entry="produce",
        exit="consume",
        outputs=PathBinding(path=("results", "consume")),
    )
    root = ProgramDefinition(
        program_id="scopes",
        name="Scopes",
        owner=application.owner,
        implementation=graph,
        input_schema=nested,
        output_schema={},
    )
    saved = await application.programs.save(root, application.owner)
    assert (
        await application.programs.validate(
            "scopes", application.owner, expected_version=saved.version
        )
    ).valid


async def test_installed_model_coercion_is_not_rejected_as_public_json_type_incompatibility(
    application,
):
    typed = ProgramBody(
        implementation=ApplicationDefinition(implementation="typed_program", version="1")
    )
    graph = GraphDefinition(
        steps=(
            ProgramCallStep(
                uid="typed",
                program=typed,
                inputs={
                    "amountAlias": PathBinding(path=("input", "amount")),
                    "label": LiteralBinding(value="coerced"),
                },
            ),
        ),
        entry="typed",
        exit="typed",
    )
    root = ProgramDefinition(
        program_id="coercion",
        name="Coercion",
        owner=application.owner,
        implementation=graph,
        input_schema={
            "type": "object",
            "properties": {"amount": {"type": "string"}},
            "required": ["amount"],
        },
    )
    saved = await application.programs.save(root, application.owner)
    assert (
        await application.programs.validate(
            "coercion", application.owner, expected_version=saved.version
        )
    ).valid


@pytest.mark.parametrize("path", [(), ("results",)])
async def test_graph_state_and_result_index_are_objects_not_the_root_invocation_value(
    application, path
):
    graph = GraphDefinition(
        steps=(
            ProgramCallStep(
                uid="array",
                program=identity(inputs={"type": "array"}),
                inputs=PathBinding(path=path),
            ),
        ),
        entry="array",
        exit="array",
    )
    root = ProgramDefinition(
        program_id="object-scope",
        name="Object scope",
        owner=application.owner,
        implementation=graph,
        input_schema={"type": "array"},
    )
    saved = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        "object-scope", application.owner, expected_version=saved.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
