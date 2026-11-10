"""Verification waiting survives an actual worker restart and native history replay."""

import asyncio

import pytest
from support.http_programs import publish_program
from support.scenarios import publish
from support.temporal import replay, worker_process, workflow_handle
from support.verification import verification_request
from support.verification_api import verification_api
from support.verification_programs import verification_graph, verification_wait_definition
from temporalio.api.enums.v1 import EventType

from lumora.executions.domain.models import ExecutionPhase, ExecutionRecord
from lumora.executions.models import StartExecution
from plugins.verification.elements.specification import ELEMENT_SPECIFICATIONS
from plugins.verification.programs.waiting import APPLICATION_PROGRAMS


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_verification_wait_recovers_after_worker_restart_without_verifier_credentials(
    durable, application, mongo_database, redis_uri, tmp_path, profile
):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)
    settings = durable.settings.model_copy(
        update={
            "application_modules": (
                *durable.settings.application_modules,
                "plugins.verification.programs.waiting",
            ),
            "element_modules": ("plugins.verification.elements.specification",),
        }
    )
    waiter = await publish(
        application,
        "durable-await-checks",
        verification_wait_definition(application.elements, profile, interval=5),
    )
    workflow = await publish(
        application, "durable-verification", verification_graph(waiter.reference, profile)
    )
    async with verification_api(
        application.owner, mongo_database, redis_uri, tmp_path, host=durable.settings.host
    ) as api:
        assert (
            await publish_program(api.http, waiter.definition, headers=api.human)
            == waiter.reference
        )
        reference = await publish_program(api.http, workflow.definition, headers=api.human)
        async with worker_process(
            settings, tmp_path / "before-worker.log", environment=api.operator_environment
        ):
            started = await api.http.post(
                "/api/executions",
                headers=api.human,
                json=StartExecution(
                    program=reference,
                    execution_id=api.root,
                    inputs={
                        "subject": verification_request().subject.model_dump(mode="json"),
                        "policy": "release@1",
                    },
                ).model_dump(mode="json"),
            )
            assert started.status_code == 202, started.text
            record = ExecutionRecord.model_validate(started.json())
            plan = await api.inspected_plan()
            async with asyncio.timeout(20):
                while True:
                    children = [
                        ExecutionRecord.model_validate(child)
                        for child in (
                            await api.http.get(
                                f"/api/executions/{record.execution_id}/children", headers=api.human
                            )
                        ).json()
                    ]
                    if children:
                        history = await workflow_handle(
                            durable.client, children[0].engine_handle
                        ).fetch_history()
                        if any(
                            event.event_type == EventType.EVENT_TYPE_TIMER_STARTED
                            and (
                                event.timer_started_event_attributes.start_to_fire_timeout.ToTimedelta().total_seconds()
                            )
                            >= 5
                            for event in history.events
                        ):
                            break
                    await asyncio.sleep(0.05)
        await api.attest(plan)
        async with worker_process(
            settings, tmp_path / "after-worker.log", environment=api.operator_environment
        ):
            async with asyncio.timeout(30):
                observed = await api.http.get(
                    f"/api/executions/{record.execution_id}/result", headers=api.human
                )
                assert observed.status_code == 200, observed.text
                result = ExecutionRecord.model_validate(observed.json())
            assert result.phase == ExecutionPhase.COMPLETED, result.failure
            output = result.result["result"]
            assert output["reason"] == "resolved" and output["polls"] >= 2
            assert output["verification"]["outcome"] == "accepted"
            assert output["verification"]["state"]["plan"]["plan_id"] == plan.plan_id
            children = [
                ExecutionRecord.model_validate(child)
                for child in (
                    await api.http.get(
                        f"/api/executions/{record.execution_id}/children", headers=api.human
                    )
                ).json()
            ]
            for execution in (result, *children):
                await replay(durable.client, settings, execution.engine_handle)
                history = await workflow_handle(
                    durable.client, execution.engine_handle
                ).fetch_history()
                assert api.credential.get_secret_value() not in str(history)
