"""Typed operations use the same dependency injection and ownership as other elements."""

from collections.abc import Iterable

from pydantic import BaseModel

from flareward.elements.categories.category_builder import CategoryBuilder
from flareward.elements.construction.collections import ResourceCollections
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.domain.construction import ResourceSpec


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
