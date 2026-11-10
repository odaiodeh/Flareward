"""Durable, versioned human consent; repeated acceptance is idempotent."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from lumora.services.identity.consent import ConsentUnavailable


class MongoConsents:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database["human_consents"]

    async def accepted(self, user: str, version: str) -> bool:
        try:
            return (
                await self._collection.find_one(
                    {"_id": hashlib.sha256(json.dumps([user, version]).encode()).hexdigest()}
                )
                is not None
            )
        except PyMongoError:
            raise ConsentUnavailable("Consent storage is unavailable") from None

    async def accept(self, user: str, version: str) -> None:
        try:
            await self._collection.update_one(
                {"_id": hashlib.sha256(json.dumps([user, version]).encode()).hexdigest()},
                {"$setOnInsert": {"accepted_at": datetime.now(UTC)}},
                upsert=True,
            )
        except PyMongoError:
            raise ConsentUnavailable("Consent storage is unavailable") from None
