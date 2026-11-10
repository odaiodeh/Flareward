"""Async invitation storage compatible with legacy JSON and BSON timestamp records."""

import re
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from lumora.services.identity.domain import Identity, IdentityType
from lumora.services.sharing.domain.models import (
    ShareDirection,
    ShareInvite,
    ShareStatus,
    matches_share_identity,
)
from lumora.services.sharing.notifications import ShareMissing, ShareStorageError


class MongoShareNotifications:
    def __init__(self, database: AsyncDatabase[dict[str, Any]], collection: str = "shares") -> None:
        self._collection = database[collection]

    async def initialize(self) -> None:
        try:
            await self._collection.create_index("share_id", unique=True)
            for participant in ("recipient_identity", "sender_identity"):
                await self._collection.create_index(
                    [
                        (participant + ".type", 1),
                        (participant + ".id", 1),
                        ("status", 1),
                        ("created_at", -1),
                    ]
                )
        except PyMongoError:
            raise ShareStorageError("Sharing storage unavailable") from None

    async def get(self, share_id: str) -> ShareInvite:
        try:
            document = await self._collection.find_one({"share_id": share_id})
            if document is None:
                raise ShareMissing("Invitation not found")
            return ShareInvite.model_validate(document)
        except PyMongoError, ValidationError:
            raise ShareStorageError("Sharing storage unavailable") from None

    async def list(
        self,
        caller: Identity,
        direction: ShareDirection,
        status: ShareStatus | None,
        offset: int,
        limit: int,
    ) -> list[ShareInvite]:
        participant = (
            "recipient_identity" if direction == ShareDirection.RECEIVED else "sender_identity"
        )
        query: dict[str, Any] = {
            participant + ".type": caller.type.value,
            participant + ".id": (
                {"$regex": "^" + re.escape(caller.id) + "$", "$options": "i"}
                if caller.type == IdentityType.USER
                else caller.id
            ),
        }
        if status is not None:
            query["status"] = status.value
        try:
            cursor = await self._collection.aggregate(
                [
                    {"$match": query},
                    {
                        "$set": {
                            "_share_created": {
                                "$convert": {
                                    "input": "$created_at",
                                    "to": "date",
                                    "onError": None,
                                    "onNull": None,
                                }
                            }
                        }
                    },
                    {"$sort": {"_share_created": -1, "share_id": 1}},
                    {"$unset": ["_id", "_share_created"]},
                ]
            )
            async with cursor:
                selected = []
                async for document in cursor:
                    invite = ShareInvite.model_validate(document)
                    # Mongo's regex case handling can include Unicode names that Python
                    # casefold keeps distinct. Apply the domain rule before pagination.
                    if not matches_share_identity(invite.participant(direction), caller):
                        continue
                    if offset:
                        offset -= 1
                        continue
                    selected.append(invite)
                    if len(selected) == limit:
                        break
                return selected
        except PyMongoError, ValidationError:
            raise ShareStorageError("Sharing storage unavailable") from None

    async def transition(self, share_id: str, status: ShareStatus, at: datetime) -> bool:
        if status not in (ShareStatus.DECLINED, ShareStatus.CANCELED):
            raise ValueError("Unsupported invitation decision")
        update: dict[str, Any] = {"status": status.value}
        if status == ShareStatus.DECLINED:
            update["declined_at"] = at
        try:
            result = await self._collection.update_one(
                {"share_id": share_id, "status": ShareStatus.PENDING.value}, {"$set": update}
            )
            return result.modified_count == 1
        except PyMongoError:
            raise ShareStorageError("Sharing storage unavailable") from None
