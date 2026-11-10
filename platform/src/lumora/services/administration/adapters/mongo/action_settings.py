"""Read action settings through an application-owned asynchronous boundary."""

from typing import Any

from pydantic import JsonValue, TypeAdapter
from pymongo.asynchronous.collection import AsyncCollection


class MongoActionSettings:
    def __init__(self, collection: AsyncCollection[dict[str, Any]]) -> None:
        self._collection = collection

    async def get_section(self, key: str) -> dict[str, JsonValue] | None:
        document = await self._collection.find_one({"key": key}, {"value": 1})
        value = document.get("value") if document else None
        return (
            TypeAdapter(dict[str, JsonValue]).validate_python(value)
            if isinstance(value, dict)
            else None
        )
