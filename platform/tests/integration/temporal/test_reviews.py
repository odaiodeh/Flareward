"""Business review decisions and native waits survive independent API/worker lifetimes."""

import asyncio
import socket
from uuid import uuid4

import pytest
from support.feature_design import design_definition
from support.http_programs import publish_program
from support.identity import authenticated_cookie
from support.managed_access import managed_access_api, managed_access_environment
from support.review_api import pending_review, review_api, review_settings
from support.review_programs import review_body, review_definition, review_graph
from support.server import api_process
from support.temporal import replay, worker_process, workflow_handle
from temporalio.api.enums.v1 import EventType
from temporalio.client import WorkflowExecutionStatus

from lumora.bootstrap.settings.worker_settings import WorkerSettings
from lumora.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from lumora.executions.domain.access import WorkflowAccess
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import GraphDefinition, ProgramCallStep, ProgramDefinition
from lumora.services.connections.adapters.redis import owned_redis
from lumora.services.identity.domain import Identity
from lumora.services.reviews.domain.results import HumanReviewResult
from plugins.adlc.programs.design import DesignResult, FeatureRequest
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
        environment = {**api.operator_environment, "LUMORA_REVIEW_ENDPOINT": str(http.base_url)}
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


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("action", ["approve", "cancel"])
async def test_adlc_reviewer_dependency_recovers_and_continues_or_cancels(
    durable,
    application,
    mongo_database,
    redis_uri,
    tmp_path,
    profile,
    action,
):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    executions = MongoExecutionRepository(mongo_database)
    root = uuid4().hex
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        async with managed_access_api(
            mongo_database.name,
            redis_uri,
            tmp_path,
            host=durable.settings.host,
            listener=listener,
            application_modules=("plugins.adlc.programs.design", "support.feature_design"),
        ) as api:
            settings = api.settings
            worker = WorkerSettings.model_validate(settings.model_dump(mode="python"))
            environment = managed_access_environment(str(api.http.base_url))
            reviewer_program = await publish_program(
                api.http,
                ProgramDefinition(
                    program_id="reviewer",
                    name="Reusable graph reviewer",
                    owner=api.owner,
                    implementation=GraphDefinition(
                        steps=(
                            ProgramCallStep(
                                uid="review",
                                program=review_body(application.elements, profile),
                                inputs=PathBinding(path=("input",)),
                            ),
                        ),
                        entry="review",
                        exit="review",
                        outputs=PathBinding(path=("results", "review")),
                    ),
                    output_schema=HumanReviewResult.model_json_schema(),
                ),
                headers=api.human,
            )
            program = await publish_program(
                api.http,
                ProgramDefinition(
                    program_id="design",
                    name="Durable design",
                    owner=api.owner,
                    implementation=design_definition(
                        application.elements, profile, reviewer=reviewer_program
                    ),
                    input_schema=FeatureRequest.model_json_schema(),
                    output_schema=DesignResult.model_json_schema(),
                ),
                headers=api.human,
            )
            request = FeatureRequest(
                task="Implement a typed operation", acceptance_criteria=("Reject invalid input",)
            )
            async with worker_process(
                worker, tmp_path / "before-adlc-worker.log", environment=environment
            ):
                started = await api.http.post(
                    "/api/executions",
                    headers=api.human,
                    json={
                        "execution_id": root,
                        "program": program.model_dump(mode="json"),
                        "inputs": request.model_dump(mode="json"),
                        "workflow_access": [
                            WorkflowAccess(
                                purpose="review@1",
                                scope={
                                    "policies": ["release@1"],
                                    "actions": ["open", "read", "close"],
                                },
                                ttl_seconds=120,
                                renewable_for_seconds=300,
                            ).model_dump(mode="json")
                        ],
                    },
                )
                assert started.status_code == 202, started.text
                first = await pending_review(
                    api.http, root, api.human, api.reviewer, design_number=1
                )
                async with asyncio.timeout(30):
                    while True:
                        await api.http.get(f"/api/executions/{root}", headers=api.human)
                        rows = [
                            await executions.get(row["_id"])
                            async for row in mongo_database.program_executions.find({}, {"_id": 1})
                        ]
                        child = next(
                            (row for row in rows if row.execution_id == first.execution_id), None
                        )
                        if child is not None:
                            history = await workflow_handle(
                                durable.client, child.engine_handle
                            ).fetch_history()
                            if any(
                                event.event_type == EventType.EVENT_TYPE_TIMER_STARTED
                                for event in history.events
                            ):
                                break
                        await asyncio.sleep(0.05)
            # No execution worker is running when the human decision is persisted.
            path = f"/api/reviews/{first.review_id}/responses"
            decision = {
                "key": "revise-after-restart",
                "expected_revision": first.revision,
                "decision": "reject",
                "data": {"feedback": "Include input validation"},
            }
            accepted = await api.http.post(path, headers=api.reviewer, json=decision)
            assert accepted.status_code == 200, accepted.text
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
                tmp_path / "after-adlc-api.log",
                listener=listener,
                environment=managed_access_environment,
            ) as http,
        ):
            human, reviewer = (
                {"Cookie": "session=" + owner_cookie},
                {"Cookie": "session=" + reviewer_cookie},
            )
            repeated = await http.post(path, headers=reviewer, json=decision)
            assert (
                repeated.status_code == 200
                and repeated.json()["response"] == accepted.json()["response"]
            )
            async with worker_process(
                worker, tmp_path / "after-adlc-worker.log", environment=environment
            ):
                second = await pending_review(
                    http, root, human, reviewer, design_number=2, timeout=60
                )
                assert second.review_id != first.review_id
                assert second.specification.fingerprint != first.specification.fingerprint
                assert (
                    "Include input validation" in second.specification.subject["proposal"]["plan"]
                )
                stale = await http.post(
                    path, headers=reviewer, json={**decision, "decision": "approve"}
                )
                assert stale.status_code == 409, stale.text
                if action == "approve":
                    approved = await http.post(
                        f"/api/reviews/{second.review_id}/responses",
                        headers=reviewer,
                        json={
                            "key": "approve-revision-two",
                            "expected_revision": second.revision,
                            "decision": "approve",
                            "data": {"feedback": "Validated revision two"},
                        },
                    )
                    assert approved.status_code == 200, approved.text
                else:
                    cancelled = await http.post(f"/api/executions/{root}/cancel", headers=human)
                    assert cancelled.status_code == 202, cancelled.text
                async with asyncio.timeout(45):
                    while True:
                        observed = await http.get(f"/api/executions/{root}", headers=human)
                        assert observed.status_code == 200, observed.text
                        record = observed.json()
                        if record["phase"] in {"completed", "failed", "cancelled"}:
                            break
                        await asyncio.sleep(0.05)
                if action == "approve":
                    assert record["phase"] == "completed", record
                    output = DesignResult.model_validate(record["result"])
                    assert output.outcome == "approved"
                    assert output.design.number == 2
                    assert output.review.review.review_id == second.review_id
                    assert output.review.review.specification.subject == output.design.model_dump(
                        mode="json"
                    )
                    assert output.review.review.response.decision == "approve"
                else:
                    assert record["phase"] == "cancelled", record
                    async with asyncio.timeout(30):
                        while True:
                            closed = await http.get(
                                f"/api/reviews/{second.review_id}", headers=reviewer
                            )
                            assert closed.status_code == 200, closed.text
                            if closed.json()["status"] == "cancelled":
                                break
                            await asyncio.sleep(0.05)
                    refused = await http.post(
                        f"/api/reviews/{second.review_id}/responses",
                        headers=reviewer,
                        json={
                            "key": "late-approval",
                            "expected_revision": second.revision,
                            "decision": "approve",
                            "data": {"feedback": "Too late"},
                        },
                    )
                    assert refused.status_code == 409, refused.text
                rows = [
                    await executions.get(row["_id"])
                    async for row in mongo_database.program_executions.find({}, {"_id": 1})
                ]
                assert len(rows) == 7
                assert (
                    sum(row.program == reviewer_program and not row.body_path for row in rows) == 2
                )
                assert all(row.context.root_execution_id == root for row in rows)
                async with asyncio.timeout(30):
                    while True:
                        states = [
                            (
                                await workflow_handle(durable.client, row.engine_handle).describe()
                            ).status
                            for row in rows
                        ]
                        if all(state != WorkflowExecutionStatus.RUNNING for state in states):
                            break
                        await asyncio.sleep(0.05)
                view = await http.get(f"/api/executions/{root}/occurrences", headers=human)
                assert view.status_code == 200, view.text
                assert view.json()["execution_id"] == root
                direct = {row.execution_id for row in rows if row.parent_execution_id == root}
                observed_children = {
                    call["child_execution_id"]
                    for call in view.json()["occurrences"]
                    if call["kind"] == "program"
                }
                assert observed_children == direct
                if action == "approve":
                    assert view.json()["total"] == 6
                    assert all(call["status"] == "completed" for call in view.json()["occurrences"])
                for row in rows:
                    await replay(durable.client, worker, row.engine_handle)
    assert await mongo_database.program_reviews.count_documents({}) == 2
