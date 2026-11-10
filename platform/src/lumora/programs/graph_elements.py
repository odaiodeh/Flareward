"""State-channel declarations belong to graph adapters, not generic element specifications."""

from collections.abc import Set
from typing import ClassVar, Protocol, runtime_checkable

from lumora.elements.specification import BaseElementSpec
from lumora.programs.graph.models.step_context import StepContext
from lumora.programs.graph.state.state_view import StateView
from lumora.resources.domain.categories import ResourceCategory


@runtime_checkable
class SupportsStateContext(Protocol):
    """State-based graph adapters expose their restricted state and step context."""

    def get_state(self) -> StateView: ...
    def get_context(self) -> StepContext: ...


@runtime_checkable
class SupportsStepContext(Protocol):
    """Graph binding supplies topology to adapters that explicitly support it."""

    def set_context(self, ctx: StepContext) -> None: ...


class GraphElementSpec(BaseElementSpec, abstract=True):
    """Specialized specification for state-based graph nodes and conditions."""

    reads: ClassVar[Set[str]] = frozenset()
    writes: ClassVar[Set[str]] = frozenset()

    @classmethod
    def validate_declaration(cls) -> None:
        super().validate_declaration()
        if cls.category not in (ResourceCategory.NODE, ResourceCategory.CONDITION):
            raise TypeError("Graph specifications apply only to nodes and conditions")
        for channels in (cls.reads, cls.writes):
            if not isinstance(channels, Set) or any(
                not isinstance(channel, str) or not channel for channel in channels
            ):
                raise TypeError("Graph channels must be sets of nonempty names")

    @staticmethod
    def require(specification: type[BaseElementSpec]) -> type[GraphElementSpec]:
        if not issubclass(specification, GraphElementSpec):
            raise ValueError("Graph node or condition requires a graph specification")
        return specification
