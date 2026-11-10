"""Unsupported transaction storage must fail closed without partial publication."""

import pytest
from support.builtins import curated_record

from lumora.resources.adapters.mongo.builtin_administration import MongoBuiltinAdministration
from lumora.resources.errors import ResourceStorageError


async def test_standalone_mongo_never_falls_back_to_partial_writes(mongo_database):
    assert not (await mongo_database.client.admin.command("hello")).get("setName"), (
        "Select the standalone Lumora Mongo service for this refusal test"
    )
    store = MongoBuiltinAdministration(
        mongo_database, resources="resources", descriptors="descriptors", blueprints="blueprints"
    )
    with pytest.raises(ResourceStorageError, match="^Resource storage is unavailable$"):
        await store.commit((), (curated_record("root", public=True),))
    assert await mongo_database.resources.count_documents({}) == 0
    assert await mongo_database.descriptors.count_documents({}) == 0
