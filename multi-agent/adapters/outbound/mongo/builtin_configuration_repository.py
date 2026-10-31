"""Atomic owner-scoped overlays share the retained built-in configuration collection."""

from mas.resources.builtin_models import BuiltinUserConfig
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError

from outbound.mongo.resource_authoring_repository import storage_errors


class MongoBuiltinConfigurationRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._collection = collection

    async def initialize(self) -> None:
        async with storage_errors():
            await self._collection.create_index(
                [("resource_id", 1), ("identity_key", 1)], unique=True, name="uq_resource_identity"
            )

    async def get(self, rid: str, identity_key: str) -> BuiltinUserConfig | None:
        async with storage_errors():
            row = await self._collection.find_one(
                {"resource_id": rid, "identity_key": identity_key}
            )
        return BuiltinUserConfig.model_validate(row) if row else None

    async def list(self, identity_key: str) -> list[BuiltinUserConfig]:
        async with storage_errors():
            return [
                BuiltinUserConfig.model_validate(row)
                async for row in self._collection.find({"identity_key": identity_key})
            ]

    async def replace(self, previous: BuiltinUserConfig | None, updated: BuiltinUserConfig) -> bool:
        async with storage_errors():
            if previous is None:
                try:
                    await self._collection.insert_one(
                        {"_id": updated.config_id, **updated.model_dump(mode="json")}
                    )
                except DuplicateKeyError:
                    return False
                return True
            result = await self._collection.replace_one(
                self._unchanged(previous), updated.model_dump(mode="json")
            )
        return result.matched_count == 1

    @staticmethod
    def _unchanged(previous: BuiltinUserConfig) -> dict:
        return {
            "_id": previous.config_id,
            "resource_id": previous.resource_id,
            "identity_key": previous.identity_key,
            "fields": previous.fields,
            "version": {"$in": [None, 0]} if previous.version == 0 else previous.version,
        }
