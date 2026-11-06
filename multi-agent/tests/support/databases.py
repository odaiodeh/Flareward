"""Own one isolated native Mongo database and drain its client at scenario teardown."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from mas.core.async_work import await_owned
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase


@asynccontextmanager
async def isolated_mongo(uri: str) -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(uri, serverSelectionTimeoutMS=5000)
    database = client[f"unifai_platform_test_{uuid4().hex}"]

    async def cleanup() -> None:
        try:
            await client.drop_database(database.name)
        finally:
            await client.close()

    try:
        await client.admin.command("ping")
        yield database
    finally:
        await await_owned(cleanup())
