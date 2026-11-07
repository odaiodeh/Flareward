"""Input and result scopes belong to graph invocation/mapping, not arbitrary writes."""

import pytest
from mas.application.programs.graph_state import AgentProgramState, graph_state_type
from mas.application.programs.state import ProgramState, StateContractError
from mas.domain.programs.models import ElementStep, GraphDefinition
from mas.graph.state.graph_state import GraphState


def test_data_graphs_accept_structured_results_without_conversation_channels():
    state = ProgramState(input={"issue": 42}).record_result(
        "work", {"done": True}, {"output": {"commit": "immutable-id"}}
    )
    assert state.output == {"commit": "immutable-id"}
    assert set(state.serialize()) == {"input", "results", "values", "output"}
    assert not issubclass(ProgramState, GraphState)


def test_only_state_based_capabilities_select_the_agent_state_adapter():
    assert graph_state_type(GraphDefinition(steps=())) is ProgramState
    graph = GraphDefinition(
        steps=(ElementStep(uid="agent", element={"category": "nodes", "rid": "agent"}),)
    )
    assert graph_state_type(graph) is AgentProgramState
    assert "messages" in graph_state_type(graph).model_fields


def test_recorded_root_values_preserve_original_input_and_other_results():
    state = ProgramState(input=[1], results={"prior": None})
    updated = state.record_result("child", [2], {"output": "finished"})
    assert updated.input == [1]
    assert updated.results == {"prior": None, "child": [2]}
    assert updated.output == "finished"
    assert state.results == {"prior": None} and state.output is None


@pytest.mark.parametrize("field", ["input", "results"])
def test_portable_output_and_resume_updates_cannot_replace_reserved_scopes(field):
    state = ProgramState(input=[1])
    with pytest.raises(StateContractError, match="read-only"):
        state.with_updates({field: "private-value"})
    with pytest.raises(StateContractError, match="read-only"):
        state.record_result("child", [2], {field: "private-value"})


def test_unknown_graph_output_destinations_fail_without_echoing_values():
    with pytest.raises(StateContractError) as failed:
        ProgramState().record_result("child", None, {"unknown": "private-value"})
    assert "private-value" not in str(failed.value)


@pytest.mark.parametrize("update", [{"values": []}, {"values": "private"}])
def test_malformed_channel_updates_have_safe_application_errors(update):
    with pytest.raises(StateContractError) as failed:
        ProgramState().record_result("child", None, update)
    assert "private" not in str(failed.value)


def test_node_write_declarations_are_enforced_against_actual_returned_state():
    state = AgentProgramState(user_prompt="initial")
    returned = GraphState(user_prompt="private-change", output="answer")
    with pytest.raises(StateContractError, match="declared") as failed:
        state.accept_node(returned, writes={"output"})
    assert "private-change" not in str(failed.value)
    accepted = state.accept_node(returned, writes={"user_prompt", "output"})
    assert accepted.user_prompt == "private-change" and accepted.output == "answer"
