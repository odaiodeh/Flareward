"""Resolve one resource's transitive construction closure from an authorized snapshot."""

from collections.abc import Iterable

from pydantic import BaseModel

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.references import references
from mas.core.secrets import protected_configuration
from mas.domain.element_bundles import BundleEntry, ElementBundle, ResourceDefinition, ResourceKey


class BundleResolutionError(ValueError):
    """The resource snapshot cannot construct the requested element."""


class ElementBundleResolver:
    def __init__(self, registry: ElementRegistry) -> None:
        self._registry = registry

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

    def validate(self, root: ResourceKey, resources: Iterable[ResourceDefinition]) -> None:
        """Validate construction locally without exporting a portable credential-bearing bundle."""
        self._ordered(root, resources)

    def _ordered(
        self, root: ResourceKey, resources: Iterable[ResourceDefinition]
    ) -> list[tuple[ResourceDefinition, BaseModel, tuple[ResourceKey, ...]]]:
        definitions: dict[ResourceKey, ResourceDefinition] = {}
        for resource in resources:
            if resource.key in definitions:
                raise BundleResolutionError(f"Duplicate resource: {resource.key}")
            definitions[resource.key] = resource
        entries: list[tuple[ResourceDefinition, BaseModel, tuple[ResourceKey, ...]]] = []
        complete: set[ResourceKey] = set()
        path: list[ResourceKey] = []

        def visit(key: ResourceKey) -> None:
            if key in complete:
                return
            if key in path:
                chain = " -> ".join(f"{item.category.value}/{item.rid}" for item in [*path, key])
                raise BundleResolutionError(f"Construction dependency cycle: {chain}")
            if key not in definitions:
                raise BundleResolutionError(f"Missing resource: {key.category.value}/{key.rid}")
            resource = definitions[key]
            spec = self._registry.get_spec(key.category, resource.type_key)
            if spec.version != resource.implementation_version:
                raise BundleResolutionError(f"Incompatible implementation version: {key}")
            config = spec.config_schema.model_validate(resource.config, by_name=True)
            dependencies = tuple(
                sorted(set(references(config)), key=lambda item: (item.category, item.rid))
            )
            path.append(key)
            for dependency in dependencies:
                visit(dependency)
            path.pop()
            entries.append((resource, config, dependencies))
            complete.add(key)

        visit(root)
        return entries
