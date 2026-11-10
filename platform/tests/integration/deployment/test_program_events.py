"""Event-source authority and native occurrences survive API/worker replacement."""

import asyncio
import os
import socket
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from runengine.adapters.coordination.config import TemporalHostConfig
from support.http_programs import publish_program
from support.identity import authenticated_cookie
from support.managed_access import managed_access_api, managed_access_environment
from support.managed_workflow import workflow_requirements
from support.review_programs import review_definition, review_graph
from support.server import api_process
from support.temporal import replay, worker_process, workflow_handle
from temporalio.client import Client, WorkflowExecutionStatus

from lumora.bootstrap.settings.worker_settings import WorkerSettings
from lumora.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from lumora.executions.domain.models import ExecutionRecord
from lumora.programs.domain.models import ProgramDefinition
from lumora.services.connections.adapters.redis import owned_redis
from lumora.services.reviews.domain.models import ReviewRecord
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS


async def test_event_redelivery_and_new_occurrence_recover_after_api_and_worker_restart(
    application, mongo_database, redis_uri, tmp_path
):
    endpoint = os.environ.get("LUMORA_TEST_TEMPORAL_ENDPOINT")
    if not endpoint:
        pytest.skip("Select the dedicated Temporal endpoint for event source recovery")
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    host = TemporalHostConfig(endpoint=endpoint, task_queue="lumora-events-" + uuid4().hex)
    native = await Client.connect(endpoint, namespace=host.namespace)
    records = MongoExecutionRepository(mongo_database)
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            async with AsyncExitStack() as workers:
                async with managed_access_api(
                    mongo_database.name, redis_uri, tmp_path, host=host, listener=listener
                ) as api:
                    settings = api.settings
                    worker_settings = WorkerSettings.model_validate(
                        settings.model_dump(mode="python")
                    )
                    worker = await workers.enter_async_context(
                        worker_process(
                            worker_settings,
                            tmp_path / "event-worker-first.log",
                            environment=managed_access_environment(str(api.http.base_url)),
                        )
                    )
                    child = await publish_program(
                        api.http,
                        ProgramDefinition(
                            program_id="event-review",
                            name="Review",
                            owner=api.owner,
                            implementation=review_definition(application.elements, "process"),
                        ),
                        headers=api.human,
                    )
                    program = await publish_program(
                        api.http,
                        ProgramDefinition(
                            program_id="event-workflow",
                            name="Workflow",
                            owner=api.owner,
                            implementation=review_graph(child),
                        ),
                        headers=api.human,
                    )
                    response = await api.http.post(
                        "/api/program-events/sources",
                        headers=api.human,
                        json={
                            "name": "Durable issues",
                            "program": program.model_dump(mode="json"),
                            "event_type": "issue@1",
                            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                            "workflow_access": [workflow_requirements()[0].model_dump(mode="json")],
                        },
                    )
                    assert response.status_code == 201, response.text
                    source = response.json()
                    bearer = {"Authorization": "Bearer " + source["credential"]}
                    event = {
                        "event_id": "first",
                        "event_type": "issue@1",
                        "inputs": {"subject": "candidate-a"},
                    }
                    accepted = await api.http.post(
                        "/api/program-events/deliveries", headers=bearer, json=event
                    )
                    assert accepted.status_code == 202, accepted.text
                    root = accepted.json()["execution_id"]
                    async with asyncio.timeout(30):
                        while True:
                            inbox = await api.http.get("/api/reviews/inbox", headers=api.reviewer)
                            assert inbox.status_code == 200, inbox.text
                            if inbox.json()["reviews"]:
                                review = ReviewRecord.model_validate(inbox.json()["reviews"][0])
                                break
                            await asyncio.sleep(0.05)
                    original = await records.get(root)
                    await worker.close()
                async with (
                    owned_redis(redis_uri, decode_responses=True) as redis,
                    authenticated_cookie(
                        redis, api.owner.id, settings.secret_key.get_secret_value()
                    ) as owner_cookie,
                    authenticated_cookie(
                        redis, "reviewer", settings.secret_key.get_secret_value()
                    ) as reviewer_cookie,
                    api_process(
                        settings,
                        tmp_path / "event-api-restarted.log",
                        listener=listener,
                        environment=managed_access_environment,
                    ) as http,
                ):
                    human = {"Cookie": "session=" + owner_cookie}
                    reviewer = {"Cookie": "session=" + reviewer_cookie}
                    # Redelivery of accepted work requires no live execution worker.
                    duplicate = await http.post(
                        "/api/program-events/deliveries", headers=bearer, json=event
                    )
                    assert duplicate.status_code == 202 and duplicate.json()["execution_id"] == root
                    assert (
                        await records.get(root)
                    ).workflow_access_approval == original.workflow_access_approval
                    assert (
                        await mongo_database.workflow_credential_material.count_documents({}) == 1
                    )
                    async with worker_process(
                        worker_settings,
                        tmp_path / "event-worker-restarted.log",
                        environment=managed_access_environment(str(http.base_url)),
                    ):
                        decision = await http.post(
                            f"/api/reviews/{review.review_id}/responses",
                            headers=reviewer,
                            json={
                                "key": "durable-event-review",
                                "expected_revision": review.revision,
                                "decision": "approve",
                                "data": {"feedback": "Reviewed after restart"},
                            },
                        )
                        assert decision.status_code == 200, decision.text
                        result = await http.get(f"/api/executions/{root}/result", headers=human)
                        assert (
                            result.status_code == 200 and result.json()["phase"] == "completed"
                        ), result.text
                        assert result.json()["context"]["engine_handle"] == original.engine_handle
                        children = await http.get(f"/api/executions/{root}/children", headers=human)
                        assert children.status_code == 200, children.text
                        for record in (
                            await records.get(root),
                            *map(ExecutionRecord.model_validate, children.json()),
                        ):
                            await replay(native, worker_settings, record.engine_handle)
                            history = await workflow_handle(
                                native, record.engine_handle
                            ).fetch_history()
                            assert source["credential"] not in str(history)
                            assert "lumora-review-v1." not in str(history)
                        fresh = await http.post(
                            "/api/program-events/deliveries",
                            headers=bearer,
                            json={
                                **event,
                                "event_id": "second",
                                "inputs": {"subject": "candidate-b"},
                            },
                        )
                        assert fresh.status_code == 202, fresh.text
                        second = fresh.json()["execution_id"]
                        assert second != root
                        async with asyncio.timeout(30):
                            while True:
                                inbox = await http.get("/api/reviews/inbox", headers=reviewer)
                                if any(
                                    row["root_execution_id"] == second
                                    for row in inbox.json()["reviews"]
                                ):
                                    break
                                await asyncio.sleep(0.05)
                        assert (
                            await http.post(f"/api/executions/{second}/cancel", headers=human)
                        ).status_code == 202
                        cancelled = await http.get(
                            f"/api/executions/{second}/result", headers=human
                        )
                        assert (
                            cancelled.status_code == 200
                            and cancelled.json()["phase"] == "cancelled"
                        ), cancelled.text
                        assert (
                            await http.delete(
                                f"/api/program-events/sources/{source['source']['source_id']}",
                                headers=human,
                            )
                        ).status_code == 204
                        async with asyncio.timeout(10):
                            while await mongo_database.workflow_credential_material.count_documents(
                                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
                            ):
                                await asyncio.sleep(0.05)
                        assert await mongo_database.program_reviews.count_documents({}) == 2
                        assert (
                            await mongo_database.workflow_credential_material.count_documents({})
                            == 2
                        )
                        assert not list(settings.workflow_credential_directory.rglob("*.json"))
                        for path in (
                            api.log,
                            tmp_path / "event-api-restarted.log",
                            tmp_path / "event-worker-first.log",
                            tmp_path / "event-worker-restarted.log",
                        ):
                            log = path.read_text()
                            assert (
                                source["credential"] not in log and "lumora-review-v1." not in log
                            )
    finally:
        async for row in mongo_database.program_executions.find({}, {"_id": 1}):
            record = await records.get(row["_id"])
            if record.submission != "accepted":
                continue
            handle = workflow_handle(native, record.engine_handle)
            if (await handle.describe()).status == WorkflowExecutionStatus.RUNNING:
                await handle.cancel()
                await handle.terminate(reason="Cleanup of owned event source test execution")
