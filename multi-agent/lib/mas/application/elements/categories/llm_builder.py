from collections.abc import Iterable
from typing import Any

from mas.application.elements.categories.category_builder import (
    CategoryBuilder,
    ResourceCollections,
)
from mas.core.enums import ResourceCategory


class LLMBuilder(CategoryBuilder):
    category = ResourceCategory.LLM

    def _iter_specs(self, blueprint: ResourceCollections) -> Iterable[Any]:
        return blueprint.llms
