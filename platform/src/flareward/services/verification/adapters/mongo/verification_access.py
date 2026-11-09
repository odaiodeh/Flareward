"""Persist workflow capabilities alongside verification state; retain only credential hashes."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError
from pymongo.write_concern import WriteConcern

from flareward.services.access.adapters.mongo.credential_lifecycle import MongoCredentialLifecycle
from flareward.services.identity.domain import Identity
from flareward.services.verification.access_models import StoredVerificationAccess
from flareward.services.verification.ports import VerificationStorageError


class MongoVerificationAccessRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.get_collection(
            "verification_access_grants", write_concern=WriteConcern(w="majority")
        )
        self._lifecycle = MongoCredentialLifecycle(self._collection)

    async def initialize(self) -> None:
        try:
            await self._collection.create_index([("owner_type", 1), ("owner_id", 1), ("_id", 1)])
            await self._lifecycle.initialize()
        except PyMongoError:
            raise VerificationStorageError("Verification access storage is unavailable") from None

    @staticmethod
    def _document(access: StoredVerificationAccess) -> dict[str, Any]:
        return {
            "_id": access.grant.grant_id,
            "owner_type": access.grant.owner.type.value,
            "owner_id": access.grant.owner.id,
            "data": access.model_dump_json(),
            "revoked": False,
            **MongoCredentialLifecycle.metadata(access.grant.expires_at, access.grant.renewal),
        }

    async def create(self, access: StoredVerificationAccess) -> None:
        try:
            await self._collection.insert_one(self._document(access))
        except PyMongoError:
            raise VerificationStorageError("Verification access storage is unavailable") from None

    async def ensure(self, access: StoredVerificationAccess) -> StoredVerificationAccess:
        try:
            return self._decode(await self._lifecycle.ensure(self._document(access)))
        except PyMongoError:
            raise VerificationStorageError("Verification access storage is unavailable") from None

    @staticmethod
    def _decode(document: dict[str, Any]) -> StoredVerificationAccess:
        try:
            stored = StoredVerificationAccess.model_validate_json(document["data"])
            if (
                stored.grant.grant_id != document["_id"]
                or stored.grant.owner.type.value != document["owner_type"]
                or stored.grant.owner.id != document["owner_id"]
                or not isinstance(document["revoked"], bool)
            ):
                raise VerificationStorageError("Verification access record identity is invalid")
            return stored.model_copy(
                update={"grant": stored.grant.model_copy(update={"revoked": document["revoked"]})}
            )
        except ValidationError, KeyError, TypeError:
            raise VerificationStorageError("Verification access record is invalid") from None

    async def get(
        self, grant_id: str, *, active_at: datetime | None = None
    ) -> StoredVerificationAccess | None:
        try:
            query: dict[str, Any] = {"_id": grant_id}
            if active_at is not None:
                query.update(
                    {
                        "revoked": False,
                        "expires_at": {"$gt": active_at.timestamp()},
                        "$expr": {
                            "$gt": [{"$multiply": ["$expires_at", 1000]}, {"$toLong": "$$NOW"}]
                        },
                    }
                )
            document = await self._collection.find_one(query)
        except PyMongoError:
            raise VerificationStorageError("Verification access storage is unavailable") from None
        stored = self._decode(document) if document is not None else None
        if (
            active_at is not None
            and stored is not None
            and document is not None
            and document["expires_at"] != stored.grant.expires_at.timestamp()
        ):
            raise VerificationStorageError("Verification access expiry metadata is invalid")
        return stored

    async def list(
        self, owner: Identity, *, after: str, limit: int
    ) -> list[StoredVerificationAccess]:
        try:
            cursor = (
                self._collection.find(
                    {
                        "owner_type": owner.type.value,
                        "owner_id": owner.id,
                        "_id": {"$gt": after},
                    }
                )
                .sort("_id", 1)
                .limit(limit)
            )
            return [self._decode(document) async for document in cursor]
        except PyMongoError:
            raise VerificationStorageError("Verification access storage is unavailable") from None

    async def revoke(self, grant_id: str) -> None:
        try:
            await self._collection.update_one({"_id": grant_id}, {"$set": {"revoked": True}})
        except PyMongoError:
            raise VerificationStorageError("Verification access storage is unavailable") from None

    async def pending(self, *, after: str, limit: int) -> Sequence[StoredVerificationAccess]:
        try:
            return [
                self._decode(document)
                for document in await self._lifecycle.pending(after=after, limit=limit)
            ]
        except PyMongoError:
            raise VerificationStorageError("Verification access storage is unavailable") from None

    async def expire(self, grant_id: str, expected_expiry: datetime, *, now: datetime) -> bool:
        try:
            return await self._lifecycle.expire(grant_id, expected_expiry, now=now)
        except PyMongoError:
            raise VerificationStorageError("Verification access storage is unavailable") from None

    async def renew(
        self, grant_id: str, expected_expiry: datetime, expires_at: datetime, *, now: datetime
    ) -> bool:
        try:
            document = await self._collection.find_one({"_id": grant_id})
            if document is None:
                return False
            stored = self._decode(document)
            grant = stored.grant
            if (
                grant.revoked
                or grant.renewal is None
                or grant.expires_at != expected_expiry
                or grant.renewal.next_expiry(now, expected_expiry) != expires_at
            ):
                return False
            updated = stored.model_copy(
                update={"grant": grant.model_copy(update={"expires_at": expires_at})}
            ).model_dump_json()
            return await self._lifecycle.renew(
                document, updated, expected_expiry, expires_at, now=now, renewal=grant.renewal
            )
        except PyMongoError:
            raise VerificationStorageError("Verification access storage is unavailable") from None
