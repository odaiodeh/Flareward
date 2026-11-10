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

from lumora.elements.categories.category_builder import CategoryBuilder
from lumora.elements.categories.condition_builder import ConditionBuilder
from lumora.elements.categories.llm_builder import LLMBuilder
from lumora.elements.categories.node_builder import NodeBuilder
from lumora.elements.categories.operation_builder import OperationBuilder

# concrete builders
from lumora.elements.categories.provider_builder import ProviderBuilder
from lumora.elements.categories.retriever_builder import RetrieverBuilder
from lumora.elements.categories.tool_builder import ToolBuilder
from lumora.resources.domain.categories import ResourceCategory


class CategoryBuilders:
    """Construct category strategies; resource references determine build order."""

    _BUILDER_CLASSES: tuple[type[CategoryBuilder], ...] = (
        ProviderBuilder,
        LLMBuilder,
        RetrieverBuilder,
        ConditionBuilder,
        ToolBuilder,
        NodeBuilder,
        OperationBuilder,
    )

    def __init__(self, element_registry) -> None:
        self._builders = {cls.category: cls(element_registry) for cls in self._BUILDER_CLASSES}

    @property
    def resource_builders(self) -> dict[ResourceCategory, CategoryBuilder]:
        return dict(self._builders)
