from mas.application.elements.categories.category_builder import (
    CategoryBuilder,
    ResourceCollections,
)
from mas.core.enums import ResourceCategory


class ToolBuilder(CategoryBuilder):
    category = ResourceCategory.TOOL
    depends_on = (ResourceCategory.PROVIDER,)

    def _iter_specs(self, blueprint: ResourceCollections):
        return blueprint.tools
