"""Actual Mongo aggregation preserves owner types and counts root executions, not sessions."""

from datetime import timedelta

import pytest
from support.reporting import NOW, OWNER, TEAM, execution, executions

from lumora.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from lumora.services.access.administrators import (
    AdministratorAccessUnavailable,
    AdministratorPolicy,
)
from lumora.services.administration.adapters.mongo.administrators import (
    MongoAdministratorDirectory,
)
from lumora.services.reporting.adapters.mongo.reporting import MongoReportingReader
from lumora.services.reporting.service import ReportingUnavailable


async def test_root_reporting_pagination_time_scope_and_private_payloads(mongo_database):
    records = MongoExecutionRepository(mongo_database)
    for record in executions():
        assert await records.create(record)
    reader = MongoReportingReader(mongo_database)
    report = await reader.system(
        NOW - timedelta(days=7), NOW + timedelta(seconds=1), offset=0, limit=1
    )
    assert report.root_executions == 5 and report.unique_owners == 2
    assert report.status_breakdown == {"completed": 2, "failed": 1, "running": 1, "cancelled": 1}
    assert len(report.owner_activity) == 1 and report.owner_activity[0].identity_type == "user"
    assert (
        report.owner_activity[0].identity_id == "same" and report.owner_activity[0].run_count == 4
    )
    assert len(report.top_owners) == 2 and len(report.top_programs) == 2
    first = report.top_programs[0]
    assert (
        first.program.revision == 1
        and first.unique_owners == 2
        and first.avg_duration_seconds == 10
    )
    assert first.program_name is None
    following = await reader.system(None, NOW + timedelta(seconds=1), offset=1, limit=1)
    assert following.root_executions == 6 and following.owner_activity[0].identity_type == "team"
    assert "reporting-private-sentinel" not in report.model_dump_json()
    assert [(point.period, point.count) for point in report.time_series] == [("2026-11-05", 5)]


async def test_overview_owns_exact_identity_and_counts_observed_active_sessions(mongo_database):
    for owner, count in ((OWNER, 2), (TEAM, 3)):
        scope = {"identity": owner.model_dump(mode="json")}
        for index in range(count):
            await mongo_database.blueprints.insert_one(
                {**scope, "blueprint_id": f"{owner.type}-{index}"}
            )
            await mongo_database.resources.insert_one(
                {**scope, "category": "tool", "type": "fixture"}
            )
            await mongo_database.workflow_sessions.insert_one(
                {
                    **scope,
                    "blueprint_id": "blueprint",
                    "status": "RUNNING",
                    "active_execution_id": str(index),
                }
            )
    await mongo_database.workflow_sessions.insert_one(
        {"identity": OWNER.model_dump(mode="json"), "blueprint_id": "idle", "status": "COMPLETED"}
    )
    reader = MongoReportingReader(mongo_database)
    own, team = await reader.overview(OWNER), await reader.overview(TEAM)
    assert own.blueprint_drafts == own.observed_active_sessions == own.resources[0].count == 2
    assert team.blueprint_drafts == team.observed_active_sessions == team.resources[0].count == 3
    assert own.blueprint_sessions == {"blueprint": 2, "idle": 1}


async def test_admin_policy_empty_document_revokes_bootstrap_authority(mongo_database):
    policy = AdministratorPolicy(
        MongoAdministratorDirectory(mongo_database, "admin_config"), ("same",)
    )
    assert await policy.allowed(OWNER)
    await mongo_database.admin_config.insert_one(
        {"key": "admin_users", "value": {"admin_usernames": []}}
    )
    assert not await policy.allowed(OWNER)
    await mongo_database.admin_config.update_one(
        {"key": "admin_users"}, {"$set": {"value": {"admin_usernames": ["SAME"]}}}
    )
    assert await policy.allowed(OWNER) and not await policy.allowed(TEAM)
    await mongo_database.admin_config.update_one(
        {"key": "admin_users"}, {"$set": {"value": {"admin_usernames": "same"}}}
    )
    with pytest.raises(AdministratorAccessUnavailable):
        await policy.allowed(OWNER)
    await mongo_database.program_executions.insert_one(
        {
            "data": {
                "parent_execution_id": None,
                "context": {"started_at": NOW},
                "program": {"program_id": "bad", "revision": 1},
            },
            "phase": "invalid",
        }
    )
    with pytest.raises(ReportingUnavailable):
        await MongoReportingReader(mongo_database).system(None, NOW, offset=0, limit=1)


async def test_empty_and_bounded_timeline_do_not_invent_totals(mongo_database):
    reader = MongoReportingReader(mongo_database)
    empty = await reader.system(None, NOW, offset=100, limit=10)
    assert empty.root_executions == empty.unique_owners == empty.programs_used == 0
    assert empty.owner_activity == empty.top_programs == empty.time_series == ()
    assert not empty.time_series_truncated
    records = MongoExecutionRepository(mongo_database)
    for day in range(370):
        assert await records.create(execution(str(day), at=NOW - timedelta(days=day)))
    report = await reader.system(None, NOW, offset=100, limit=10)
    assert report.root_executions == 370 and report.owner_activity == ()
    assert len(report.time_series) == 366 and report.time_series_truncated
    assert report.time_series[0].period == (NOW - timedelta(days=365)).date().isoformat()
    assert report.time_series[-1].period == NOW.date().isoformat()
