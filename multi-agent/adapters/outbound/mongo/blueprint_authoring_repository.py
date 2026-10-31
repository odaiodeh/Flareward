"""Async authoring storage shares existing documents and fences native and legacy edits."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mas.blueprints.contracts import BlueprintDocument, BlueprintPage
from mas.blueprints.exceptions import BlueprintDuplicateNameError, BlueprintStorageError
from mas.core.identity import Identity
from pymongo import IndexModel
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError, PyMongoError

from outbound.mongo.helpers import identity_q


@asynccontextmanager
async def storage_errors(name: str = "") -> AsyncIterator[None]:
    try:
        yield
    except DuplicateKeyError:
        raise BlueprintDuplicateNameError(name) from None
    except PyMongoError:
        raise BlueprintStorageError() from None


def unchanged(document: BlueprintDocument) -> dict:
    return {
        "blueprint_id": document.blueprint_id,
        **identity_q(document.identity),
        "version": document.version if document.version else {"$in": [None, 0]},
        "spec_dict": document.spec_dict,
        "metadata": document.metadata if document.metadata else {"$in": [None, {}]},
    }


class MongoBlueprintAuthoringRepository:
    def __init__(self, collection: AsyncCollection) -> None:
        self._collection = collection

    async def initialize(self) -> None:
        async with storage_errors():
            await self._collection.create_indexes(
                [
                    IndexModel([("blueprint_id", 1)], unique=True),
                    IndexModel([("rid_refs", 1)]),
                    IndexModel([("identity.type", 1), ("identity.id", 1), ("updated_at", -1)]),
                    IndexModel(
                        [("identity.type", 1), ("identity.id", 1), ("spec_dict.name", 1)],
                        unique=True,
                    ),
                ]
            )

    async def create(self, document: BlueprintDocument) -> None:
        async with storage_errors(document.spec_dict.get("name", "")):
            await self._collection.insert_one(document.model_dump(mode="python"))

    async def get(self, blueprint_id: str) -> BlueprintDocument:
        async with storage_errors():
            document = await self._collection.find_one({"blueprint_id": blueprint_id})
        if document is None:
            raise KeyError(blueprint_id)
        return BlueprintDocument.model_validate(document)

    async def replace(self, previous: BlueprintDocument, updated: BlueprintDocument) -> bool:
        async with storage_errors(updated.spec_dict.get("name", "")):
            result = await self._collection.replace_one(
                unchanged(previous), updated.model_dump(mode="python")
            )
        return result.matched_count == 1

    async def delete(self, previous: BlueprintDocument) -> bool:
        async with storage_errors():
            result = await self._collection.delete_one(unchanged(previous))
        return result.deleted_count == 1

    async def list(
        self, identity: Identity, *, skip: int, limit: int, sort_desc: bool
    ) -> BlueprintPage:
        async with storage_errors():
            query = identity_q(identity)
            cursor = (
                self._collection.find(query)
                .sort([("updated_at", -1 if sort_desc else 1), ("blueprint_id", 1)])
                .skip(skip)
                .limit(limit)
            )
            items = [BlueprintDocument.model_validate(document) async for document in cursor]
            total = await self._collection.count_documents(query)
        return BlueprintPage(items=items, total=total, skip=skip, limit=limit)
