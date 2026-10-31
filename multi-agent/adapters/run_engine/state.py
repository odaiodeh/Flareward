"""Typed engine state reuses the domain fields and their reducer annotations."""

from typing import Annotated

from mas.graph.state.graph_state import GraphState
from pydantic import Field, JsonValue
from runengine.programs.graph.models.state import GraphState as RuntimeGraphState

__runengine_contract__ = "unifai-graph-state-v1"


def merge_values(old: dict[str, JsonValue], new: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {**old, **new}


class ProgramGraphState(GraphState, RuntimeGraphState):
    values: Annotated[dict[str, JsonValue], merge_values] = Field(default_factory=dict)
