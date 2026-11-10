"""Majority-written check intents use the existing native application database."""

from typing import Any

from pydantic import ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.write_concern import WriteConcern

from lumora.services.verification.domain.check_runs import (
    CheckJobState,
    CheckRun,
    CheckRunStatus,
)
from lumora.services.verification.ports import VerificationStorageError


class MongoCheckRunRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.get_collection(
            "verification_check_runs", write_concern=WriteConcern(w="majority")
        )

    async def initialize(self) -> None:
        try:
            await self._collection.create_index([("job_state", 1), ("_id", 1)])
        except PyMongoError:
            raise VerificationStorageError("Check intent storage is unavailable") from None

    @staticmethod
    def _job_state(run: CheckRun) -> str | None:
        return run.job_state.value if run.job_state is not None else None

    @classmethod
    def _decode(cls, document: dict[str, Any]) -> CheckRun:
        try:
            run = CheckRun.model_validate_json(document["data"])
            if (
                run.intent_id != document["_id"]
                or run.revision != document["revision"]
                or cls._job_state(run) != document["job_state"]
            ):
                raise VerificationStorageError("Check intent identity is invalid")
            return run
        except ValidationError, KeyError, TypeError:
            raise VerificationStorageError("Check intent is invalid") from None

    async def create(self, run: CheckRun) -> bool:
        if run.revision != 0 or run.status != CheckRunStatus.READY:
            raise ValueError("Check intent must start ready")
        try:
            await self._collection.insert_one(
                {
                    "_id": run.intent_id,
                    "revision": 0,
                    "data": run.model_dump_json(),
                    "job_state": self._job_state(run),
                }
            )
        except DuplicateKeyError:
            return False
        except PyMongoError:
            raise VerificationStorageError("Check intent storage is unavailable") from None
        return True

    async def get(self, intent_id: str) -> CheckRun | None:
        try:
            document = await self._collection.find_one({"_id": intent_id})
        except PyMongoError:
            raise VerificationStorageError("Check intent storage is unavailable") from None
        if document is None:
            return None
        return self._decode(document)

    async def pending_jobs(self, *, after: str, limit: int) -> list[CheckRun]:
        if not 1 <= limit <= 100:
            raise ValueError("Check maintenance page size must be between 1 and 100")
        try:
            cursor = (
                self._collection.find(
                    {
                        "job_state": {
                            "$in": [CheckJobState.ACTIVE.value, CheckJobState.RETIRING.value]
                        },
                        "_id": {"$gt": after},
                    }
                )
                .sort("_id", 1)
                .limit(limit)
            )
            return [self._decode(document) async for document in cursor]
        except PyMongoError:
            raise VerificationStorageError("Check intent storage is unavailable") from None

    async def save(self, run: CheckRun, *, expected_revision: int) -> bool:
        if run.revision != expected_revision + 1:
            raise ValueError("Check update requires the next revision")
        try:
            result = await self._collection.update_one(
                {"_id": run.intent_id, "revision": expected_revision},
                {
                    "$set": {
                        "revision": run.revision,
                        "data": run.model_dump_json(),
                        "job_state": self._job_state(run),
                    }
                },
            )
            return result.modified_count == 1
        except PyMongoError:
            raise VerificationStorageError("Check intent storage is unavailable") from None
