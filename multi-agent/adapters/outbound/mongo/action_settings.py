"""Read action settings through an application-owned asynchronous boundary."""

import asyncio
from typing import Any

from mas.core.async_work import await_owned
from mas.core.identity.ports import AdminConfigReaderPort
from pydantic import JsonValue, TypeAdapter
from pymongo.asynchronous.collection import AsyncCollection


class BlockingActionSettings:
    """Legacy composition borrows its existing synchronous settings reader off-loop."""

    def __init__(self, reader: AdminConfigReaderPort) -> None:
        self._reader = reader

    async def get_section(self, key: str) -> dict[str, JsonValue] | None:
        value = await await_owned(asyncio.to_thread(self._reader.get_section, key))
        return (
            TypeAdapter(dict[str, JsonValue]).validate_python(value) if value is not None else None
        )


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
