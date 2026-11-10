"""Immutable human consent metadata with database-clock expiry and one-way revocation."""

from datetime import datetime
from typing import Any

from pydantic import ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError
from pymongo.write_concern import WriteConcern

from lumora.executions.domain.consent import WorkflowConsent
from lumora.services.access.credentials import WorkflowCredentialUnavailable
from lumora.services.identity.domain import Identity


class MongoWorkflowConsents:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.get_collection(
            "workflow_consents", write_concern=WriteConcern(w="majority")
        )

    async def create(self, consent: WorkflowConsent) -> None:
        try:
            await self._collection.insert_one(
                {
                    "_id": consent.consent_id,
                    "owner_type": consent.owner.type.value,
                    "owner_id": consent.owner.id,
                    "expires_at": consent.expires_at.timestamp(),
                    "revoked": consent.revoked,
                    "data": consent.model_dump_json(),
                }
            )
        except PyMongoError:
            raise WorkflowCredentialUnavailable("Workflow consent storage is unavailable") from None

    async def get(
        self, consent_id: str, owner: Identity, *, active_at: datetime | None = None
    ) -> WorkflowConsent:
        query: dict[str, Any] = {
            "_id": consent_id,
            "owner_type": owner.type.value,
            "owner_id": owner.id,
        }
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
            raise WorkflowCredentialUnavailable("Workflow consent storage is unavailable") from None
        if row is None:
            raise PermissionError("Workflow consent is unavailable or no longer active")
        try:
            consent = WorkflowConsent.model_validate_json(row["data"])
        except KeyError, TypeError, ValidationError:
            raise WorkflowCredentialUnavailable("Workflow consent storage is invalid") from None
        if consent.consent_id != row["_id"] or not consent.owner.owns(owner):
            raise WorkflowCredentialUnavailable("Workflow consent storage is invalid")
        return consent.model_copy(update={"revoked": row["revoked"]})

    async def revoke(self, consent_id: str, owner: Identity) -> None:
        try:
            result = await self._collection.update_one(
                {"_id": consent_id, "owner_type": owner.type.value, "owner_id": owner.id},
                {"$set": {"revoked": True}},
            )
        except PyMongoError:
            raise WorkflowCredentialUnavailable("Workflow consent storage is unavailable") from None
        if not result.matched_count:
            raise PermissionError("Workflow consent is unavailable")
