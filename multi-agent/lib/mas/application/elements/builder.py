"""
Builds a ElementInstances from a ResourceCollections by orchestrating one
CategoryBuilder per resource category.

Key features
------------
* **Data-driven** – Build order is derived from `depends_on` declared on each
  CategoryBuilder subclass.  No hard-coded lists beyond registration.
* **Validated** – Unknown dependencies and cyclic graphs raise ValueError
  before any expensive objects are constructed.
* **SOLID** – The class depends only on the CategoryBuilder abstraction and
  ElementInstances protocol; adding a new category means writing one new
  builder and importing it here.
"""

from collections import deque

from mas.application.elements.categories.category_builder import CategoryBuilder
from mas.application.elements.categories.condition_builder import ConditionBuilder
from mas.application.elements.categories.llm_builder import LLMBuilder
from mas.application.elements.categories.node_builder import NodeBuilder
from mas.application.elements.categories.operation_builder import OperationBuilder

# concrete builders
from mas.application.elements.categories.provider_builder import ProviderBuilder
from mas.application.elements.categories.retriever_builder import RetrieverBuilder
from mas.application.elements.categories.tool_builder import ToolBuilder
from mas.application.elements.construction.collections import ResourceCollections
from mas.application.elements.instances import ElementInstances
from mas.core.element_deps import ElementBuildContext
from mas.core.enums import ResourceCategory


class SessionElementBuilder:
    """
    Orchestrates CategoryBuilders → returns a fully-populated ElementInstances.
    """

    # Register all category builders once.  Order does *not* matter here;
    # topological sort from depends_on determines build order.
    _BUILDER_CLASSES: list[type[CategoryBuilder]] = [
        ProviderBuilder,
        LLMBuilder,
        RetrieverBuilder,
        ConditionBuilder,
        ToolBuilder,
        NodeBuilder,
        OperationBuilder,
    ]

    # --------------------------------------------------------------------- #
    # Public API                                                            #
    # --------------------------------------------------------------------- #
    def __init__(self, element_registry):
        """
        Parameters
        ----------
        element_registry : ElementRegistry
            The plugin registry that knows every factory/schema pair.
            It is forwarded to each CategoryBuilder.
        """
        self._builders: dict[ResourceCategory, CategoryBuilder] = {
            cls.category: cls(element_registry) for cls in self._BUILDER_CLASSES
        }
        # raises early on unknown deps / cycles
        self._ordered_builders: list[CategoryBuilder] = self._topological_order()

    # -- main entry ------------------------------------------------------------
    def build(
        self,
        blueprint: ResourceCollections,
        deps: ElementBuildContext | None = None,
    ) -> ElementInstances:
        """Return a fully populated ElementInstances.

        Cross-cutting runtime concerns are forwarded via the typed
        ``ElementBuildContext`` bag to each CategoryBuilder.
        """
        registry = ElementInstances()

        for builder in self._ordered_builders:
            builder.build(blueprint, registry, deps=deps)

        registry.freeze()
        return registry

    @property
    def resource_builders(self) -> dict[ResourceCategory, CategoryBuilder]:
        """Expose construction strategies without coupling callers to blueprint plans."""
        return dict(self._builders)

    # --------------------------------------------------------------------- #
    # Internal helpers                                                      #
    # --------------------------------------------------------------------- #
    def _topological_order(self) -> list[CategoryBuilder]:
        """
        Kahn’s algorithm topological sort.

        Raises
        ------
        ValueError
            • if any builder lists an unknown dependency
            • if a cyclic dependency is found
        """
        # Build adjacency map: category -> deps
        graph: dict[ResourceCategory, set[ResourceCategory]] = {
            cat: set(b.depends_on) for cat, b in self._builders.items()
        }

        # --- validation: unknown deps -----------------------------------
        unknown = {d for deps in graph.values() for d in deps} - graph.keys()
        if unknown:
            cats = ", ".join(item.value for item in sorted(unknown))
            raise ValueError(f"Unknown builder dependency(ies): {cats}")

        # --- Kahn -------------------------------------------------------
        queue = deque([cat for cat, deps in graph.items() if not deps])
        ordered: list[CategoryBuilder] = []

        while queue:
            cat = queue.popleft()
            ordered.append(self._builders[cat])

            # remove edges
            for tgt in list(graph):
                if cat in graph[tgt]:
                    graph[tgt].discard(cat)
                    if not graph[tgt]:
                        queue.append(tgt)
            graph.pop(cat, None)

        # --- cycle detection -------------------------------------------
        if graph:  # any remaining nodes ⇒ cycle
            cycle = " → ".join(cat.value for cat in graph)
            raise ValueError(f"Cyclic builder dependencies detected: {cycle}")

        return ordered
