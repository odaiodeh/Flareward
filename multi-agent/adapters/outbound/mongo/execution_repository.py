"""Native async execution records with immutable request identity and terminal fencing."""

from mas.execution.identity import request_digest
from mas.execution.models import (
    TERMINAL_PHASES,
    ExecutionPhase,
    ExecutionRecord,
    PreparedExecution,
    SubmissionState,
)
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError


class MongoExecutionRepository:
    def __init__(self, database: AsyncDatabase) -> None:
        self._collection = database.program_executions

    async def initialize(self) -> None:
        await self._collection.create_index([("data.parent_execution_id", 1), ("_id", 1)])

    async def create(
        self,
        record: ExecutionRecord,
        prepared: PreparedExecution | None = None,
    ) -> bool:
        try:
            await self._collection.insert_one(
                {
                    "_id": record.execution_id,
                    "request_digest": request_digest(record),
                    "phase": record.phase.value,
                    "submission": record.submission.value,
                    "data": record.model_dump(mode="json"),
                    "prepared": prepared.model_dump_json() if prepared is not None else None,
                }
            )
        except DuplicateKeyError:
            return False
        return True

    async def get(self, execution_id: str) -> ExecutionRecord:
        document = await self._collection.find_one({"_id": execution_id})
        if document is None:
            raise KeyError(execution_id)
        return ExecutionRecord.model_validate(document["data"])

    async def get_prepared(self, execution_id: str) -> PreparedExecution:
        document = await self._collection.find_one({"_id": execution_id}, {"prepared": 1})
        if document is None or document.get("prepared") is None:
            raise KeyError(execution_id)
        return PreparedExecution.model_validate_json(document["prepared"])

    async def children(self, execution_id: str) -> list[ExecutionRecord]:
        cursor = self._collection.find({"data.parent_execution_id": execution_id}).sort("_id", 1)
        return [ExecutionRecord.model_validate(document["data"]) async for document in cursor]

    async def claim_submission(self, execution_id: str) -> bool:
        document = await self._collection.find_one_and_update(
            {
                "_id": execution_id,
                "submission": SubmissionState.PREPARED.value,
                "phase": {"$nin": [phase.value for phase in TERMINAL_PHASES]},
            },
            {
                "$set": {
                    "submission": SubmissionState.STARTING.value,
                    "data.submission": SubmissionState.STARTING.value,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return document is not None

    async def cancel_prepared(self, execution_id: str) -> bool:
        result = await self._collection.update_one(
            {
                "_id": execution_id,
                "submission": SubmissionState.PREPARED.value,
                "phase": {"$nin": [phase.value for phase in TERMINAL_PHASES]},
            },
            {
                "$set": {
                    "phase": ExecutionPhase.CANCELLED.value,
                    "data.phase": ExecutionPhase.CANCELLED.value,
                }
            },
        )
        return result.matched_count == 1

    async def pending(
        self,
        limit: int = 100,
        *,
        after_execution_id: str | None = None,
    ) -> list[ExecutionRecord]:
        query = {"phase": {"$nin": [phase.value for phase in TERMINAL_PHASES]}}
        if after_execution_id is not None:
            query["_id"] = {"$gt": after_execution_id}
        cursor = self._collection.find(query).sort("_id", 1).limit(limit)
        return [ExecutionRecord.model_validate(document["data"]) async for document in cursor]

    async def update(self, record: ExecutionRecord) -> None:
        query = {"_id": record.execution_id, "request_digest": request_digest(record)}
        query["$or"] = [
            {"phase": {"$nin": [phase.value for phase in TERMINAL_PHASES]}},
            {"phase": record.phase.value},
        ]
        if record.submission in {
            SubmissionState.PREPARED,
            SubmissionState.STARTING,
            SubmissionState.UNCONFIRMED,
        }:
            query["submission"] = {"$ne": SubmissionState.ACCEPTED.value}
        result = await self._collection.update_one(
            query,
            {
                "$set": {
                    "phase": record.phase.value,
                    "submission": record.submission.value,
                    "data": record.model_dump(mode="json"),
                }
            },
        )
        if result.matched_count == 0:
            current = await self.get(record.execution_id)
            if request_digest(current) != request_digest(record):
                raise ValueError("Execution request identity cannot be changed")
            if (
                current.phase not in TERMINAL_PHASES
                and current.submission != SubmissionState.ACCEPTED
            ):
                raise RuntimeError("Execution update lost its matching record")
