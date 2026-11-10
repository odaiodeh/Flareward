"""Source races, closure ownership and explicit adoption without an execution engine."""

from unittest.mock import AsyncMock

import pytest
from support.construction_values import dependency_chain
from support.resource_snapshots import MemoryResourceSources
from support.secrets import MemorySecretStore

from lumora.elements.construction.resolver import ElementBundleResolver
from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.elements.construction.snapshots import (
    ResourceAdoption,
    ResourceSelection,
    ResourceSnapshotConflict,
    ResourceSnapshotSource,
    SavedResourceResolver,
)
from lumora.resources.domain.bundles import ResourceDefinition, ResourceKey
from lumora.services.identity.domain import Identity


@pytest.fixture
def snapshots(application):
    source = MemoryResourceSources(application.owner)
    secrets = ConfigurationSecrets(application.elements, MemorySecretStore())
    resolver = SavedResourceResolver(source, application.elements, secrets)
    root = ResourceKey(category="operations", rid="work")
    return source, resolver, ResourceSelection(source=source.reference(root))


async def test_saved_selection_resolves_complete_typed_closure_and_detaches_readers(
    application, snapshots
):
    source, resolver, selection = snapshots
    result = await resolver.materialize((), (selection,), application.owner)
    bundle = ElementBundleResolver(application.elements).resolve(selection.source.key, result)
    assert [entry.resource.key.rid for entry in bundle.entries] == ["leaf", "middle", "work"]
    result[0].config["prefix"] = "reader edit"
    assert "prefix" not in source.resources[selection.source.key].config
    with pytest.raises(KeyError):
        await resolver.materialize((), (selection,), Identity.team(application.owner.id))


async def test_exported_bundle_reuses_authorized_closure_and_rejects_stale_sources(
    application, snapshots
):
    source, resolver, selection = snapshots
    bundle = await resolver.bundle(selection, application.owner)
    assert {entry.resource.key.rid for entry in bundle.entries} == {"work", "middle", "leaf"}
    source.versions[selection.source.key] += 1
    with pytest.raises(ResourceSnapshotConflict):
        await resolver.bundle(selection, application.owner)
    with pytest.raises(KeyError):
        await resolver.bundle(selection, Identity.team(application.owner.id))


async def test_bundle_export_never_returns_plaintext_configuration_credentials(application):
    resource = ResourceDefinition(
        key=ResourceKey(category="tools", rid="secret"),
        type_key="platform_secret_tool",
        config={"api_key": "private-bundle-value"},
    )
    source = MemoryResourceSources(application.owner, (resource,))
    store = MemorySecretStore()
    resolver = SavedResourceResolver(
        source, application.elements, ConfigurationSecrets(application.elements, store)
    )
    bundle = await resolver.bundle(
        ResourceSelection(source=source.reference(resource.key)), application.owner
    )
    assert "private-bundle-value" not in bundle.model_dump_json() and len(store._values) == 1


async def test_stale_selection_and_dependency_change_are_rejected(application, snapshots):
    source, resolver, selection = snapshots
    source.versions[selection.source.key] += 1
    with pytest.raises(ResourceSnapshotConflict, match="changed"):
        await resolver.materialize((), (selection,), application.owner)
    selection = ResourceSelection(source=source.reference(selection.source.key))
    port = AsyncMock(spec=ResourceSnapshotSource)
    reads = 0

    async def changing(key, caller):
        nonlocal reads
        reads += 1
        if reads == 4:
            source.versions[ResourceKey(category="tools", rid="middle")] += 1
        return await source.resolve_source(key, caller)

    port.resolve_source.side_effect = changing
    racing = SavedResourceResolver(
        port, application.elements, ConfigurationSecrets(application.elements, None)
    )
    with pytest.raises(ResourceSnapshotConflict, match="dependencies changed"):
        await racing.materialize((), (selection,), application.owner)


async def test_conflicting_shared_dependency_requires_explicit_adoption(application, snapshots):
    source, resolver, selection = snapshots
    original = await resolver.materialize((), (selection,), application.owner)
    middle = ResourceKey(category="tools", rid="middle")
    source.resources[middle] = source.resources[middle].model_copy(
        update={"config": {"value": "new", "dependency": "$ref:leaf"}}
    )
    source.versions[middle] += 1
    with pytest.raises(ResourceSnapshotConflict, match="all uses"):
        await resolver.materialize(original, (selection,), application.owner)
    updated = await resolver.materialize(
        original,
        (selection.model_copy(update={"adoption": ResourceAdoption.REPLACE}),),
        application.owner,
    )
    assert next(value for value in updated if value.key == middle).config["value"] == "new"
    assert next(value for value in original if value.key == middle).config["value"] == "middle"


async def test_unchanged_secret_snapshot_reuses_opaque_reference(application):
    resource = ResourceDefinition(
        key=ResourceKey(category="tools", rid="secret"),
        type_key="platform_secret_tool",
        config={"api_key": "private-value"},
    )
    source = MemoryResourceSources(application.owner, (resource,))
    store = MemorySecretStore()
    configuration = ConfigurationSecrets(application.elements, store)
    resolver = SavedResourceResolver(source, application.elements, configuration)
    protected = await configuration.protect_resource(resource, application.owner)
    result = await resolver.materialize(
        (protected,), (ResourceSelection(source=source.reference(resource.key)),), application.owner
    )
    assert result == (protected,) and len(store._values) == 1
    assert "private-value" not in result[0].model_dump_json()


async def test_cycles_and_repeated_roots_fail_through_shared_construction_contract(
    application, snapshots
):
    source, resolver, selection = snapshots
    with pytest.raises(ValueError, match="only once"):
        await resolver.materialize((), (selection, selection), application.owner)
    leaf = ResourceKey(category="tools", rid="leaf")
    source.resources[leaf] = source.resources[leaf].model_copy(
        update={"config": {"dependency": "$ref:middle"}}
    )
    with pytest.raises(ValueError, match="cycle"):
        await resolver.materialize((), (selection,), application.owner)


def test_deep_construction_resolution_preserves_dependency_order(application):
    resources = dependency_chain(1200)
    bundle = ElementBundleResolver(application.elements).resolve(resources[0].key, resources)
    assert [entry.resource.key for entry in bundle.entries] == [
        resource.key for resource in reversed(resources)
    ]


async def test_selecting_every_resource_as_a_root_does_not_bypass_depth_limit(application):
    source = MemoryResourceSources(application.owner, dependency_chain(70))
    resolver = SavedResourceResolver(
        source, application.elements, ConfigurationSecrets(application.elements, None)
    )
    selections = tuple(ResourceSelection(source=source.reference(key)) for key in source.resources)
    with pytest.raises(ValueError, match="depth"):
        await resolver.materialize((), selections, application.owner)
