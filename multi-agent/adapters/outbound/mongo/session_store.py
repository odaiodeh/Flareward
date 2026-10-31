"""Native async access to the existing session document shape."""

from mas.core.identity import Identity
from mas.session.domain.dto import SessionListFilter
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.status import SessionStatus
from mas.session.execution.session_store import SessionPage
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError


class MongoSessionStore:
    def __init__(self, database: AsyncDatabase, collection: str = "workflow_sessions") -> None:
        self._collection = database[collection]

    async def initialize(self) -> None:
        await self._collection.create_index("run_id", unique=True, name="uq_session_run_id")
        for fields in (
            [
                ("identity.type", 1),
                ("identity.id", 1),
                ("run_context.started_at", -1),
                ("run_id", -1),
            ],
            [
                ("identity.type", 1),
                ("identity.id", 1),
                ("blueprint_id", 1),
                ("run_context.started_at", -1),
                ("run_id", -1),
            ],
        ):
            await self._collection.create_index(fields)
        await self._collection.create_index([("status", 1), ("program", 1)])
        await self._collection.create_index(
            [
                ("identity.type", 1),
                ("identity.id", 1),
                ("metadata.schedule_id", 1),
                ("run_context.started_at", -1),
            ]
        )

    async def create(self, record: SessionRecord) -> bool:
        try:
            await self._collection.insert_one(record.model_dump(mode="json"))
        except DuplicateKeyError:
            return False
        return True

    async def get(self, session_id: str) -> SessionRecord:
        document = await self._collection.find_one({"run_id": session_id}, {"_id": 0})
        if document is None:
            raise KeyError(session_id)
        return SessionRecord.model_validate(document)

    async def replace(self, record: SessionRecord, *, expected_version: int) -> bool:
        if record.version != expected_version + 1:
            raise ValueError("Session version must increment by one")
        version = (
            {"$or": [{"version": 0}, {"version": {"$exists": False}}]}
            if expected_version == 0
            else {"version": expected_version}
        )
        query = {
            "run_id": record.run_id,
            "identity.type": record.identity.type.value,
            "identity.id": record.identity.id,
            **version,
        }
        result = await self._collection.replace_one(query, record.model_dump(mode="json"))
        return result.matched_count == 1

    async def list(self, owner: Identity, *, limit: int = 100) -> list[SessionRecord]:
        query = {"identity.type": owner.type.value, "identity.id": owner.id}
        return [
            SessionRecord.model_validate(value)
            async for value in self._collection.find(query, {"_id": 0}).limit(limit)
        ]

    async def query(
        self, owner: Identity, filters: SessionListFilter, *, offset: int, limit: int
    ) -> SessionPage:
        query = {
            "identity.type": owner.type.value,
            "identity.id": owner.id,
            **filters.model_dump(exclude_none=True),
        }
        records = [
            SessionRecord.model_validate(document)
            async for document in self._collection.find(query, {"_id": 0})
            .sort([("run_context.started_at", -1), ("run_id", -1)])
            .skip(offset)
            .limit(limit)
        ]
        return SessionPage(
            records=records,
            total=await self._collection.count_documents(query),
            offset=offset,
            limit=limit,
        )

    async def delete(self, record: SessionRecord) -> bool:
        version = (
            {"$or": [{"version": 0}, {"version": {"$exists": False}}]}
            if record.version == 0
            else {"version": record.version}
        )
        result = await self._collection.delete_one(
            {
                "run_id": record.run_id,
                "identity.type": record.identity.type.value,
                "identity.id": record.identity.id,
                **version,
            }
        )
        return result.deleted_count == 1

    async def pending(
        self,
        *,
        limit: int = 100,
        after_session_id: str | None = None,
    ) -> list[SessionRecord]:
        query = {
            "program": {"$ne": None},
            "status": {"$in": [SessionStatus.QUEUED.value, SessionStatus.RUNNING.value]},
        }
        if after_session_id is not None:
            query["run_id"] = {"$gt": after_session_id}
        return [
            SessionRecord.model_validate(value)
            async for value in self._collection.find(query, {"_id": 0})
            .sort("run_id", 1)
            .limit(limit)
        ]

    async def scheduled(
        self, owner: Identity, schedule_id: str, *, limit: int
    ) -> list[SessionRecord]:
        query = {
            "identity.type": owner.type.value,
            "identity.id": owner.id,
            "metadata.schedule_id": schedule_id,
        }
        return [
            SessionRecord.model_validate(document)
            async for document in self._collection.find(query, {"_id": 0})
            .sort("run_context.started_at", -1)
            .limit(limit)
        ]
