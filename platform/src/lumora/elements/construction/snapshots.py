"""Materialize authorized saved resources through the existing construction contracts."""

from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.construction.references import references
from lumora.elements.construction.resolver import ElementBundleResolver
from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.resources.domain.bundles import (
    ElementBundle,
    ResourceDefinition,
    ResourceKey,
    ResourceSourceRef,
)
from lumora.resources.secrets import authored_configuration
from lumora.services.identity.domain import Identity


class ResourceAdoption(StrEnum):
    REJECT = "reject"
    REPLACE = "replace"


class ResourceSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source: ResourceSourceRef
    adoption: ResourceAdoption = ResourceAdoption.REJECT


@dataclass(frozen=True, repr=False)
class SourcedResource:
    """Server-local authored values; private configuration must be protected before export."""

    reference: ResourceSourceRef
    definition: ResourceDefinition


class ResourceSnapshotSource(Protocol):
    async def resolve_source(self, key: ResourceKey, caller: Identity) -> SourcedResource: ...


class ResourceSnapshotConflict(ValueError):
    """A selected source changed or would replace an existing frozen configuration."""


class ResourceSnapshotsUnavailable(RuntimeError):
    """Saved-resource selection requires a configured resource library."""


class SavedResourceResolver:
    def __init__(
        self,
        source: ResourceSnapshotSource,
        elements: ElementRegistry,
        configuration: ConfigurationSecrets,
    ) -> None:
        self._source, self._elements, self._configuration = source, elements, configuration
        self._bundles = ElementBundleResolver(elements)

    async def bundle(
        self,
        selection: ResourceSelection,
        caller: Identity,
        *,
        existing: ElementBundle | None = None,
    ) -> ElementBundle:
        if (
            existing is not None
            and existing.root != selection.source.key
            and selection.adoption != ResourceAdoption.REPLACE
        ):
            raise ResourceSnapshotConflict(
                "Changing a captured resource requires explicit replacement"
            )
        resources = await self.materialize(
            tuple(entry.resource for entry in existing.entries) if existing else (),
            (selection,),
            caller,
        )
        protected = tuple(
            [await self._configuration.protect_resource(resource, caller) for resource in resources]
        )
        return self._bundles.resolve(selection.source.key, protected)

    async def materialize(
        self,
        existing: tuple[ResourceDefinition, ...],
        selections: tuple[ResourceSelection, ...],
        caller: Identity,
    ) -> tuple[ResourceDefinition, ...]:
        roots = {selection.source.key: selection for selection in selections}
        if len(roots) != len(selections):
            raise ValueError("Select each saved resource only once")
        captured: dict[ResourceKey, SourcedResource] = {}
        dependencies: dict[ResourceKey, tuple[ResourceKey, ...]] = {}
        pending = deque((key, 0) for key in roots)
        while pending:
            key, depth = pending.popleft()
            if key in captured:
                continue
            if len(captured) >= 1000 or depth > 64:
                raise ValueError("Saved-resource dependency closure exceeds its bounds")
            value = await self._source.resolve_source(key, caller)
            if value.reference.key != key or value.definition.key != key:
                raise ValueError("Saved-resource source returned a different identity")
            model = self._model(value.definition)
            captured[key] = SourcedResource(
                value.reference,
                value.definition.model_copy(
                    update={"config": authored_configuration(model)}, deep=True
                ),
            )
            dependencies[key] = tuple(
                sorted(set(references(model)), key=lambda ref: (ref.category, ref.rid))
            )
            pending.extend((dependency, depth + 1) for dependency in dependencies[key])
        for key, selection in roots.items():
            if captured[key].reference != selection.source:
                raise ResourceSnapshotConflict("Saved resource changed; reload before selecting it")
            self._bundles.validate(
                key, (value.definition for value in captured.values()), max_depth=64
            )
        # With monotonic source revisions, unchanged rereads establish one captured closure.
        # Reauthorize every dependency before protecting or persisting any private value.
        for key, value in captured.items():
            current = await self._source.resolve_source(key, caller)
            if current.reference != value.reference:
                raise ResourceSnapshotConflict(
                    "Saved-resource dependencies changed; retry selection"
                )
        replacements: set[ResourceKey] = set()
        for key, selection in roots.items():
            if selection.adoption == ResourceAdoption.REPLACE:
                pending_keys = [key]
                while pending_keys:
                    dependency = pending_keys.pop()
                    if dependency not in replacements:
                        replacements.add(dependency)
                        pending_keys.extend(dependencies[dependency])
        merged = {resource.key: resource for resource in existing}
        if len(merged) != len(existing):
            raise ValueError("Program resource snapshots must have unique identities")
        for key, value in captured.items():
            previous = merged.get(key)
            if previous is not None:
                raw = await self._configuration.resolve_authored(self._model(previous), caller)
                if previous.model_copy(update={"config": raw}) == value.definition:
                    continue
                if key not in replacements:
                    raise ResourceSnapshotConflict(
                        "Selection changes a resource snapshot; explicitly replace all uses"
                    )
            merged[key] = value.definition
        return tuple(merged.values())

    def _model(self, resource: ResourceDefinition) -> BaseModel:
        try:
            return self._elements.get_schema(
                resource.key.category, resource.type_key
            ).model_validate(resource.config, by_name=True)
        except ValidationError:
            raise ValueError("Invalid saved-resource configuration") from None
