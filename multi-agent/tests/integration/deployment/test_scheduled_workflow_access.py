"""Real calendar/worker consent, durable review recovery, native replay and revocation."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from mas.domain.execution.models import ExecutionPhase
from mas.domain.programs.models import ProgramDefinition
from mas.domain.reviews import ReviewRecord
from mas_plugins.reviews.specification import ELEMENT_SPECIFICATIONS
from outbound.temporal.execution_observation import TemporalExecutionObservation
from runengine.adapters.coordination.config import TemporalHostConfig
from runengine.adapters.coordination.temporal.models import TemporalRunIdentity
from support.calendar import CalendarDeployment, wait_calendar
from support.http_programs import publish_program
from support.managed_access import managed_access_api
from support.review_programs import review_definition
from support.temporal import replay, worker_process
from temporalio.client import Client, ScheduleActionExecutionStartWorkflow

from config.worker_settings import WorkerSettings


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_scheduled_consent_survives_worker_restart_and_rejects_revoked_ticks(
    application, mongo_database, redis_uri, tmp_path, profile
):
    endpoint = os.environ.get("UNIFAI_TEST_TEMPORAL_ENDPOINT")
    if not endpoint:
        pytest.skip("Select the dedicated Temporal endpoint for scheduled workflow access")
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    host = TemporalHostConfig(endpoint=endpoint, task_queue="unifai-consent-" + uuid4().hex)
    async with managed_access_api(mongo_database.name, redis_uri, tmp_path, host=host) as api:
        worker = WorkerSettings.model_validate(api.settings.model_dump(mode="python"))
        native = await Client.connect(endpoint, namespace=host.namespace)
        deployment = CalendarDeployment(api.settings, worker, native)
        environment = {
            "UNIFAI_REVIEW_ENDPOINT": str(api.http.base_url),
            "UNIFAI_REVIEW_ALLOW_INSECURE": "true",
        }
        async with worker_process(
            worker, tmp_path / "worker-first.log", environment=environment
        ) as first_worker:
            try:
                reference = await publish_program(
                    api.http,
                    ProgramDefinition(
                        program_id="scheduled-review",
                        name="Scheduled review",
                        owner=api.owner,
                        implementation=review_definition(application.elements, profile),
                    ),
                    headers=api.human,
                )
                body = {
                    "session": {"program": reference.model_dump(mode="json")},
                    "inputs": {"subject": {"candidate": "scheduled-candidate"}},
                    "schedule": {"interval": "P1D", "enabled": False},
                    "workflow_access": {
                        "requirements": [
                            {
                                "purpose": "review@1",
                                "scope": {
                                    "policies": ["release@1"],
                                    "actions": ["open", "read", "close"],
                                },
                                "ttl_seconds": 60,
                                "renewable_for_seconds": 180,
                            }
                        ],
                        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                    },
                }
                denied = await api.http.post(
                    "/api/program-schedules",
                    headers={**api.human, "Authorization": "Bearer untrusted-token"},
                    json=body,
                )
                assert denied.status_code == 401, denied.text
                assert await mongo_database.workflow_consents.count_documents({}) == 0
                created = await api.http.post(
                    "/api/program-schedules",
                    headers={**api.human, "Idempotency-Key": "scheduled-consent"},
                    json=body,
                )
                assert created.status_code == 201, created.text
                view = created.json()
                schedule_id = view["definition"]["schedule_id"]
                deployment.schedule_ids.append(schedule_id)
                consent = view["workflow_access_consent"]
                assert consent["approved_by"]["id"] == api.owner.id
                assert consent["consent_id"] == view["authorization_id"]
                assert await mongo_database.workflow_credential_material.count_documents({}) == 0
                assert (
                    await api.http.post(
                        f"/api/program-schedules/{schedule_id}/trigger", headers=api.human
                    )
                ).status_code == 202
                async with asyncio.timeout(30):
                    while True:
                        inbox = await api.http.get("/api/reviews/inbox", headers=api.reviewer)
                        assert inbox.status_code == 200, inbox.text
                        if inbox.json()["reviews"]:
                            review = ReviewRecord.model_validate(inbox.json()["reviews"][0])
                            break
                        runs = await api.http.get(
                            f"/api/program-schedules/{schedule_id}/runs", headers=api.human
                        )
                        assert runs.status_code == 200, runs.text
                        assert not any(
                            row["status"] in {"FAILED", "CANCELLED"} for row in runs.json()
                        ), runs.text
                        await asyncio.sleep(0.05)
                root = review.root_execution_id
                record = (await api.http.get(f"/api/executions/{root}", headers=api.human)).json()
                assert record["workflow_access_approval"]["consent_id"] == consent["consent_id"]
                assert record["workflow_access_approval"]["approved_at"] == consent["approved_at"]
                await first_worker.close()
                decision_task = asyncio.create_task(
                    api.http.post(
                        f"/api/reviews/{review.review_id}/responses",
                        headers=api.reviewer,
                        json={
                            "key": "scheduled-human-response",
                            "expected_revision": review.revision,
                            "decision": "approve",
                            "data": {"feedback": "Reviewed this exact scheduled candidate"},
                        },
                    )
                )
                async with worker_process(
                    worker, tmp_path / "worker-restarted.log", environment=environment
                ):
                    decision = await decision_task
                    assert decision.status_code == 200, decision.text
                    result = await api.http.get(f"/api/executions/{root}/result", headers=api.human)
                    assert result.status_code == 200 and result.json()["phase"] == "completed", (
                        result.text
                    )
                    assert result.json()["result"]["review"]["response"]["decision"] == "approve"
                    await replay(native, worker, result.json()["context"]["engine_handle"])
                    async with asyncio.timeout(10):
                        while await mongo_database.workflow_credential_material.count_documents(
                            {"$or": [{"retired": False}, {"cleanup_pending": True}]}
                        ):
                            await asyncio.sleep(0.05)
                    assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
                    revoked = await api.http.delete(
                        f"/api/program-schedules/{schedule_id}/workflow-access", headers=api.human
                    )
                    assert revoked.status_code == 204, revoked.text
                    assert (
                        await api.http.post(
                            f"/api/program-schedules/{schedule_id}/trigger", headers=api.human
                        )
                    ).status_code == 403
                    handle = native.get_schedule_handle("unifai-program-schedule-" + schedule_id)
                    # Even a direct native trigger cannot bypass persisted revocation.
                    await handle.trigger()
                    description = await wait_calendar(
                        handle,
                        lambda value: (
                            len(value.info.recent_actions) >= 2 and not value.info.running_actions
                        ),
                    )
                    latest = description.info.recent_actions[-1].action
                    assert isinstance(latest, ScheduleActionExecutionStartWorkflow)
                    refused_identity = TemporalRunIdentity(
                        namespace=host.namespace,
                        workflow_id=latest.workflow_id,
                        run_id=latest.first_execution_run_id,
                    )
                    assert (
                        await TemporalExecutionObservation(host, native).status(
                            refused_identity.encode()
                        )
                        == ExecutionPhase.FAILED
                    )
                    assert (
                        await mongo_database.workflow_credential_material.count_documents({}) == 1
                    )
                    assert await mongo_database.program_reviews.count_documents({}) == 1
                    assert "unifai-review-v1." not in api.log.read_text()
            finally:
                await deployment.close_schedules()
