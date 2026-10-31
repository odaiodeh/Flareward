from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.core.enums import ResourceCategory
from mas.graph.state.graph_state import GraphState

from .models import DependencyMatrix


class MatrixBuilder:
    """Builds dependency matrix from element registry."""

    def __init__(self, registry: ElementRegistry):
        self._registry = registry

    def build(self) -> DependencyMatrix:
        """Build dependency matrix from all registered elements."""
        producer_map = {}
        consumer_map = {}

        # Process all element categories
        for category in ResourceCategory:
            for type_key in self._registry.list_types(ResourceCategory(category)):
                spec = self._registry.get_spec(ResourceCategory(category), type_key)
                element_id = (ResourceCategory(category).value, type_key)

                # Extract reads/writes
                reads = self._get_reads(spec)
                writes = self._get_writes(spec)

                # Update maps
                for channel in writes:
                    producer_map.setdefault(channel, set()).add(element_id)

                for channel in reads:
                    consumer_map.setdefault(channel, set()).add(element_id)

        return DependencyMatrix(
            producer_map=producer_map,
            consumer_map=consumer_map,
            external_channels=GraphState.get_external_channels(),
        )

    def _get_reads(self, spec) -> set[str]:
        """Extract read channels from element spec."""
        return getattr(spec, "reads", set())

    def _get_writes(self, spec) -> set[str]:
        """Extract write channels from element spec."""
        return getattr(spec, "writes", set())
