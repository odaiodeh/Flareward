"""Generic mapping extension remains portable and preserves legacy payload shape."""

import pytest
from pydantic import ValidationError
from runengine import GraphBuilder
from runengine.coordination.models import RunRequest
from runengine.programs.graph.inputs import GraphProgramInput
from runengine.programs.graph.models.execution import GraphCallArguments
from runengine.programs.graph.models.program import ProgramNode

from lumora.executions.adapters.run_engine.inbound.programs import (
    execute_program,
    map_program_inputs,
    map_program_outputs,
)
from lumora.executions.adapters.run_engine.shared.state import ProgramGraphState


def test_empty_mapping_arguments_do_not_change_existing_payloads():
    node = ProgramNode(request=RunRequest.create(execute_program))
    payload = node.model_dump(mode="json")
    assert "input_arguments" not in payload
    assert "output_arguments" not in payload
    assert ProgramNode.model_validate(payload) == node


def test_mapping_arguments_require_an_installed_mapping():
    with pytest.raises(ValidationError, match="require a mapping function"):
        ProgramNode(
            request=RunRequest.create(execute_program),
            input_arguments=GraphCallArguments(kwargs={"bindings": {}}),
        )


def test_compilation_snapshots_mapping_configuration():
    bindings = {"name": {"kind": "path", "path": ["user_prompt"]}}
    graph = (
        GraphBuilder(ProgramGraphState)
        .add_program_node(
            "child",
            RunRequest.create(execute_program),
            input_mapping=map_program_inputs,
            output_mapping=map_program_outputs,
            input_arguments=GraphCallArguments(kwargs={"bindings": bindings}),
            output_arguments=GraphCallArguments(kwargs={"bindings": {}, "key": "child"}),
        )
        .compile()
    )
    bindings["name"]["path"] = ["output"]
    payload = GraphProgramInput.model_validate(graph.request(ProgramGraphState()).input)
    assert payload.programs["child"].input_arguments.kwargs["bindings"]["name"]["path"] == [
        "user_prompt"
    ]


def test_invalid_mapping_signature_is_refused_before_execution():
    with pytest.raises(TypeError):
        GraphBuilder(ProgramGraphState).add_program_node(
            "child",
            RunRequest.create(execute_program),
            input_mapping=map_program_inputs,
        ).compile()
