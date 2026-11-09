"""Resolve one resource's transitive construction closure from an authorized snapshot."""

from collections.abc import Iterable

from pydantic import BaseModel

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.construction.references import references
from flareward.resources.domain.bundles import (
    BundleEntry,
    ElementBundle,
    ResourceDefinition,
    ResourceKey,
)
from flareward.resources.secrets import protected_configuration


class BundleResolutionError(ValueError):
    """The resource snapshot cannot construct the requested element."""


class ElementBundleResolver:
    def __init__(self, registry: ElementRegistry) -> None:
        self._registry = registry

    def validate_embedded(self, configuration: BaseModel) -> None:
        """Require complete registered construction inside a composed configuration."""
        pending: list[object] = [configuration]
        while pending:
            value = pending.pop()
            if isinstance(value, ElementBundle):
                resolved = self.resolve(value.root, (entry.resource for entry in value.entries))
                if resolved != value:
                    raise BundleResolutionError("Embedded construction snapshot is not canonical")
            elif isinstance(value, ResourceDefinition):
                schema = self._registry.get_schema(value.key.category, value.type_key)
                pending.append(schema.model_validate(value.config, by_name=True))
            elif isinstance(value, BaseModel):
                pending.extend(getattr(value, name) for name in type(value).model_fields)
            elif isinstance(value, dict):
                pending.extend(value.values())
            elif isinstance(value, (list, tuple)):
                pending.extend(value)

    def resolve(self, root: ResourceKey, resources: Iterable[ResourceDefinition]) -> ElementBundle:
        entries = tuple(
            BundleEntry(
                resource=resource.model_copy(
                    update={"config": protected_configuration(config)}, deep=True
                ),
                dependencies=dependencies,
            )
            for resource, config, dependencies in self._ordered(root, resources)
        )
        return ElementBundle(root=root, entries=entries)

    def validate(
        self,
        root: ResourceKey,
        resources: Iterable[ResourceDefinition],
        *,
        max_depth: int | None = None,
    ) -> None:
        """Validate construction locally without exporting a portable credential-bearing bundle."""
        self._ordered(root, resources, max_depth=max_depth)

    def validate_snapshot(self, resources: Iterable[ResourceDefinition]) -> None:
        """Validate every authored resource once, including unused draft entries."""
        snapshot = tuple(resources)
        self._ordered((resource.key for resource in snapshot), snapshot)

    def _ordered(
        self,
        root: ResourceKey | Iterable[ResourceKey],
        resources: Iterable[ResourceDefinition],
        *,
        max_depth: int | None = None,
    ) -> list[tuple[ResourceDefinition, BaseModel, tuple[ResourceKey, ...]]]:
        definitions: dict[ResourceKey, ResourceDefinition] = {}
        for resource in resources:
            if resource.key in definitions:
                raise BundleResolutionError(f"Duplicate resource: {resource.key}")
            definitions[resource.key] = resource
        entries: list[tuple[ResourceDefinition, BaseModel, tuple[ResourceKey, ...]]] = []
        complete: set[ResourceKey] = set()
        active: set[ResourceKey] = set()
        path: list[ResourceKey] = []
        prepared: dict[
            ResourceKey, tuple[ResourceDefinition, BaseModel, tuple[ResourceKey, ...]]
        ] = {}
        depths: dict[ResourceKey, int] = {}
        roots = (root,) if isinstance(root, ResourceKey) else root
        pending = [(key, False) for key in roots]
        while pending:
            key, returning = pending.pop()
            if returning:
                entry = prepared[key]
                depths[key] = max((depths[dependency] + 1 for dependency in entry[2]), default=0)
                path.pop()
                active.remove(key)
                if max_depth is not None and len(path) + depths[key] > max_depth:
                    raise BundleResolutionError("Construction dependency depth exceeds its bound")
                entries.append(entry)
                complete.add(key)
                continue
            if key in complete:
                if max_depth is not None and len(path) + depths[key] > max_depth:
                    raise BundleResolutionError("Construction dependency depth exceeds its bound")
                continue
            if key in active:
                chain = " -> ".join(f"{item.category.value}/{item.rid}" for item in [*path, key])
                raise BundleResolutionError(f"Construction dependency cycle: {chain}")
            if max_depth is not None and len(path) > max_depth:
                raise BundleResolutionError("Construction dependency depth exceeds its bound")
            if key not in definitions:
                raise BundleResolutionError(f"Missing resource: {key.category.value}/{key.rid}")
            resource = definitions[key]
            spec = self._registry.get_spec(key.category, resource.type_key)
            if spec.version != resource.implementation_version:
                raise BundleResolutionError(f"Incompatible implementation version: {key}")
            config = spec.config_schema.model_validate(resource.config, by_name=True)
            self.validate_embedded(config)
            dependencies = tuple(
                sorted(set(references(config)), key=lambda item: (item.category, item.rid))
            )
            path.append(key)
            active.add(key)
            prepared[key] = resource, config, dependencies
            pending.append((key, True))
            pending.extend((dependency, False) for dependency in reversed(dependencies))
        return entries
