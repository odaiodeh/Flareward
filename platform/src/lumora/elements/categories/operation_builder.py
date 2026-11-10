"""Typed operations use the same dependency injection and ownership as other elements."""

from collections.abc import Iterable

from pydantic import BaseModel

from lumora.elements.categories.category_builder import CategoryBuilder
from lumora.elements.construction.collections import ResourceCollections
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.domain.construction import ResourceSpec


class OperationBuilder(CategoryBuilder):
    category = ResourceCategory.OPERATION
    depends_on = (
        ResourceCategory.LLM,
        ResourceCategory.TOOL,
        ResourceCategory.PROVIDER,
        ResourceCategory.RETRIEVER,
    )

    def _iter_specs(self, blueprint: ResourceCollections) -> Iterable[ResourceSpec[BaseModel]]:
        return blueprint.operations
