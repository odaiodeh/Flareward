"""Application condition contract with declared channel access and per-step context."""

from abc import ABC, abstractmethod
from typing import ClassVar

from lumora.elements.domain.conditions import ConditionOutputSchema, ConditionResult
from lumora.programs.graph.models.step_context import StepContext
from lumora.programs.graph.state.graph_state import GraphState
from lumora.programs.graph.state.state_view import StateView


class BaseCondition(ABC):
    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(self) -> None:
        self._ctx: StepContext | None = None

    def __call__(
        self, state: GraphState, config: dict[str, object] | None = None
    ) -> ConditionResult:
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
