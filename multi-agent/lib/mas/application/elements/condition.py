"""Application condition contract with declared channel access and per-step context."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import ClassVar

from mas.domain.conditions import ConditionOutputSchema, ConditionResult
from mas.graph.models.step_context import StepContext
from mas.graph.state.graph_state import GraphState
from mas.graph.state.state_view import StateView


class ConditionResultError(ValueError):
    """A condition returned an invalid or undeclared routing outcome."""


def normalize_condition_result(value: object, branches: Mapping[str, str]) -> str | list[str]:
    if isinstance(value, bool):
        result = str(value).lower()
    elif isinstance(value, str):
        result = value
    elif isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        result = list(value)
    else:
        raise ConditionResultError("Condition must return a boolean, string or sequence of strings")
    labels = [result] if isinstance(result, str) else result
    if any(label not in branches and label != "END" for label in labels):
        raise ConditionResultError("Condition returned an undeclared branch")
    return result


class BaseCondition(ABC):
    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(self) -> None:
        self._ctx: StepContext | None = None

    def __call__(self, state: GraphState, config: dict | None = None) -> ConditionResult:
        return self.run(StateView(state, reads=self.read_channels(), writes=self.write_channels()))

    @abstractmethod
    def run(self, state: StateView) -> ConditionResult: ...

    def set_context(self, step_ctx: StepContext) -> None:
        self._ctx = step_ctx

    @property
    def context(self) -> StepContext | None:
        return self._ctx

    @classmethod
    def read_channels(cls) -> set[str]:
        return set(cls.READS)

    @classmethod
    def write_channels(cls) -> set[str]:
        return set(cls.WRITES)

    @classmethod
    @abstractmethod
    def get_output_schema(cls) -> ConditionOutputSchema: ...
