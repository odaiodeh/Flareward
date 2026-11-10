from collections.abc import Iterable
from typing import Any

from lumora.elements.categories.category_builder import (
    CategoryBuilder,
    ResourceCollections,
)
from lumora.elements.construction.context import ElementBuildContext
from lumora.elements.instance_ports import ElementInstances
from lumora.resources.domain.categories import ResourceCategory


class ProviderBuilder(CategoryBuilder):
    category = ResourceCategory.PROVIDER

    def _iter_specs(self, blueprint: ResourceCollections) -> Iterable[Any]:
        return blueprint.providers

    def _extra_kwargs(
        self,
        cfg: Any,
        session_registry: ElementInstances,
        deps: ElementBuildContext | None = None,
    ) -> dict[str, Any]:
        cred = self._resolve_auth_credential(cfg, deps)
        kwargs = super()._extra_kwargs(cfg, session_registry, deps)
        if cred:
            kwargs["auth_credential"] = cred
        return kwargs
