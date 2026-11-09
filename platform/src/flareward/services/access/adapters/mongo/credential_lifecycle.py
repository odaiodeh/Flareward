"""Bounded grant discovery and expiry fences; purpose services own authority."""

from datetime import datetime
from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError, PyMongoError

from flareward.services.access.domain.leases import CredentialLease


class MongoCredentialLifecycle:
    def __init__(self, collection: AsyncCollection[dict[str, Any]]) -> None:
        self._collection = collection

    @staticmethod
    def metadata(expires_at: datetime, renewal: CredentialLease | None) -> dict[str, Any]:
        return {
            "expires_at": expires_at.timestamp(),
            "renewable_until": renewal.renewable_until.timestamp() if renewal else None,
            "renewable": renewal is not None and expires_at < renewal.renewable_until,
        }

    async def initialize(self) -> None:
        await self._collection.create_index([("revoked", 1), ("_id", 1)])

    async def ensure(self, document: dict[str, Any]) -> dict[str, Any]:
        try:
            stored = await self._collection.find_one_and_update(
                {"_id": document["_id"]},
                {"$setOnInsert": document},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            stored = await self._collection.find_one({"_id": document["_id"]})
        if stored is None:
            raise PyMongoError("Credential grant registration is unobservable")
        return stored

    async def pending(self, *, after: str, limit: int) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("Credential maintenance page size must be between 1 and 100")
        cursor = (
            self._collection.find(
                {
                    "revoked": False,
                    "_id": {"$gt": after},
                }
            )
            .sort("_id", 1)
            .limit(limit)
        )
        return [document async for document in cursor]

    async def expire(self, grant_id: str, expected_expiry: datetime, *, now: datetime) -> bool:
        if expected_expiry > now:
            return False
        result = await self._collection.update_one(
            {
                "_id": grant_id,
                "revoked": False,
                "expires_at": {"$eq": expected_expiry.timestamp(), "$lte": now.timestamp()},
                "$expr": {"$lte": [{"$multiply": ["$expires_at", 1000]}, {"$toLong": "$$NOW"}]},
            },
            {"$set": {"revoked": True}},
        )
        return result.modified_count == 1

    async def renew(
        self,
        document: dict[str, Any],
        updated: str,
        expected_expiry: datetime,
        expires_at: datetime,
        *,
        now: datetime,
        renewal: CredentialLease,
    ) -> bool:
        if expires_at <= expected_expiry or now >= expected_expiry:
            return False
        result = await self._collection.update_one(
            {
                "_id": document["_id"],
                "data": document["data"],
                "revoked": False,
                "renewable": True,
                "expires_at": {"$eq": expected_expiry.timestamp(), "$gt": now.timestamp()},
                "renewable_until": {"$gte": expires_at.timestamp()},
                "$expr": {"$gt": [{"$multiply": ["$expires_at", 1000]}, {"$toLong": "$$NOW"}]},
            },
            {"$set": {"data": updated, **self.metadata(expires_at, renewal)}},
        )
        return result.modified_count == 1
