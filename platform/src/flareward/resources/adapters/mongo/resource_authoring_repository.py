"""Native resource persistence shares the library's existing documents and descriptors."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from pydantic import ValidationError
from pymongo import IndexModel
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError

from flareward.resources.authoring import ResourceRecord
from flareward.resources.domain.categories import (
    ResourceCategory,
    ResourceOwnership,
    ResourceVisibility,
)
from flareward.resources.domain.models import Resource
from flareward.resources.errors import ResourceDuplicateNameError, ResourceStorageError
from flareward.services.connections.adapters.mongo.helpers import identity_q
from flareward.services.identity.domain import Identity


@asynccontextmanager
async def storage_errors() -> AsyncIterator[None]:
    try:
        yield
    except DuplicateKeyError:
        raise ResourceDuplicateNameError() from None
    except PyMongoError:
        raise ResourceStorageError() from None


class MongoResourceAuthoringRepository:
    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        *,
        resources: str,
        descriptors: str,
        blueprints: str,
    ) -> None:
        self._resources, self._blueprints = database[resources], database[blueprints]
        self._lookup = {
            "$lookup": {
                "from": descriptors,
                "localField": "_id",
                "foreignField": "_id",
                "as": "_descriptor",
            }
        }

    async def initialize(self) -> None:
        async with storage_errors():
            await self._resources.create_indexes(
                [
                    IndexModel([("nested_refs", 1)]),
                    IndexModel(
                        [
                            ("identity.type", 1),
                            ("identity.id", 1),
                            ("category", 1),
                            ("type", 1),
                            ("name", 1),
                        ],
                        unique=True,
                        name="uq_identity_cat_type_name",
                    ),
                ]
            )

    async def create(self, resource: Resource) -> None:
        async with storage_errors():
            await self._resources.insert_one(
                {"_id": resource.rid, **resource.model_dump(mode="json")}
            )

    async def get(self, rid: str) -> ResourceRecord:
        async with storage_errors():
            rows = await (
                await self._resources.aggregate([{"$match": {"_id": rid}}, self._lookup])
            ).to_list(1)
        if not rows:
            raise KeyError(rid)
        return self._record(rows[0])

    async def replace(self, previous: Resource, updated: Resource) -> bool:
        async with storage_errors():
            result = await self._resources.replace_one(
                self._unchanged(previous), updated.model_dump(mode="json")
            )
        return result.matched_count == 1

    async def delete(self, previous: Resource) -> bool:
        async with storage_errors():
            result = await self._resources.delete_one(self._unchanged(previous))
        return result.deleted_count == 1

    async def usage(self, rid: str) -> tuple[list[str], list[str]]:
        async with storage_errors():
            blueprints = [
                row["blueprint_id"]
                async for row in self._blueprints.find({"rid_refs": rid}, {"blueprint_id": 1})
            ]
            resources = [
                row["_id"] async for row in self._resources.find({"nested_refs": rid}, {"_id": 1})
            ]
        return blueprints, resources

    async def list(
        self,
        caller: Identity,
        *,
        category: ResourceCategory | None,
        type_key: str | None,
        ownership: ResourceOwnership | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ResourceRecord], int]:
        owned = {**identity_q(caller), "_descriptor": []}
        public = {"_descriptor.visibility": ResourceVisibility.PUBLIC.value}
        visible = (
            owned
            if ownership == ResourceOwnership.CUSTOM
            else (public if ownership == ResourceOwnership.BUILTIN else {"$or": [owned, public]})
        )
        filters = {}
        if category is not None:
            filters["category"] = category.value
        if type_key is not None:
            filters["type"] = type_key
        async with storage_errors():
            cursor = await self._resources.aggregate(
                [
                    {"$match": filters},
                    self._lookup,
                    {"$match": visible},
                    {
                        "$facet": {
                            "items": [
                                {"$sort": {"updated": -1, "_id": 1}},
                                {"$skip": offset},
                                {"$limit": limit},
                            ],
                            "count": [{"$count": "total"}],
                        }
                    },
                ]
            )
            result = (await cursor.to_list(1))[0]
        return (
            [self._record(row) for row in result["items"]],
            result["count"][0]["total"] if result["count"] else 0,
        )

    @staticmethod
    def _record(row: dict[str, Any]) -> ResourceRecord:
        try:
            return ResourceRecord.model_validate(
                {
                    "resource": row,
                    "descriptor": row["_descriptor"][0] if row["_descriptor"] else None,
                    "storage_revision": row.get("_admin_fence", 0),
                }
            )
        except ValidationError:
            raise ResourceStorageError() from None

    @staticmethod
    def _unchanged(resource: Resource) -> dict[str, Any]:
        return {
            "_id": resource.rid,
            **identity_q(resource.identity),
            "category": resource.category.value,
            "type": resource.type,
            "name": resource.name,
            "cfg_dict": resource.cfg_dict,
            "execution": (
                {"$in": [None, {}, {"profile": None}]}
                if resource.execution.profile is None
                else resource.execution.model_dump(mode="json")
            ),
            "version": {"$in": [None, 1]} if resource.version == 1 else resource.version,
        }
