"""Bounded reporting queries use stored projections without loading execution payloads."""

import asyncio
from datetime import UTC, datetime
from typing import Any

from bson.codec_options import CodecOptions
from pydantic import ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from lumora.executions.domain.models import ExecutionPhase
from lumora.programs.domain.models import ProgramRef
from lumora.services.identity.domain import Identity
from lumora.services.reporting.models import (
    ActivityPoint,
    OwnerActivity,
    OwnerOverview,
    ProgramUsage,
    ResourceCount,
    SystemReport,
)
from lumora.services.reporting.service import ReportingUnavailable


class MongoReportingReader:
    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        *,
        blueprints: str = "blueprints",
        resources: str = "resources",
    ) -> None:
        self._database, self._blueprints, self._resources = database, blueprints, resources

    async def _aggregate(
        self, collection: str, pipeline: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return await (
            await self._database[collection]
            .with_options(codec_options=CodecOptions(tz_aware=True, tzinfo=UTC))
            .aggregate(pipeline, allowDiskUse=True, maxTimeMS=5000)
        ).to_list()

    async def overview(self, owner: Identity) -> OwnerOverview:
        scope = {"identity.type": owner.type.value, "identity.id": owner.id}
        try:
            async with asyncio.TaskGroup() as group:
                blueprint_count = group.create_task(
                    self._database[self._blueprints].count_documents(scope, maxTimeMS=5000)
                )
                program_count = group.create_task(
                    self._database.program_drafts.count_documents(
                        {"owner_type": owner.type.value, "owner_id": owner.id}, maxTimeMS=5000
                    )
                )
                session_counts = group.create_task(
                    self._aggregate(
                        "workflow_sessions",
                        [
                            {"$match": scope},
                            {
                                "$facet": {
                                    "blueprints": [
                                        {"$match": {"blueprint_id": {"$nin": ["", None]}}},
                                        {"$group": {"_id": "$blueprint_id", "count": {"$sum": 1}}},
                                    ],
                                    "active": [
                                        {
                                            "$match": {
                                                "status": {"$in": ["RUNNING", "IN_USE"]},
                                                "active_execution_id": {"$ne": None},
                                            }
                                        },
                                        {"$count": "count"},
                                    ],
                                }
                            },
                        ],
                    )
                )
                resource_counts = group.create_task(
                    self._aggregate(
                        self._resources,
                        [
                            {"$match": scope},
                            {
                                "$group": {
                                    "_id": {"category": "$category", "type": "$type"},
                                    "count": {"$sum": 1},
                                }
                            },
                        ],
                    )
                )
            blueprints, programs = blueprint_count.result(), program_count.result()
            sessions, resources = session_counts.result(), resource_counts.result()
            categories: dict[str, dict[str, int]] = {}
            for row in resources:
                categories.setdefault(row["_id"]["category"], {})[row["_id"]["type"]] = row["count"]
            counts = sessions[0]
            return OwnerOverview(
                blueprint_drafts=blueprints,
                program_drafts=programs,
                observed_active_sessions=counts["active"][0]["count"] if counts["active"] else 0,
                blueprint_sessions={row["_id"]: row["count"] for row in counts["blueprints"]},
                resources=tuple(
                    ResourceCount(category=category, count=sum(types.values()), types=types)
                    for category, types in sorted(categories.items())
                ),
            )
        except PyMongoError, ValidationError, KeyError, TypeError, IndexError, ExceptionGroup:
            raise ReportingUnavailable() from None

    @staticmethod
    def _counts() -> dict[str, Any]:
        return {
            "run_count": {"$sum": 1},
            **{
                phase.value: {"$sum": {"$cond": [{"$eq": ["$phase", phase.value]}, 1, 0]}}
                for phase in ExecutionPhase
            },
        }

    @staticmethod
    def _statuses(row: dict[str, Any]) -> dict[ExecutionPhase, int]:
        return {phase: row[phase.value] for phase in ExecutionPhase if row[phase.value]}

    async def system(
        self, since: datetime | None, until: datetime, *, offset: int, limit: int
    ) -> SystemReport:
        base: list[dict[str, Any]] = [
            {"$match": {"data.parent_execution_id": None}},
            {
                "$set": {
                    "ended": {
                        "$convert": {
                            "input": "$data.context.finished_at",
                            "to": "date",
                            "onError": None,
                            "onNull": None,
                        }
                    },
                    "at": {
                        "$convert": {
                            "input": "$data.context.started_at",
                            "to": "date",
                            "onError": None,
                            "onNull": None,
                        }
                    },
                }
            },
            {"$match": {"at": {"$lte": until, **({"$gte": since} if since else {})}}},
        ]
        owner_key = {"type": "$data.owner.type", "id": "$data.owner.id"}
        owner_group = {"$group": {"_id": owner_key, **self._counts()}}
        owner_sort = {"$sort": {"run_count": -1, "_id.type": 1, "_id.id": 1}}
        try:
            data = (
                await self._aggregate(
                    "program_executions",
                    [
                        *base,
                        {
                            "$facet": {
                                "statuses": [{"$group": {"_id": "$phase", "count": {"$sum": 1}}}],
                                "owners": [{"$group": {"_id": owner_key}}, {"$count": "count"}],
                                "programs": [
                                    {"$group": {"_id": "$data.program.program_id"}},
                                    {"$count": "count"},
                                ],
                                "page": [
                                    owner_group,
                                    owner_sort,
                                    {"$skip": offset},
                                    {"$limit": limit},
                                ],
                                "top": [owner_group, owner_sort, {"$limit": 8}],
                                "usage": [
                                    {
                                        "$group": {
                                            "_id": {
                                                "program_id": "$data.program.program_id",
                                                "revision": "$data.program.revision",
                                            },
                                            **self._counts(),
                                            "last": {"$max": "$at"},
                                            "duration": {
                                                "$avg": {
                                                    "$cond": [
                                                        {
                                                            "$and": [
                                                                {"$eq": ["$phase", "completed"]},
                                                                {"$ne": ["$ended", None]},
                                                                {"$gte": ["$ended", "$at"]},
                                                            ]
                                                        },
                                                        {
                                                            "$divide": [
                                                                {"$subtract": ["$ended", "$at"]},
                                                                1000,
                                                            ]
                                                        },
                                                        None,
                                                    ]
                                                }
                                            },
                                        }
                                    },
                                    {
                                        "$sort": {
                                            "run_count": -1,
                                            "_id.program_id": 1,
                                            "_id.revision": 1,
                                        }
                                    },
                                    {"$limit": 10},
                                ],
                                "series": [
                                    {
                                        "$group": {
                                            "_id": {
                                                "$dateToString": {
                                                    "date": "$at",
                                                    "format": "%Y-%m-%d",
                                                    "timezone": "UTC",
                                                }
                                            },
                                            "count": {"$sum": 1},
                                        }
                                    },
                                    {"$sort": {"_id": -1}},
                                    {"$limit": 367},
                                ],
                            }
                        },
                    ],
                )
            )[0]
            owners = {
                (row["_id"]["type"], row["_id"]["id"]): row["_id"]
                for row in (*data["page"], *data["top"])
            }
            owner_programs = (
                await self._aggregate(
                    "program_executions",
                    [
                        *base,
                        {
                            "$match": {
                                "$or": [
                                    {"data.owner.type": key["type"], "data.owner.id": key["id"]}
                                    for key in owners.values()
                                ]
                            }
                        },
                        {
                            "$group": {
                                "_id": {"owner": owner_key, "program": "$data.program.program_id"}
                            }
                        },
                        {"$group": {"_id": "$_id.owner", "count": {"$sum": 1}}},
                    ],
                )
                if owners
                else []
            )
            program_counts = {
                (row["_id"]["type"], row["_id"]["id"]): row["count"] for row in owner_programs
            }

            def activity(row: dict[str, Any]) -> OwnerActivity:
                key = row["_id"]
                return OwnerActivity(
                    identity_type=key["type"],
                    identity_id=key["id"],
                    run_count=row["run_count"],
                    status_breakdown=self._statuses(row),
                    programs_used=program_counts[(key["type"], key["id"])],
                )

            references = [row["_id"] for row in data["usage"]]
            distinct = (
                await self._aggregate(
                    "program_executions",
                    [
                        *base,
                        {
                            "$match": {
                                "$or": [
                                    {
                                        "data.program.program_id": ref["program_id"],
                                        "data.program.revision": ref["revision"],
                                    }
                                    for ref in references
                                ]
                            }
                        },
                        {
                            "$group": {
                                "_id": {
                                    "program": {
                                        "program_id": "$data.program.program_id",
                                        "revision": "$data.program.revision",
                                    },
                                    "owner": owner_key,
                                }
                            }
                        },
                        {"$group": {"_id": "$_id.program", "count": {"$sum": 1}}},
                    ],
                )
                if references
                else []
            )
            distinct_counts = {
                (row["_id"]["program_id"], row["_id"]["revision"]): row["count"] for row in distinct
            }
            usages = tuple(
                ProgramUsage(
                    program=ProgramRef.model_validate(row["_id"]),
                    run_count=row["run_count"],
                    status_breakdown=self._statuses(row),
                    unique_owners=distinct_counts.get(
                        (row["_id"]["program_id"], row["_id"]["revision"]), 0
                    ),
                    last_run_at=row["last"],
                    avg_duration_seconds=row["duration"],
                )
                for row in data["usage"]
            )
            statuses = {ExecutionPhase(row["_id"]): row["count"] for row in data["statuses"]}
            return SystemReport(
                root_executions=sum(statuses.values()),
                unique_owners=data["owners"][0]["count"] if data["owners"] else 0,
                programs_used=data["programs"][0]["count"] if data["programs"] else 0,
                status_breakdown=statuses,
                owner_activity=tuple(map(activity, data["page"])),
                top_owners=tuple(map(activity, data["top"])),
                owner_offset=offset,
                owner_limit=limit,
                top_programs=tuple(usages),
                time_series=tuple(
                    ActivityPoint(period=row["_id"], count=row["count"])
                    for row in reversed(data["series"][:366])
                ),
                time_series_truncated=len(data["series"]) > 366,
                generated_at=until,
            )
        except PyMongoError, ValidationError, KeyError, TypeError, IndexError, ValueError:
            raise ReportingUnavailable() from None
