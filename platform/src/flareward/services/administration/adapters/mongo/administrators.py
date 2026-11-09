"""Async persisted administrator directory; policy and bootstrap decisions remain inward."""

from typing import Any

from pydantic import BaseModel, Field, ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from flareward.services.access.administrators import AdministratorAccessUnavailable


class _Administrators(BaseModel):
    admin_usernames: tuple[str, ...] = Field(default=(), max_length=10_000)


class MongoAdministratorDirectory:
    def __init__(self, database: AsyncDatabase[dict[str, Any]], collection: str) -> None:
        self._collection = database[collection]

    async def usernames(self) -> tuple[str, ...] | None:
        try:
            row = await self._collection.find_one({"key": "admin_users"}, {"value": 1})
            return (
                _Administrators.model_validate(row["value"]).admin_usernames
                if row is not None
                else None
            )
        except PyMongoError, ValidationError, KeyError, TypeError:
            raise AdministratorAccessUnavailable() from None
