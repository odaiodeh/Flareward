"""Select explicit state adapters required by the capabilities in a graph Program."""

from collections.abc import Set
from typing import Annotated, Self

from lumora.programs.domain.models import ElementStep, GraphDefinition
from lumora.programs.graph.state.graph_state import GraphState
from lumora.programs.state import ProgramState, StateContractError, replace_value


class AgentProgramState(ProgramState, GraphState):
    """MAS node adapters add conversation/workload channels to ordinary Program data."""

    model_config = ProgramState.model_config
    output: Annotated[str, replace_value] = ""

    def accept_node(self, result: GraphState, *, writes: Set[str]) -> Self:
        original = self.serialize()
        try:
            returned = result.model_dump(mode="json", warnings="error")
        except ValueError, TypeError:
            raise StateContractError("Node state must contain portable channel values") from None
        changed = {name: value for name, value in returned.items() if original.get(name) != value}
        self._writable(changed)
        if changed.keys() - writes:
            raise StateContractError("Node returned changes outside its declared write contract")
        return type(self).model_validate({**original, **returned})


def graph_state_type(graph: GraphDefinition) -> type[ProgramState]:
    """Only state-based node/condition adapters require MAS-specific channels."""
    if graph.conditions or any(isinstance(step, ElementStep) for step in graph.steps):
        return AgentProgramState
    return ProgramState
