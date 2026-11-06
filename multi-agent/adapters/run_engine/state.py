"""Typed engine state reuses the domain fields and their reducer annotations."""

from mas.application.programs.state import ProgramState
from pydantic import ConfigDict
from runengine.programs.graph.models.state import GraphState as RuntimeGraphState

__runengine_contract__ = "unifai-graph-state-v3"


class ProgramGraphState(ProgramState, RuntimeGraphState):
    """Bind application channels to the native graph state protocol."""

    model_config = ConfigDict(**ProgramState.model_config)
