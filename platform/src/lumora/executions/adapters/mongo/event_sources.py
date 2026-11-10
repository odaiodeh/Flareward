"""Private immutable source registrations, hash-only delivery keys and one-way revocation."""

from datetime import datetime
from typing import Any

from pydantic import ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError
from pymongo.write_concern import WriteConcern

from lumora.executions.domain.events import ProgramEventSource
from lumora.executions.events import (
    EventSourceConflict,
    EventSourceUnavailable,
    StoredEventSource,
)
from lumora.services.identity.domain import Identity


class MongoEventSources:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.get_collection(
            "program_event_sources", write_concern=WriteConcern(w="majority")
        )

    async def initialize(self) -> None:
        try:
            await self._collection.create_index([("owner_type", 1), ("owner_id", 1), ("_id", 1)])
        except PyMongoError:
            raise EventSourceUnavailable("Event source storage is unavailable") from None

    async def create(self, registration: StoredEventSource) -> None:
        source = registration.definition
        try:
            await self._collection.insert_one(
                {
                    "_id": source.source_id,
                    "owner_type": source.owner.type.value,
                    "owner_id": source.owner.id,
                    "expires_at": source.expires_at.timestamp(),
                    "revoked": source.revoked,
                    "credential_revision": registration.credential_revision,
                    "data": registration.model_dump_json(),
                }
            )
        except PyMongoError:
            raise EventSourceUnavailable("Event source registration is unconfirmed") from None

    @staticmethod
    def _registration(row: dict[str, Any]) -> StoredEventSource:
        try:
            registration = StoredEventSource.model_validate_json(row["data"])
            source = registration.definition
            if (
                source.source_id != row["_id"]
                or (source.owner.type.value, source.owner.id)
                != (row["owner_type"], row["owner_id"])
                or source.expires_at.timestamp() != row["expires_at"]
                or not isinstance(row["revoked"], bool)
                or type(row["credential_revision"]) is not int
                or registration.credential_revision != row["credential_revision"]
            ):
                raise EventSourceUnavailable()
            return registration.model_copy(
                update={"definition": source.model_copy(update={"revoked": row["revoked"]})}
            )
        except ValidationError, KeyError, TypeError:
            raise EventSourceUnavailable("Event source storage is invalid") from None

    async def get(
        self, source_id: str, owner: Identity | None = None, *, active_at: datetime | None = None
    ) -> StoredEventSource:
        query: dict[str, Any] = {"_id": source_id}
        if owner is not None:
            query.update({"owner_type": owner.type.value, "owner_id": owner.id})
        if active_at is not None:
            query.update(
                {
                    "revoked": False,
                    "expires_at": {"$gt": active_at.timestamp()},
                    "$expr": {"$gt": [{"$multiply": ["$expires_at", 1000]}, {"$toLong": "$$NOW"}]},
                }
            )
        try:
            row = await self._collection.find_one(query)
        except PyMongoError:
            raise EventSourceUnavailable("Event source storage is unavailable") from None
        if row is None:
            raise KeyError(source_id)
        return self._registration(row)

    async def list(self, owner: Identity, *, after: str, limit: int) -> list[ProgramEventSource]:
        if not 1 <= limit <= 100:
            raise ValueError("Event source page size must be between 1 and 100")
        try:
            cursor = (
                self._collection.find(
                    {"owner_type": owner.type.value, "owner_id": owner.id, "_id": {"$gt": after}}
                )
                .sort("_id", 1)
                .limit(limit)
            )
            return [self._registration(row).definition async for row in cursor]
        except PyMongoError:
            raise EventSourceUnavailable("Event source storage is unavailable") from None

    async def revoke(self, source_id: str, owner: Identity) -> None:
        try:
            result = await self._collection.update_one(
                {"_id": source_id, "owner_type": owner.type.value, "owner_id": owner.id},
                {"$set": {"revoked": True}},
            )
        except PyMongoError:
            raise EventSourceUnavailable("Event source revocation is unconfirmed") from None
        if not result.matched_count:
            raise KeyError(source_id)

    async def rotate(
        self, source_id: str, owner: Identity, expected_revision: int, digest: str, *, now: datetime
    ) -> None:
        registration = await self.get(source_id, owner, active_at=now)
        if registration.credential_revision != expected_revision:
            raise EventSourceConflict("Event source credential revision is stale")
        updated = registration.model_copy(
            update={"secret_sha256": digest, "credential_revision": expected_revision + 1}
        )
        try:
            result = await self._collection.update_one(
                {
                    "_id": source_id,
                    "owner_type": owner.type.value,
                    "owner_id": owner.id,
                    "revoked": False,
                    "credential_revision": expected_revision,
                    "expires_at": {"$gt": now.timestamp()},
                    "$expr": {"$gt": [{"$multiply": ["$expires_at", 1000]}, {"$toLong": "$$NOW"}]},
                },
                {
                    "$set": {
                        "credential_revision": expected_revision + 1,
                        "data": updated.model_dump_json(),
                    }
                },
            )
        except PyMongoError:
            raise EventSourceUnavailable("Event source rotation is unconfirmed") from None
        if not result.matched_count:
            raise EventSourceConflict("Event source changed or is no longer active")
