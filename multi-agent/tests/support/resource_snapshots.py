"""Saved-resource scenarios share portable definitions and an application-owned source double."""

import hashlib

from mas.application.elements.construction.snapshots import SourcedResource
from mas.core.identity import Identity
from mas.domain.element_bundles import ResourceDefinition, ResourceKey, ResourceSourceRef

from support.operations import operation_graph, operation_resources


class MemoryResourceSources:
    def __init__(self, owner: Identity, resources: tuple[ResourceDefinition, ...] | None = None):
        self.owner = owner
        selected = operation_resources() if resources is None else resources
        self.resources = {resource.key: resource for resource in selected}
        self.versions = dict.fromkeys(self.resources, 1)

    def reference(self, key: ResourceKey) -> ResourceSourceRef:
        return ResourceSourceRef(
            key=key, revision=hashlib.sha256(str(self.versions[key]).encode()).hexdigest()
        )

    async def resolve_source(self, key: ResourceKey, caller: Identity) -> SourcedResource:
        if not caller.owns(self.owner):
            raise KeyError(key.rid)
        return SourcedResource(self.reference(key), self.resources[key].model_copy(deep=True))


def saved_resource_graph(profile: str = "thread"):
    return operation_graph(profile).model_copy(update={"resources": ()})
