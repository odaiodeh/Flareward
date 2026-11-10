"""Signed humans query real reporting stores and execute the production TypeScript clients."""

import os
import shutil
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from support.http_programs import execute_program, publish_program
from support.identity import authenticated_cookie
from support.native_settings import session_settings
from support.reporting import OWNER, executions
from support.server import api_process
from support.ui_clients import run_contracts

from lumora.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from lumora.programs.domain.models import ApplicationDefinition, ProgramDefinition
from lumora.services.connections.adapters.redis import owned_redis


async def test_reporting_native_authority_root_counts_and_pinned_names(
    mongo_database, redis_uri, tmp_path, request
):
    settings = session_settings(mongo_database.name, redis_uri).model_copy(
        update={
            "admin_config_database": mongo_database.name,
            "reconcile_interval": 3600,
        }
    )
    await mongo_database.admin_config.insert_one(
        {"key": "admin_users", "value": {"admin_usernames": ["ADMIN"]}}
    )
    async with AsyncExitStack() as stack:
        redis = await stack.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        cookies = {}
        for name in ("same", "admin", "other"):
            cookies[name] = await stack.enter_async_context(
                authenticated_cookie(redis, name, settings.secret_key.get_secret_value())
            )
        http = await stack.enter_async_context(api_process(settings, tmp_path / "reporting.log"))
        owner = {"Cookie": "session=" + cookies["same"]}
        admin = {"Cookie": "session=" + cookies["admin"]}
        first = None
        for name in ("Original name", "Changed name"):
            reference = await publish_program(
                http,
                ProgramDefinition(
                    program_id="build",
                    name=name,
                    owner=OWNER,
                    implementation=ApplicationDefinition(
                        implementation="wait",
                        version="1",
                        config={"channel": "answer", "timeout_seconds": 0.01},
                    ),
                ),
                headers=owner,
            )
            first = first or reference
        saved = await http.get("/api/programs/build", headers=owner)
        definition = saved.json()["definition"]
        definition["name"] = "Unpublished title"
        assert (
            await http.put(
                "/api/programs/build",
                headers=owner,
                json={"definition": definition, "expected_version": saved.json()["version"]},
            )
        ).status_code == 200
        records = MongoExecutionRepository(mongo_database)
        now = datetime.now(UTC)
        for record in executions():
            at = now - (
                timedelta(days=40) if record.execution_id == "old" else timedelta(minutes=5)
            )
            context = record.context.model_copy(
                update={
                    "started_at": at,
                    "finished_at": at + timedelta(seconds=10)
                    if record.phase == "completed"
                    else None,
                }
            )
            assert await records.create(record.model_copy(update={"context": context}))
        # This extra run is a real native invocation, not a seeded projection.
        http.headers.update(owner)
        result = await execute_program(http, first, uuid4().hex)
        assert result["phase"] == "completed"
        http.headers.clear()
        assert (await http.get("/api/reporting/system")).status_code == 401
        assert (
            await http.get("/api/reporting/system?userId=admin", headers=owner)
        ).status_code == 403
        assert (
            await http.get(
                "/api/reporting/system", headers={**admin, "Authorization": "Bearer invalid"}
            )
        ).status_code == 401
        report = await http.get(
            "/api/reporting/system?time_range=today&owner_limit=1", headers=admin
        )
        assert report.status_code == 200, report.text
        data = report.json()
        assert data["root_executions"] == 6 and data["unique_owners"] == 2
        assert data["observation"] == "stored_execution_projection"
        revision = next(row for row in data["top_programs"] if row["program"]["revision"] == 1)
        assert revision["program_name"] == "Original name" and revision["completion_rate"] == 75
        assert (
            "Unpublished title" not in report.text
            and "reporting-private-sentinel" not in report.text
        )
        assert (await http.get("/api/executions/first", headers=admin)).status_code in (403, 404)
        assert (
            await http.get("/api/reporting/system?time_range=invalid", headers=admin)
        ).status_code == 422
        assert (
            await http.get("/api/reporting/system?owner_limit=101", headers=admin)
        ).status_code == 422
        if request.config.getoption("--ui-clients"):
            node = shutil.which("node")
            assert node is not None
            output = await run_contracts(
                node,
                "reporting",
                {
                    **os.environ,
                    "LUMORA_TEST_UI_API_URL": str(http.base_url).rstrip("/") + "/api",
                    "LUMORA_TEST_UI_OWNER_COOKIE": "session=" + cookies["same"],
                    "LUMORA_TEST_UI_ADMIN_COOKIE": "session=" + cookies["admin"],
                },
            )
            assert "Reporting production clients passed" in output
        await mongo_database.admin_config.update_one(
            {"key": "admin_users"}, {"$set": {"value.admin_usernames": []}}
        )
        assert (await http.get("/api/reporting/system", headers=admin)).status_code == 403
