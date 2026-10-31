from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, ClassVar

from pydantic import ValidationError

from mas.application.elements.construction.collections import ResourceCollections
from mas.application.elements.construction.references import references, resolve_reference_value
from mas.application.elements.exceptions import PluginConfigurationError
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.core.contracts import ElementInstances
from mas.core.element_deps import ElementBuildContext
from mas.core.enums import ResourceCategory
from mas.core.resource_models import ResourceSpec


class CategoryBuilder(ABC):
    """SRP: one concrete subclass per resource category."""

    # must be overridden
    category: ClassVar[ResourceCategory]
    depends_on: ClassVar[tuple[ResourceCategory, ...]] = ()

    def __init__(self, registry_elements) -> None:
        self._registry_elements = registry_elements

    def build(
        self,
        blueprint: ResourceCollections,
        registry: ElementInstances,
        deps: ElementBuildContext | None = None,
    ) -> None:
        for resource in self._iter_specs(blueprint):
            self.build_resource(resource, registry, deps=deps)

    def build_resource(
        self,
        resource: ResourceSpec,
        registry: ElementInstances,
        deps: ElementBuildContext | None = None,
    ) -> Any:
        """Construct one resource; caller controls dependency order and lifetime."""
        spec = self._registry_elements.get_spec(self.category, resource.type)
        instance = self._create_instance(resource, registry, deps=deps)
        self._register(registry, resource.rid.ref, instance, spec, resource)
        return instance

    # -------- protected helpers ----------------------------------------

    @abstractmethod
    def _iter_specs(self, blueprint: ResourceCollections) -> Iterable[ResourceSpec]: ...

    def _register(self, registry, name: str, inst: Any, spec: Any, resource_spec: Any):
        registry.register(self.category, name, inst, spec, resource_spec)

    def _resolve_auth_credential(
        self,
        cfg: Any,
        deps: ElementBuildContext | None,
    ) -> Any:
        """
        Bind a lazy OAuth credential when cfg names a registry auth server.

        Static dropdown values (none / access_token) must not bind.
        Returns the credential or None.
        """
        server_id = (getattr(cfg, "server_identifier", "") or "").rstrip("/")
        scheme_type = getattr(cfg, "scheme_type", "") or ""
        if (
            not server_id
            or server_id in StaticAuthMethod.values()
            or not deps
            or not deps.auth_service
        ):
            return None

        ctx_holder = getattr(deps, "execution_ctx", None)
        if not ctx_holder:
            return None

        def resolver(_h=ctx_holder) -> str:
            return _h.context.credential_user_id()

        return deps.auth_service.bind_lazy(resolver, server_id, scheme_type)

    # ––– shared factory construction with error handling ––––––––––––––
    def _create_instance(
        self,
        resource_spec: ResourceSpec,
        session_registry: ElementInstances,
        deps: ElementBuildContext | None = None,
    ) -> Any:
        """Lookup factory, validate schema, create instance with extras."""
        try:
            factory_cls = self._registry_elements.get_factory_class(
                self.category, resource_spec.type
            )
            schema_cls = self._registry_elements.get_schema(self.category, resource_spec.type)
        except KeyError as e:
            raise PluginConfigurationError(
                f"No plugin for {self.category!r} type={resource_spec.type!r}",
                resource_spec.config.model_dump(),
            ) from e

        raw = resource_spec.config.model_dump(exclude_unset=True)
        try:
            validated = schema_cls(**raw) if schema_cls else raw
        except ValidationError as ve:
            raise PluginConfigurationError(
                f"Config validation failed for {self.category}/{resource_spec.type}: {ve}", raw
            ) from ve

        factory = factory_cls()
        if not factory.accepts(cfg=validated, element_type=resource_spec.type):
            raise PluginConfigurationError(
                f"{factory_cls.__name__} rejects element type {resource_spec.type!r}",
                validated,
            )

        try:
            extra = self._extra_kwargs(resource_spec.config, session_registry, deps=deps)
            return factory.create(validated, deps=deps, **extra)
        except Exception as e:
            raise PluginConfigurationError(
                f"{factory_cls.__name__}.create() failed: {e}", validated
            ) from e

    # subclasses may override
    def _extra_kwargs(
        self,
        cfg,
        session_registry: ElementInstances,
        deps: ElementBuildContext | None = None,
    ) -> dict[str, Any]:
        return {
            name: resolve_reference_value(getattr(cfg, name), session_registry)
            for name in type(cfg).model_fields
            if any(references(getattr(cfg, name)))
        }
