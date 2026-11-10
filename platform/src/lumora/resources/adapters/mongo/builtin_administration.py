"""Atomic curated resource changes on a transaction-capable Mongo deployment."""

import asyncio
from typing import Any

from pydantic import ValidationError
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from lumora.resources.adapters.mongo.resource_authoring_repository import (
    MongoResourceAuthoringRepository,
    storage_errors,
)
from lumora.resources.authoring import ResourceRecord
from lumora.resources.domain.builtins import BuiltinResourceDescriptor
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.domain.models import Resource
from lumora.resources.errors import ResourceConflictError, ResourceStorageError


class MongoBuiltinAdministration:
    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        *,
        resources: str,
        descriptors: str,
        blueprints: str,
        overlays: str = "builtin_user_configs",
    ) -> None:
        self._database = database
        self._resources, self._descriptors = database[resources], database[descriptors]
        self._overlays = database[overlays]
        self._reader = MongoResourceAuthoringRepository(
            database, resources=resources, descriptors=descriptors, blueprints=blueprints
        )
        self._lookup = {
            "$lookup": {
                "from": descriptors,
                "localField": "_id",
                "foreignField": "_id",
                "as": "_descriptor",
            }
        }

    async def get(self, rid: str) -> ResourceRecord:
        return await self._reader.get(rid)

    async def usage(self, rid: str) -> tuple[list[str], list[str]]:
        return await self._reader.usage(rid)

    async def list(
        self, category: ResourceCategory | None, type_key: str | None, offset: int, limit: int
    ) -> tuple[list[ResourceRecord], int]:
        filters: dict[str, Any] = {}
        if category is not None:
            filters["category"] = category.value
        if type_key is not None:
            filters["type"] = type_key
        async with storage_errors():
            rows = await (
                await self._resources.aggregate(
                    [
                        {"$match": filters},
                        self._lookup,
                        {"$match": {"_descriptor.0": {"$exists": True}}},
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
                    ],
                    maxTimeMS=5000,
                )
            ).to_list(1)
        data = rows[0]
        return [self._record(row) for row in data["items"]], data["count"][0]["total"] if data[
            "count"
        ] else 0

    async def dependents(self, rid: str) -> tuple[ResourceRecord, ...]:
        async with storage_errors():
            rows = await (
                await self._resources.aggregate(
                    [
                        {"$match": {"nested_refs": rid}},
                        {"$limit": 1001},
                        self._lookup,
                    ],
                    maxTimeMS=5000,
                )
            ).to_list(1001)
        if len(rows) > 1000:
            raise ValueError("Curated dependent graph exceeds its limit")
        return tuple(self._record(row) for row in rows)

    async def commit(
        self,
        observed: tuple[ResourceRecord, ...],
        changed: tuple[ResourceRecord, ...],
        deleted: tuple[str, ...] = (),
    ) -> None:
        async def apply(session: AsyncClientSession) -> None:
            # Every observed resource is written, even when already public. That
            # serializes publication against concurrent demotion/deletion/config edits.
            for entry in sorted(observed, key=lambda item: item.resource.rid):
                rid = entry.resource.rid
                resource = await self._resources.find_one({"_id": rid}, session=session)
                descriptor = await self._descriptors.find_one({"_id": rid}, session=session)
                if resource is None:
                    raise ResourceConflictError()
                try:
                    actual = ResourceRecord(
                        resource=Resource.model_validate(resource),
                        descriptor=BuiltinResourceDescriptor.model_validate(descriptor)
                        if descriptor
                        else None,
                        storage_revision=resource.get("_admin_fence", 0),
                    )
                except ValidationError:
                    raise ResourceConflictError() from None
                if actual != entry:
                    raise ResourceConflictError()
                await self._resources.update_one(
                    {"_id": rid}, {"$inc": {"_admin_fence": 1}}, session=session
                )
            existing = {entry.resource.rid for entry in observed}
            for entry in changed:
                rid = entry.resource.rid
                document = {
                    "_id": rid,
                    **entry.resource.model_dump(mode="json"),
                    "_admin_fence": entry.storage_revision + 1,
                }
                if rid in existing:
                    await self._resources.replace_one({"_id": rid}, document, session=session)
                else:
                    await self._resources.insert_one(document, session=session)
                if entry.descriptor is not None:
                    await self._descriptors.replace_one(
                        {"_id": rid},
                        {"_id": rid, **entry.descriptor.model_dump(mode="json")},
                        upsert=True,
                        session=session,
                    )
            for rid in deleted:
                if rid not in existing:
                    raise ResourceConflictError()
                await self._resources.delete_one({"_id": rid}, session=session)
                await self._descriptors.delete_one({"_id": rid}, session=session)
                await self._overlays.delete_many({"resource_id": rid}, session=session)

        try:
            async with storage_errors(), asyncio.timeout(15):
                async with self._database.client.start_session() as session:
                    await session.with_transaction(
                        apply,
                        read_concern=ReadConcern("snapshot"),
                        write_concern=WriteConcern("majority"),
                        max_commit_time_ms=5000,
                    )
        except TimeoutError:
            raise ResourceStorageError() from None

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
