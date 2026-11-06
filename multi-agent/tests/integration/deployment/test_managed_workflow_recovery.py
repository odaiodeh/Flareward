"""Automatic multi-purpose roots retain private authority across a live API restart."""

import asyncio
import json
import os
import socket
from contextlib import AsyncExitStack
from uuid import uuid4

import pytest
from mas.application.access.issuance import CredentialReservation
from mas.domain.execution.models import ExecutionRecord
from mas.domain.programs.models import ProgramDefinition
from mas.domain.reviews import ReviewRecord
from mas_plugins.reviews.specification import ELEMENT_SPECIFICATIONS as REVIEW_SPECIFICATIONS
from mas_plugins.verification.specification import (
    ELEMENT_SPECIFICATIONS as VERIFICATION_SPECIFICATIONS,
)
from outbound.mongo.execution_repository import MongoExecutionRepository
from outbound.redis_client import owned_redis
from runengine.adapters.coordination.config import TemporalHostConfig
from support.http_programs import publish_program
from support.identity import authenticated_cookie
from support.managed_access import managed_access_api, managed_access_environment
from support.managed_workflow import review_verification_graph, workflow_requirements
from support.review_programs import review_definition
from support.server import api_process
from support.temporal import replay, worker_process, workflow_handle
from support.verification import verification_request
from temporalio.client import Client, WorkflowExecutionStatus

