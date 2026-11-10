"""Atomic verification records reuse the platform's native async Mongo connection."""

from typing import Any

from pydantic import ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.write_concern import WriteConcern

from lumora.services.verification.domain.models import VerificationState
from lumora.services.verification.ports import VerificationStorageError


class MongoVerificationRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.get_collection(
            "program_verifications", write_concern=WriteConcern(w="majority")
        )

    async def create(self, state: VerificationState) -> bool:
        if state.revision != 0 or state.evidence or state.cancelled:
            raise ValueError("New verification state must be initial")
        try:
            await self._collection.insert_one(
                {
                    "_id": state.plan.plan_id,
                    "revision": 0,
                    "data": state.model_dump_json(),
                }
            )
        except DuplicateKeyError:
            return False
        except PyMongoError:
            raise VerificationStorageError("Verification storage is unavailable") from None
        return True

    async def get(self, plan_id: str) -> VerificationState | None:
        try:
            document = await self._collection.find_one({"_id": plan_id})
        except PyMongoError:
            raise VerificationStorageError("Verification storage is unavailable") from None
        if document is None:
            return None
        try:
            state = VerificationState.model_validate_json(document["data"])
            if state.revision != document["revision"] or state.plan.plan_id != plan_id:
                raise VerificationStorageError("Verification record identity is invalid")
            return state
        except ValidationError, KeyError, TypeError:
            raise VerificationStorageError("Verification record is invalid") from None

    async def save(self, state: VerificationState, *, expected_revision: int) -> bool:
        if state.revision != expected_revision + 1:
            raise ValueError("Verification update requires the next revision")
        try:
            result = await self._collection.update_one(
                {"_id": state.plan.plan_id, "revision": expected_revision},
                {"$set": {"revision": state.revision, "data": state.model_dump_json()}},
            )
        except PyMongoError:
            raise VerificationStorageError("Verification storage is unavailable") from None
        return result.modified_count == 1
