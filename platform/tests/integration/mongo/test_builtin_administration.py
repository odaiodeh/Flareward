"""Actual Mongo transactions prove atomic publication, rollback and competing catalog changes."""

import asyncio

import pytest
from support.builtins import chain, curated_record

from flareward.resources.adapters.mongo.builtin_administration import MongoBuiltinAdministration
from flareward.resources.adapters.mongo.resource_authoring_repository import (
    MongoResourceAuthoringRepository,
)
from flareward.resources.errors import ResourceConflictError, ResourceDuplicateNameError


async def repository(database):
    hello = await database.client.admin.command("hello")
    assert hello.get("setName"), "Select Flareward's transaction-capable Mongo test service"
    resources = MongoResourceAuthoringRepository(
        database,
        resources="resources",
        descriptors="builtin_resource_descriptors",
        blueprints="blueprints",
    )
    await resources.initialize()
    store = MongoBuiltinAdministration(
        database,
        resources="resources",
        descriptors="builtin_resource_descriptors",
        blueprints="blueprints",
    )
    for entry in chain():
        await store.commit((), (entry,))
    return store


async def test_atomic_batch_rollback_preserves_previous_visibility_and_absent_root(
    transaction_database,
):
    store = await repository(transaction_database)
    previous = await store.get("middle")
    promoted = previous.model_copy(deep=True)
    promoted.descriptor = curated_record("middle", public=True).descriptor
    conflict = curated_record("conflicting-id")
    conflict.resource.name = "leaf"  # Actual unique identity/category/type/name index failure.
    new = curated_record("new-root", public=True)
    with pytest.raises(ResourceDuplicateNameError):
        await store.commit((previous,), (new, promoted, conflict))
    assert (await store.get("middle")) == previous
    with pytest.raises(KeyError):
        await store.get("new-root")
    assert (
        await transaction_database.builtin_resource_descriptors.count_documents({"_id": "middle"})
        == 0
    )


async def test_competing_publication_and_demotion_cannot_both_commit_stale_views(
    transaction_database,
):
    store = await repository(transaction_database)
    leaf = await store.get("leaf")
    leaf_public = leaf.model_copy(deep=True)
    leaf_public.descriptor = curated_record("leaf", public=True).descriptor
    await store.commit((leaf,), (leaf_public,))
    leaf, parent = await store.get("leaf"), await store.get("middle")
    published_parent = parent.model_copy(deep=True)
    published_parent.descriptor = curated_record("middle", public=True).descriptor
    demoted_leaf = leaf.model_copy(deep=True)
    demoted_leaf.descriptor.visibility = "draft"
    results = await asyncio.gather(
        store.commit((parent, leaf), (published_parent,)),
        store.commit((leaf,), (demoted_leaf,)),
        return_exceptions=True,
    )
    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, ResourceConflictError) for result in results) == 1
    actual_parent, actual_leaf = await store.get("middle"), await store.get("leaf")
    if actual_parent.descriptor is not None and actual_parent.descriptor.visibility == "public":
        assert actual_leaf.descriptor.visibility == "public"


async def test_delete_atomically_removes_resource_descriptor_and_only_its_overlays(
    transaction_database,
):
    store = await repository(transaction_database)
    await transaction_database.builtin_user_configs.insert_many(
        [
            {"resource_id": "root", "fields": {"private": "fixture"}},
            {"resource_id": "other", "fields": {}},
        ]
    )
    previous = await store.get("root")
    await store.commit((previous,), (), ("root",))
    with pytest.raises(KeyError):
        await store.get("root")
    assert (
        await transaction_database.builtin_resource_descriptors.count_documents({"_id": "root"})
        == 0
    )
    assert await transaction_database.builtin_user_configs.count_documents({}) == 1
