"""Business review decisions and native waits survive independent API/worker lifetimes."""

import asyncio

import pytest
from support.identity import authenticated_cookie
from support.review_api import review_api, review_settings
from support.review_programs import review_definition, review_graph
from support.server import api_process
from support.temporal import replay, worker_process, workflow_handle
from temporalio.api.enums.v1 import EventType
from temporalio.client import WorkflowExecutionStatus

from flareward.bootstrap.settings.worker_settings import WorkerSettings
from flareward.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from flareward.services.connections.adapters.redis import owned_redis
from flareward.services.identity.domain import Identity
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS


@pytest.fixture(autouse=True)
async def cleanup_review_executions(mongo_database, durable):
    yield
    records = MongoExecutionRepository(mongo_database)
    async for document in mongo_database.program_executions.find({}, {"_id": 1}):
        record = await records.get(document["_id"])
        if record.submission != "accepted":
            continue
        handle = workflow_handle(durable.client, record.engine_handle)
        if (await handle.describe()).status == WorkflowExecutionStatus.RUNNING:
            # All worker contexts have exited; these identities belong to this test's database.
            await handle.cancel()
            await handle.terminate(reason="Cleanup of abandoned Human Review test execution")


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_review_decision_survives_api_and_worker_restart_and_native_replay(
    durable, application, mongo_database, redis_uri, tmp_path, profile
):
    owner = Identity.user("review-owner")
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    settings = review_settings(owner, mongo_database.name, redis_uri).model_copy(
        update={"host": durable.settings.host}
    )
    worker = WorkerSettings.model_validate(settings.model_dump(mode="python"))
    executions = MongoExecutionRepository(mongo_database)
    async with review_api(
        owner, mongo_database.name, redis_uri, tmp_path, settings=settings
    ) as api:
        definition = review_definition(application.elements, profile)
        definition.config["reconcile_seconds"] = 5
        review_program = await api.publish("durable-review", definition)
        workflow = await api.publish("durable-workflow", review_graph(review_program.reference))
        async with worker_process(
            worker, tmp_path / "before-worker.log", environment=api.operator_environment
        ):
            started = await api.http.post(
                "/api/executions",
                headers=api.human,
                json={
                    "execution_id": api.root,
                    "program": workflow.reference.model_dump(mode="json"),
                    "inputs": {"subject": "exact-candidate"},
                },
            )
            assert started.status_code == 202, started.text
            review = await api.pending()
            async with asyncio.timeout(20):
                while True:
                    children = await api.http.get(
                        f"/api/executions/{api.root}/children", headers=api.human
                    )
                    assert children.status_code == 200, children.text
                    records = children.json()
                    if records:
                        child = await executions.get(records[0]["execution_id"])
                        history = await workflow_handle(
                            durable.client, child.engine_handle
                        ).fetch_history()
                        if any(
                            event.event_type == EventType.EVENT_TYPE_TIMER_STARTED
                            for event in history.events
                        ):
                            break
                    await asyncio.sleep(0.05)
        response = {
            "key": "durable-human-decision",
            "expected_revision": review.revision,
            "decision": "approve",
            "data": {"feedback": "Reviewed while the execution worker was stopped"},
        }
        path = f"/api/reviews/{review.review_id}/responses"
        accepted = await api.http.post(path, headers=api.reviewer, json=response)
        assert accepted.status_code == 200, accepted.text
        assert (await api.http.get(f"/api/executions/{api.root}", headers=api.human)).json()[
            "phase"
        ] not in ("completed", "failed", "cancelled")

    async with (
        owned_redis(redis_uri, decode_responses=True) as redis,
        authenticated_cookie(
            redis, owner.id, settings.secret_key.get_secret_value()
        ) as owner_cookie,
        authenticated_cookie(
            redis, "reviewer", settings.secret_key.get_secret_value()
        ) as reviewer_cookie,
        api_process(settings, tmp_path / "after-api.log") as http,
    ):
        human = {"Cookie": "session=" + owner_cookie}
        reviewer = {"Cookie": "session=" + reviewer_cookie}
        repeated = await http.post(path, headers=reviewer, json=response)
        assert repeated.status_code == 200, repeated.text
        assert repeated.json()["response"] == accepted.json()["response"]
        environment = {**api.operator_environment, "FLAREWARD_REVIEW_ENDPOINT": str(http.base_url)}
        async with worker_process(worker, tmp_path / "after-worker.log", environment=environment):
            result = await http.get(f"/api/executions/{api.root}/result", headers=human)
            assert result.status_code == 200, result.text
            assert result.json()["phase"] == "completed", result.text
            output = result.json()["result"]["result"]
            assert output["reason"] == "resolved" and output["review"]["status"] == "decided"
            assert output["review"]["response"] == accepted.json()["response"]
            children = (
                await http.get(f"/api/executions/{api.root}/children", headers=human)
            ).json()
            for execution in (result.json(), *children):
                record = await executions.get(execution["execution_id"])
                await replay(durable.client, worker, record.engine_handle)
                history = await workflow_handle(
                    durable.client, record.engine_handle
                ).fetch_history()
                assert api.credential.get_secret_value() not in str(history)
    assert await mongo_database.program_reviews.count_documents({}) == 1
