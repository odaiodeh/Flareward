"""Atomic encrypted issuance reservations; retired rows retain audit without material."""

import asyncio
from datetime import datetime
from typing import Any

from pydantic import SecretStr, ValidationError
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.write_concern import WriteConcern

from lumora.async_work import await_owned
from lumora.services.access.issuance import (
    CredentialIssuanceClosed,
    CredentialIssuanceConflict,
    CredentialMaterial,
    CredentialMaterialUnavailable,
    CredentialReservation,
)
from lumora.services.auth.credentials.ports import CipherError, TokenCipher


class MongoCredentialMaterial:
    def __init__(self, database: AsyncDatabase[dict[str, Any]], cipher: TokenCipher) -> None:
        self._collection = database.get_collection(
            "workflow_credential_material", write_concern=WriteConcern(w="majority")
        )
        self._cipher = cipher

    async def initialize(self) -> None:
        try:
            await self._collection.create_index([("retired", 1), ("_id", 1)])
            await self._collection.create_index([("cleanup_pending", 1), ("_id", 1)])
        except PyMongoError:
            raise CredentialMaterialUnavailable() from None

    @staticmethod
    def _reservation(document: dict[str, Any]) -> CredentialReservation:
        try:
            reservation = CredentialReservation.model_validate_json(document["data"])
            if reservation.binding_id != document["_id"]:
                raise CredentialMaterialUnavailable()
            return reservation
        except ValidationError, KeyError, TypeError:
            raise CredentialMaterialUnavailable() from None

    async def reserve(self, candidate: CredentialMaterial) -> CredentialMaterial:
        reservation = candidate.reservation
        try:
            encrypted = await await_owned(
                asyncio.to_thread(self._cipher.encrypt, candidate.credential.get_secret_value())
            )
            if (
                not isinstance(encrypted, str)
                or encrypted == candidate.credential.get_secret_value()
            ):
                raise CredentialMaterialUnavailable()
            try:
                document = await self._collection.find_one_and_update(
                    {"_id": reservation.binding_id},
                    {
                        "$setOnInsert": {
                            "data": reservation.model_dump_json(),
                            "maximum_expiry": reservation.maximum_expiry.timestamp(),
                            "credential": encrypted,
                            "retired": False,
                            "cleanup_pending": False,
                        }
                    },
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                )
            except DuplicateKeyError:
                document = await self._collection.find_one({"_id": reservation.binding_id})
            if document is None:
                raise CredentialMaterialUnavailable()
            saved = self._reservation(document)
            if saved.request_sha256 != reservation.request_sha256:
                raise CredentialIssuanceConflict()
            if document.get("retired") is not False:
                raise CredentialIssuanceClosed()
            decrypted = await await_owned(
                asyncio.to_thread(self._cipher.decrypt, document["credential"])
            )
            if (
                not isinstance(decrypted, str)
                or not decrypted
                or decrypted == document["credential"]
            ):
                raise CredentialMaterialUnavailable()
            return CredentialMaterial(saved, SecretStr(decrypted))
        except PyMongoError, CipherError, KeyError, TypeError:
            raise CredentialMaterialUnavailable() from None

    async def pending(self, *, after: str, limit: int) -> list[CredentialReservation]:
        if not 1 <= limit <= 100:
            raise ValueError("Credential maintenance page size must be between 1 and 100")
        try:
            cursor = (
                self._collection.find({"retired": False, "_id": {"$gt": after}}, {"data": 1})
                .sort("_id", 1)
                .limit(limit)
            )
            return [self._reservation(document) async for document in cursor]
        except PyMongoError:
            raise CredentialMaterialUnavailable() from None

    async def retire(self, binding_id: str) -> None:
        try:
            await self._collection.update_one(
                {"_id": binding_id, "retired": False},
                {"$set": {"retired": True, "cleanup_pending": True}, "$unset": {"credential": ""}},
            )
        except PyMongoError:
            raise CredentialMaterialUnavailable() from None

    async def expire(self, reservation: CredentialReservation, *, now: datetime) -> bool:
        if reservation.maximum_expiry > now:
            return False
        try:
            result = await self._collection.update_one(
                {
                    "_id": reservation.binding_id,
                    "retired": False,
                    "maximum_expiry": {
                        "$eq": reservation.maximum_expiry.timestamp(),
                        "$lte": now.timestamp(),
                    },
                    "$expr": {
                        "$lte": [{"$multiply": ["$maximum_expiry", 1000]}, {"$toLong": "$$NOW"}]
                    },
                },
                {"$set": {"retired": True, "cleanup_pending": True}, "$unset": {"credential": ""}},
            )
            return result.modified_count == 1
        except PyMongoError:
            raise CredentialMaterialUnavailable() from None

    async def cleanup_pending(self, *, after: str, limit: int) -> list[CredentialReservation]:
        if not 1 <= limit <= 100:
            raise ValueError("Credential maintenance page size must be between 1 and 100")
        try:
            cursor = (
                self._collection.find({"cleanup_pending": True, "_id": {"$gt": after}}, {"data": 1})
                .sort("_id", 1)
                .limit(limit)
            )
            return [self._reservation(document) async for document in cursor]
        except PyMongoError:
            raise CredentialMaterialUnavailable() from None

    async def cleaned(self, binding_id: str) -> None:
        try:
            await self._collection.update_one(
                {"_id": binding_id, "retired": True}, {"$set": {"cleanup_pending": False}}
            )
        except PyMongoError:
            raise CredentialMaterialUnavailable() from None
