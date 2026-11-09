"""Async configuration persistence; compare-and-swap edits never overwrite stale values."""

from typing import Any

from pydantic import ValidationError
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError, PyMongoError

from flareward.services.administration.contracts import SettingsRecord, SettingsUnavailable


class MongoSettingsRepository:
    def __init__(self, collection: AsyncCollection[dict[str, Any]]) -> None:
        self._collection = collection

    async def initialize(self) -> None:
        try:
            await self._collection.create_index("key", unique=True)
        except PyMongoError:
            raise SettingsUnavailable("Configuration storage is unavailable") from None

    async def get(self, key: str) -> SettingsRecord | None:
        try:
            row = await self._collection.find_one({"key": key}, {"_id": 0})
            return SettingsRecord.model_validate(row) if row else None
        except PyMongoError, ValidationError:
            raise SettingsUnavailable("Configuration storage is unavailable") from None

    async def replace(self, record: SettingsRecord, expected_revision: int) -> bool:
        try:
            outcome = await self._collection.update_one(
                {"key": record.key, "revision": expected_revision},
                {"$set": record.model_dump()},
                upsert=expected_revision == 0,
            )
            return outcome.modified_count == 1 or outcome.upserted_id is not None
        except DuplicateKeyError:
            return False
        except PyMongoError:
            raise SettingsUnavailable("Configuration storage is unavailable") from None