from config.worker_settings import WorkerSettings


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_concurrent_multipurpose_roots_survive_api_restart_with_independent_cleanup(
    application, mongo_database, redis_uri, tmp_path, profile
):
    endpoint = os.environ.get("UNIFAI_TEST_TEMPORAL_ENDPOINT")
    if not endpoint:
        pytest.skip("Select the dedicated Temporal endpoint for running-root API recovery")
    for spec in (*REVIEW_SPECIFICATIONS, *VERIFICATION_SPECIFICATIONS):
        application.elements.register_spec_class(spec)
    host = TemporalHostConfig(endpoint=endpoint, task_queue="unifai-managed-" + uuid4().hex)
    native = await Client.connect(endpoint, namespace=host.namespace)
    records = MongoExecutionRepository(mongo_database)
    try:
        # Borrow the same listening socket for both API processes. Native receivers
        # keep their configured endpoint and the worker remains live throughout.
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
                            tmp_path / "managed-worker.log",
                            environment=managed_access_environment(str(api.http.base_url)),
                        )
                    )
                    review_program = await publish_program(
                        api.http,
                        ProgramDefinition(
                            program_id="managed-review",
                            name="Managed review",
                            owner=api.owner,
                            implementation=review_definition(application.elements, profile),
                        ),
                        headers=api.human,
                    )
                    workflow = await publish_program(
                        api.http,
                        ProgramDefinition(
                            program_id="managed-workflow",
                            name="Managed workflow",
                            owner=api.owner,
                            implementation=review_verification_graph(review_program, profile),
                        ),
                        headers=api.human,
                    )
                    requests = {
                        root: {
                            "execution_id": root,
                            "program": workflow.model_dump(mode="json"),
                            "inputs": {
                                "subject": verification_request(
                                    digest=letter * 64
                                ).subject.model_dump(mode="json")
                            },
                            "workflow_access": [
                                item.model_dump(mode="json") for item in workflow_requirements()
                            ],
                        }
                        for root, letter in (("cancelled-root", "a"), ("completed-root", "b"))
                    }
                    submitted = await asyncio.gather(
                        *(
                            api.http.post("/api/executions", headers=api.human, json=body)
                            for body in requests.values()
                            for _ in range(4)
                        )
                    )
                    assert all(response.status_code == 202 for response in submitted), [
                        (response.status_code, response.text) for response in submitted
                    ]
                    async with asyncio.timeout(30):
                        while True:
                            inbox = await api.http.get("/api/reviews/inbox", headers=api.reviewer)
                            assert inbox.status_code == 200, inbox.text
                            reviews = {
                                value.root_execution_id: value
                                for row in inbox.json()["reviews"]
                                if (value := ReviewRecord.model_validate(row))
                            }
                            if reviews.keys() == requests.keys():
                                break
                            for root in requests:
                                record = await records.get(root)
                                assert record.phase not in {"failed", "cancelled", "completed"}
                            await asyncio.sleep(0.05)
                    before = {root: await records.get(root) for root in requests}
                    material = {
                        row["_id"]: row
                        async for row in mongo_database.workflow_credential_material.find({})
                    }
                    assert len(material) == 4
                    by_root = {
                        root: [
                            key
                            for key, row in material.items()
                            if CredentialReservation.model_validate_json(
                                row["data"]
                            ).root_execution_id
                            == root
                        ]
                        for root in requests
                    }
                    assert all(len(keys) == 2 for keys in by_root.values())
                    for collection in (
                        mongo_database.review_access_grants,
                        mongo_database.verification_access_grants,
                    ):
                        assert await collection.count_documents({}) == 2
                    assert await mongo_database.program_reviews.count_documents({}) == 2
                    assert all(
                        value.workflow_access_approval is not None for value in before.values()
                    )
                worker.assert_running()
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
                        tmp_path / "managed-restarted-api.log",
                        listener=listener,
                        environment=managed_access_environment,
                    ) as http,
                ):
                    human = {"Cookie": "session=" + owner_cookie}
                    reviewer = {"Cookie": "session=" + reviewer_cookie}
                    recovered = await asyncio.gather(
                        *(
                            http.post("/api/executions", headers=human, json=body)
                            for body in requests.values()
                        )
                    )
                    assert all(response.status_code == 202 for response in recovered)
                    for root, original in before.items():
                        current = await records.get(root)
                        assert current.workflow_access_approval == original.workflow_access_approval
                        assert current.engine_handle == original.engine_handle
                    cancelled = await http.post(
                        "/api/executions/cancelled-root/cancel", headers=human
                    )
                    assert cancelled.status_code == 202, cancelled.text
                    result = await http.get("/api/executions/cancelled-root/result", headers=human)
                    assert result.status_code == 200 and result.json()["phase"] == "cancelled"
                    async with asyncio.timeout(10):
                        while await mongo_database.workflow_credential_material.count_documents(
                            {
                                "_id": {"$in": by_root["cancelled-root"]},
                                "$or": [{"retired": False}, {"cleanup_pending": True}],
                            }
                        ):
                            await asyncio.sleep(0.05)
                    assert (
                        await mongo_database.workflow_credential_material.count_documents(
                            {"_id": {"$in": by_root["completed-root"]}, "retired": False}
                        )
                        == 2
                    )
                    assert len(list(settings.workflow_credential_directory.rglob("*.json"))) == 2
                    review = reviews["completed-root"]
                    decision = await http.post(
                        f"/api/reviews/{review.review_id}/responses",
                        headers=reviewer,
                        json={
                            "key": "managed-human-response",
                            "expected_revision": review.revision,
                            "decision": "approve",
                            "data": {"feedback": "Reviewed after the API restart"},
                        },
                    )
                    assert decision.status_code == 200, decision.text
                    completed = await http.get(
                        "/api/executions/completed-root/result", headers=human
                    )
                    assert completed.status_code == 200, completed.text
                    execution = ExecutionRecord.model_validate(completed.json())
                    assert execution.phase == "completed"
                    assert (
                        completed.json()["result"]["result"]["review"]["response"]["decision"]
                        == "approve"
                    )
                    async with asyncio.timeout(10):
                        while await mongo_database.workflow_credential_material.count_documents(
                            {"$or": [{"retired": False}, {"cleanup_pending": True}]}
                        ):
                            await asyncio.sleep(0.05)
                    assert not list(settings.workflow_credential_directory.rglob("*.json"))
                    for root, body in requests.items():
                        duplicate = await http.post("/api/executions", headers=human, json=body)
                        assert duplicate.status_code == 202, duplicate.text
                        children = await http.get(f"/api/executions/{root}/children", headers=human)
                        assert children.status_code == 200, children.text
                        for record in (
                            await records.get(root),
                            *map(ExecutionRecord.model_validate, children.json()),
                        ):
                            await replay(native, worker_settings, record.engine_handle)
                    assert (
                        await mongo_database.workflow_credential_material.count_documents({}) == 4
                    )
                    assert await mongo_database.program_reviews.count_documents({}) == 2
                    for binding, original in material.items():
                        retired = await mongo_database.workflow_credential_material.find_one(
                            {"_id": binding}
                        )
                        assert retired["data"] == original["data"]
                        assert "credential" not in retired
                    portable = json.dumps([response.json() for response in submitted])
                    for log in (
                        api.log,
                        tmp_path / "managed-worker.log",
                        tmp_path / "managed-restarted-api.log",
                    ):
                        portable += log.read_text()
                    assert "unifai-review-v1." not in portable
                    assert "unifai-verification-v1." not in portable
    finally:
        # Only executions admitted into this test's isolated database are owned.
        async for row in mongo_database.program_executions.find({}, {"_id": 1}):
            record = await records.get(row["_id"])
            handle = workflow_handle(native, record.engine_handle)
            if (await handle.describe()).status == WorkflowExecutionStatus.RUNNING:
                await handle.cancel()
                await handle.terminate(reason="Cleanup of owned managed workflow test execution")
