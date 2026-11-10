from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.programs.graph.state.graph_state import GraphState
from lumora.programs.graph.validation.channel.models import DependencyMatrix
from lumora.programs.graph_elements import GraphElementSpec
from lumora.resources.domain.categories import ResourceCategory


class MatrixBuilder:
    """Builds dependency matrix from element registry."""

    def __init__(self, registry: ElementRegistry):
        self._registry = registry

    def build(self) -> DependencyMatrix:
        """Build dependency matrix from all registered elements."""
        producer_map = {}
        consumer_map = {}

        for category in (ResourceCategory.NODE, ResourceCategory.CONDITION):
            for type_key in self._registry.list_types(category):
                spec = GraphElementSpec.require(self._registry.get_spec(category, type_key))
                element_id = (category.value, type_key)

                # Update maps
                for channel in spec.writes:
                    producer_map.setdefault(channel, set()).add(element_id)

                for channel in spec.reads:
                    consumer_map.setdefault(channel, set()).add(element_id)

        return DependencyMatrix(
            producer_map=producer_map,
            consumer_map=consumer_map,
            external_channels=GraphState.get_external_channels(),
        )
