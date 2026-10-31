"""Real calendar actions, separate API/worker processes, and durable business records."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from mas.core.identity import Identity
from mas.programs.models import ApplicationDefinition, ProgramDefinition
from mas.scheduling.models import PromptSource, ScheduleDefinition, ScheduleOverlapPolicy
from mas.scheduling.programs import ProgramScheduleConflict, program_schedule_id
from outbound.temporal.program_schedules import TemporalProgramSchedules
from run_engine.scheduling import ScheduledProgramInput
from runengine.adapters.coordination.temporal.host import TemporalRunHost
from runengine.adapters.coordination.temporal.models import RunParameters
from runengine.core.refs import FunctionRef
from support.calendar import CalendarReadBarrier, wait_calendar, wait_schedule_runs
from support.http_programs import publish_program
from support.scenarios import echo_graph
from support.scheduling import schedule_request
from support.server import api_process
from support.temporal import replay
from temporalio.client import Client

from bootstrap.scheduling import admit_scheduled_execution


@pytest.mark.parametrize("kind", ["graph", "process", "application", "composed"])
async def test_scheduled_program_runs_in_owning_engine_run_across_api_restart(
    calendar_deployment, tmp_path, kind
):
    deployment = calendar_deployment
    implementation = (
        echo_graph("process" if kind == "process" else "thread")
        if kind in {"graph", "process"}
        else ApplicationDefinition(implementation="greeting", version="1")
    )
    async with api_process(deployment.settings, tmp_path / "api.log") as http:
        if kind == "composed":
            leaf = await publish_program(
                http,
                ProgramDefinition(
                    program_id="leaf",
                    name="Scheduled child",
                    owner=Identity.user("owner"),
                    implementation=ApplicationDefinition(implementation="greeting", version="1"),
                ),
            )
            implementation = ApplicationDefinition(
                implementation="composed", version="1", children={"greet": leaf}
            )
        reference = await publish_program(
            http,
            ProgramDefinition(
                program_id="scheduled",
                name="Scheduled program",
                owner=Identity.user("owner"),
                implementation=implementation,
            ),
        )
        request = schedule_request(reference)
        request_key = uuid4().hex
        headers = {"Idempotency-Key": request_key}
        schedule_id = program_schedule_id(Identity.user("owner"), request_key)
        deployment.schedule_ids.append(schedule_id)
        created = await http.post(
            "/api/program-schedules", json=request.model_dump(mode="json"), headers=headers
        )
        assert created.status_code == 201, created.text
        assert created.json()["definition"]["schedule_id"] == schedule_id
        retried = await http.post(
            "/api/program-schedules", json=request.model_dump(mode="json"), headers=headers
        )
        assert retried.status_code == 201 and retried.json() == created.json(), retried.text
        conflict = await http.post(
            "/api/program-schedules",
            json=request.model_copy(update={"inputs": {"name": "different"}}).model_dump(
                mode="json"
            ),
            headers=headers,
        )
        assert conflict.status_code == 409, conflict.text
        replacement = await publish_program(
            http,
            ProgramDefinition(
                program_id="scheduled",
                name="Replacement program",
                owner=Identity.user("owner"),
                implementation=ApplicationDefinition(
                    implementation="greeting", version="1", config={"prefix": "replacement:"}
                ),
            ),
        )
        assert replacement.revision == 2
        triggered = await http.post(f"/api/program-schedules/{schedule_id}/trigger")
        assert triggered.status_code == 202, triggered.text
        runs = await wait_schedule_runs(http, schedule_id, 1)
        expected = "greeting:scheduled" if kind in {"graph", "process"} else "hello scheduled"
        assert runs[0]["last_result"]["answer"] == expected
        first_id = runs[0]["active_execution_id"]
        assert runs[0]["run_context"]["root_execution_id"] == first_id
        assert runs[0]["run_context"]["parent_execution_id"] is None
        children = (await http.get(f"/api/executions/{first_id}/children")).json()
        assert len(children) == (1 if kind == "composed" else 0)
        for child in children:
            assert child["parent_execution_id"] == first_id
            host = TemporalRunHost(deployment.worker.host, client=deployment.native)
            handle = await host.get_handle(child["context"]["engine_handle"])
            assert (await handle.status()).parent_run_id == runs[0]["run_context"]["engine_handle"]
            await replay(deployment.native, deployment.worker, child["context"]["engine_handle"])
        await replay(deployment.native, deployment.worker, runs[0]["run_context"]["engine_handle"])
    # The calendar and worker continue while the HTTP process is absent.
    native_schedule = deployment.native.get_schedule_handle(
        "unifai-program-schedule-" + schedule_id
    )
    await native_schedule.trigger()
    async with asyncio.timeout(30):
        while True:
            native = await native_schedule.describe()
            if len(native.info.recent_actions) == 2 and not native.info.running_actions:
                break
            await asyncio.sleep(0.05)
    async with api_process(deployment.settings, tmp_path / "restarted-api.log") as http:
        runs = await wait_schedule_runs(http, schedule_id, 2)
        assert len({run["run_id"] for run in runs}) == 2
        assert first_id in {run["active_execution_id"] for run in runs}
        assert all(run["metadata"]["schedule_id"] == schedule_id for run in runs)
        assert all(run["program"]["revision"] == 1 for run in runs)
        assert all(run["last_result"]["answer"] == expected for run in runs)
        assert all(run["run_context"]["parent_execution_id"] is None for run in runs)
        for run in runs:
            await replay(deployment.native, deployment.worker, run["run_context"]["engine_handle"])


async def test_automatic_schedule_exhausts_and_rearms_its_finite_budget(
    calendar_deployment, tmp_path
):
    deployment = calendar_deployment
    async with api_process(deployment.settings, tmp_path / "api.log") as http:
        reference = await publish_program(
            http,
            ProgramDefinition(
                program_id="automatic",
                name="Automatic program",
                owner=Identity.user("owner"),
                implementation=ApplicationDefinition(implementation="greeting", version="1"),
            ),
        )
        request = schedule_request(reference, enabled=True)
        request = request.model_copy(
            update={
                "schedule": ScheduleDefinition(
                    interval=timedelta(minutes=1),
                    start_at=datetime.now(UTC) + timedelta(seconds=3),
                    end_at=datetime.now(UTC) + timedelta(seconds=30),
                    remaining_actions=1,
                    timezone="Asia/Jerusalem",
                )
            }
        )
        created = await http.post("/api/program-schedules", json=request.model_dump(mode="json"))
        assert created.status_code == 201, created.text
        schedule_id = created.json()["definition"]["schedule_id"]
        deployment.schedule_ids.append(schedule_id)
        runs = await wait_schedule_runs(http, schedule_id, 1)
        assert runs[0]["status"] == "COMPLETED"
        exhausted = (await http.get(f"/api/program-schedules/{schedule_id}")).json()
        assert exhausted["status"] == "completed" and exhausted["remaining_actions"] == 0
        assert exhausted["total_runs"] == 1
        assert (await http.post(f"/api/program-schedules/{schedule_id}/trigger")).status_code == 202
        manual = await wait_schedule_runs(http, schedule_id, 2)
        assert len({run["run_id"] for run in manual}) == 2
        still_exhausted = (await http.get(f"/api/program-schedules/{schedule_id}")).json()
        assert (
            still_exhausted["status"] == "completed" and still_exhausted["remaining_actions"] == 0
        )
        rearmed = request.model_copy(
            update={
                "schedule": request.schedule.model_copy(
                    update={"start_at": datetime.now(UTC) + timedelta(seconds=3)}
                )
            }
        )
        updated = await http.put(
            f"/api/program-schedules/{schedule_id}",
            json={"request": rearmed.model_dump(mode="json"), "expected_version": 1},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["definition"]["version"] == 2
        stale = await http.put(
            f"/api/program-schedules/{schedule_id}",
            json={"request": rearmed.model_dump(mode="json"), "expected_version": 1},
        )
        assert stale.status_code == 409
        runs = await wait_schedule_runs(http, schedule_id, 3)
        assert len({run["run_id"] for run in runs}) == 3
        exhausted = (await http.get(f"/api/program-schedules/{schedule_id}")).json()
        assert exhausted["status"] == "completed" and exhausted["total_runs"] == 1
        for run in runs:
            await replay(deployment.native, deployment.worker, run["run_context"]["engine_handle"])


@pytest.mark.parametrize("policy", list(ScheduleOverlapPolicy))
async def test_native_overlap_policy_controls_running_programs(
    calendar_deployment, tmp_path, policy
):
    deployment = calendar_deployment
    async with api_process(deployment.settings, tmp_path / "api.log") as http:
        reference = await publish_program(
            http,
            ProgramDefinition(
                program_id="overlap",
                name="Overlapping waits",
                owner=Identity.user("owner"),
                implementation=ApplicationDefinition(implementation="waiting", version="1"),
            ),
        )
        request = schedule_request(reference)
        request = request.model_copy(
            update={"schedule": request.schedule.model_copy(update={"overlap_policy": policy})}
        )
        created = await http.post("/api/program-schedules", json=request.model_dump(mode="json"))
        assert created.status_code == 201, created.text
        schedule_id = created.json()["definition"]["schedule_id"]
        deployment.schedule_ids.append(schedule_id)
        prefix = f"/api/program-schedules/{schedule_id}"
        assert (await http.post(prefix + "/trigger")).status_code == 202
        first = (await wait_schedule_runs(http, schedule_id, 1, terminal=False))[0]
        assert (await http.post(prefix + "/trigger")).status_code == 202
        native = deployment.native.get_schedule_handle("unifai-program-schedule-" + schedule_id)
        if policy == ScheduleOverlapPolicy.SKIP:
            await wait_calendar(native, lambda state: state.info.num_actions_skipped_overlap == 1)
        elif policy == ScheduleOverlapPolicy.BUFFER_ONE:
            await wait_calendar(native, lambda state: state.raw_description.info.buffer_size == 1)
        if policy != ScheduleOverlapPolicy.CANCEL_OTHER:
            delivered = await http.post(
                f"/api/executions/{first['active_execution_id']}/messages",
                json={"name": "answer", "data": "first"},
            )
            assert delivered.status_code == 202, delivered.text
        count = 1 if policy == ScheduleOverlapPolicy.SKIP else 2
        runs = await wait_schedule_runs(http, schedule_id, count, terminal=False)
        if count == 2:
            second = next(run for run in runs if run["run_id"] != first["run_id"])
            delivered = await http.post(
                f"/api/executions/{second['active_execution_id']}/messages",
                json={"name": "answer", "data": "second"},
            )
            assert delivered.status_code == 202, delivered.text
        runs = await wait_schedule_runs(http, schedule_id, count)
        expected = (
            ["CANCELLED", "COMPLETED"]
            if policy == ScheduleOverlapPolicy.CANCEL_OTHER
            else ["COMPLETED"] * count
        )
        assert sorted(run["status"] for run in runs) == expected
        for run in runs:
            await replay(deployment.native, deployment.worker, run["run_context"]["engine_handle"])


async def test_native_schedule_update_fences_concurrent_writers(calendar_deployment, tmp_path):
    deployment = calendar_deployment
    async with api_process(deployment.settings, tmp_path / "api.log") as http:
        reference = await publish_program(
            http,
            ProgramDefinition(
                program_id="concurrent",
                name="Concurrent schedule edits",
                owner=Identity.user("owner"),
                implementation=ApplicationDefinition(implementation="greeting", version="1"),
            ),
        )
        created = await http.post(
            "/api/program-schedules", json=schedule_request(reference).model_dump(mode="json")
        )
        assert created.status_code == 201, created.text
        schedule_id = created.json()["definition"]["schedule_id"]
        deployment.schedule_ids.append(schedule_id)
        native = await deployment.native.get_schedule_handle(
            "unifai-program-schedule-" + schedule_id
        ).describe()
        arguments = await deployment.native.data_converter.decode(native.schedule.action.args)
        parameters = RunParameters.model_validate(arguments[0])
        action = ScheduledProgramInput.model_validate(parameters.request.input)
        registration = action.registration.model_copy(
            update={"definition": action.registration.definition.model_copy(update={"version": 2})}
        )
        competing = registration.model_copy(
            update={
                "definition": registration.definition.model_copy(
                    update={
                        "request": registration.definition.request.model_copy(
                            update={"source": PromptSource.SHORTCUT_COPY}
                        )
                    }
                )
            }
        )
        assert native.raw_description.conflict_token, "Calendar server returned no update token"
        controlled = Client(
            deployment.native.service_client,
            namespace=deployment.native.namespace,
            interceptors=[CalendarReadBarrier()],
        )
        backend = TemporalProgramSchedules(
            deployment.settings.host,
            FunctionRef.from_callable(admit_scheduled_execution),
            client=controlled,
        )
        async with asyncio.timeout(15):
            outcomes = await asyncio.gather(
                backend.replace(competing, expected_version=1, restart=False),
                backend.replace(registration, expected_version=1, restart=False),
                return_exceptions=True,
            )
        assert sum(outcome is None for outcome in outcomes) == 1, outcomes
        assert sum(isinstance(outcome, ProgramScheduleConflict) for outcome in outcomes) == 1, (
            outcomes
        )
        assert (await http.get(f"/api/program-schedules/{schedule_id}")).json()["definition"][
            "version"
        ] == 2


async def test_manual_runs_preserve_timer_budget_and_history_after_deletion(
    calendar_deployment, tmp_path
):
    deployment = calendar_deployment
    async with api_process(deployment.settings, tmp_path / "api.log") as http:
        reference = await publish_program(
            http,
            ProgramDefinition(
                program_id="manual-budget",
                name="Manual budget",
                owner=Identity.user("owner"),
                implementation=ApplicationDefinition(implementation="greeting", version="1"),
            ),
        )
        request = schedule_request(reference)
        request = request.model_copy(
            update={"schedule": request.schedule.model_copy(update={"remaining_actions": 3})}
        )
        created = await http.post("/api/program-schedules", json=request.model_dump(mode="json"))
        assert created.status_code == 201, created.text
        schedule_id = created.json()["definition"]["schedule_id"]
        deployment.schedule_ids.append(schedule_id)
        prefix = f"/api/program-schedules/{schedule_id}"
        async with asyncio.timeout(30):
            while True:
                listed = await http.get("/api/program-schedules")
                assert listed.status_code == 200, listed.text
                if any(item["definition"]["schedule_id"] == schedule_id for item in listed.json()):
                    break
                await asyncio.sleep(0.1)
        backend = TemporalProgramSchedules(
            deployment.settings.host,
            FunctionRef.from_callable(admit_scheduled_execution),
            client=deployment.native,
        )
        with pytest.raises(PermissionError):
            await backend.get(schedule_id, Identity.user("other"))
        resumed = await http.post(prefix + "/resume")
        assert resumed.status_code == 200 and resumed.json()["status"] == "active", resumed.text
        paused = await http.post(prefix + "/pause")
        assert paused.status_code == 200 and paused.json()["status"] == "paused", paused.text
        assert (await http.post(prefix + "/trigger")).status_code == 202
        await wait_schedule_runs(http, schedule_id, 1)
        changed = request.model_copy(update={"source": PromptSource.SHORTCUT_COPY})
        updated = await http.put(
            prefix, json={"request": changed.model_dump(mode="json"), "expected_version": 1}
        )
        assert updated.status_code == 200 and updated.json()["remaining_actions"] == 3, updated.text
        assert (await http.post(prefix + "/trigger")).status_code == 202
        runs = await wait_schedule_runs(http, schedule_id, 2)
        assert len({run["active_execution_id"] for run in runs}) == 2
        assert (await http.delete(prefix)).status_code == 204
        assert (await http.get(prefix)).status_code == 404
        for run in runs:
            response = await http.get(f"/api/sessions/{run['run_id']}")
            assert (
                response.status_code == 200 and response.json()["last_result"] == run["last_result"]
            )
