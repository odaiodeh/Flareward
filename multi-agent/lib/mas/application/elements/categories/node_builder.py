"""Node construction reuses common typed dependency injection and auth binding."""

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from mas.application.elements.categories.category_builder import CategoryBuilder
from mas.application.elements.construction.collections import ResourceCollections
from mas.core.contracts import ElementInstances
from mas.core.element_deps import ElementBuildContext
from mas.core.enums import ResourceCategory
from mas.core.resource_models import ResourceSpec


class NodeBuilder(CategoryBuilder):
    category = ResourceCategory.NODE
    depends_on = {
        ResourceCategory.TOOL,
        ResourceCategory.LLM,
        ResourceCategory.RETRIEVER,
        ResourceCategory.PROVIDER,
    }

    def _iter_specs(self, blueprint: ResourceCollections) -> Iterable[ResourceSpec]:
        return blueprint.nodes

    def _extra_kwargs(
        self,
        cfg: BaseModel,
        registry: ElementInstances,
        deps: ElementBuildContext | None = None,
    ) -> dict[str, Any]:
        kwargs = super()._extra_kwargs(cfg, registry, deps)
        credential = self._resolve_auth_credential(cfg, deps)
        if credential is not None:
            kwargs["auth_credential"] = credential
        return kwargs
