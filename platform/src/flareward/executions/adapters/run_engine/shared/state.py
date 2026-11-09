"""Typed engine state reuses the domain fields and their reducer annotations."""

from pydantic import ConfigDict
from runengine.programs.graph.models.state import GraphState as RuntimeGraphState

from flareward.programs.domain.models import GraphDefinition
from flareward.programs.graph_state import AgentProgramState, graph_state_type
from flareward.programs.state import ProgramState

__runengine_contract__ = "flareward-graph-state-v4"


class ProgramGraphState(ProgramState, RuntimeGraphState):
    """Bind application channels to the native graph state protocol."""

    model_config = ConfigDict(**ProgramState.model_config)


class AgentProgramGraphState(AgentProgramState, ProgramGraphState):
    """Engine binding for Programs containing state-based agent adapters."""


def engine_state_type(graph: GraphDefinition) -> type[ProgramGraphState]:
    return (
        AgentProgramGraphState
        if graph_state_type(graph) is AgentProgramState
        else ProgramGraphState
    )
