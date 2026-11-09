"""Native async execution records with immutable request identity and terminal fencing."""

from datetime import datetime
from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from flareward.executions.domain.identity import request_digest
from flareward.executions.domain.models import (
    TERMINAL_PHASES,
    ExecutionPhase,
    ExecutionRecord,
    SubmissionState,
)
from flareward.executions.models import PreparedExecution, SubmissionClaim


class MongoExecutionRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
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
                    "cancel_requested": record.cancel_requested,
                }
            )
        except DuplicateKeyError:
            return False
        return True

    async def get(self, execution_id: str) -> ExecutionRecord:
        document = await self._collection.find_one({"_id": execution_id})
        if document is None:
            raise KeyError(execution_id)
        return self._record(document)

    @staticmethod
    def _record(document: dict[str, Any]) -> ExecutionRecord:
        return ExecutionRecord.model_validate(document["data"]).model_copy(
            update={"cancel_requested": bool(document.get("cancel_requested", False))}
        )

    async def get_prepared(self, execution_id: str) -> PreparedExecution:
        document = await self._collection.find_one({"_id": execution_id}, {"prepared": 1})
        if document is None or document.get("prepared") is None:
            raise KeyError(execution_id)
        return PreparedExecution.model_validate_json(document["prepared"])

    async def children(self, execution_id: str) -> list[ExecutionRecord]:
        cursor = self._collection.find({"data.parent_execution_id": execution_id}).sort("_id", 1)
        return [self._record(document) async for document in cursor]

    async def claim_submission(
        self, execution_id: str, claim: SubmissionClaim, *, now: datetime, recover: bool = False
    ) -> bool:
        if claim.expires_at <= now:
            raise ValueError("Submission claim must have a future deadline")
        query: dict[str, object] = {
            "_id": execution_id,
            "phase": {"$nin": [phase.value for phase in TERMINAL_PHASES]},
        }
        if recover:
            query["$or"] = [
                {"submission": SubmissionState.UNCONFIRMED.value},
                {
                    "submission": SubmissionState.STARTING.value,
                    "$or": [
                        {"claim_expires_at": {"$lte": now.timestamp()}},
                        {"claim_expires_at": {"$exists": False}},
                    ],
                },
            ]
        else:
            query["submission"] = SubmissionState.PREPARED.value
        document = await self._collection.find_one_and_update(
            query,
            {
                "$set": {
                    "submission": SubmissionState.STARTING.value,
                    "data.submission": SubmissionState.STARTING.value,
                    "submission_claim": claim.model_dump(mode="json"),
                    "claim_expires_at": claim.expires_at.timestamp(),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return document is not None

    async def submission_claim(self, execution_id: str) -> SubmissionClaim | None:
        document = await self._collection.find_one({"_id": execution_id}, {"submission_claim": 1})
        value = document.get("submission_claim") if document else None
        return SubmissionClaim.model_validate(value) if value else None

    async def finish_submission(self, record: ExecutionRecord, token: str) -> bool:
        try:
            return await self._update(record, token)
        finally:
            await self._collection.update_one(
                {"_id": record.execution_id, "submission_claim.token": token},
                {"$unset": {"submission_claim": "", "claim_expires_at": ""}},
            )

    async def request_cancellation(self, execution_id: str) -> None:
        await self._collection.update_one(
            {"_id": execution_id, "phase": {"$nin": [phase.value for phase in TERMINAL_PHASES]}},
            {"$set": {"cancel_requested": True}},
        )

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
        query: dict[str, object] = {"phase": {"$nin": [phase.value for phase in TERMINAL_PHASES]}}
        if after_execution_id is not None:
            query["_id"] = {"$gt": after_execution_id}
        cursor = self._collection.find(query).sort("_id", 1).limit(limit)
        return [self._record(document) async for document in cursor]

    async def update(self, record: ExecutionRecord) -> None:
        await self._update(record)

    async def _update(self, record: ExecutionRecord, token: str | None = None) -> bool:
        query: dict[str, object] = {
            "_id": record.execution_id,
            "request_digest": request_digest(record),
        }
        if token is not None:
            query["submission_claim.token"] = token
        query["$or"] = [
            {"phase": {"$nin": [phase.value for phase in TERMINAL_PHASES]}},
            {"phase": record.phase.value},
        ]
        if record.submission in {
            SubmissionState.PREPARED,
            SubmissionState.STARTING,
            SubmissionState.UNCONFIRMED,
            SubmissionState.REFUSED,
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
            if token is not None:
                return False
            if (
                current.phase not in TERMINAL_PHASES
                and current.submission != SubmissionState.ACCEPTED
            ):
                raise RuntimeError("Execution update lost its matching record")
        return result.matched_count == 1
