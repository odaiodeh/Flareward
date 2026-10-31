"""A submitted session survives native FastAPI shutdown and resumes through durable ports."""

import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from inbound.http_api.app import create_app
from mas.programs.models import ApplicationDefinition, ProgramDefinition
from support.elements import element_registry
from temporalio.api.enums.v1 import EventType

from bootstrap.platform import compose_platform
from bootstrap.worker import compose_worker
from config.platform_settings import PlatformSettings


@asynccontextmanager
async def api(settings):
    app = create_app(
        services_factory=lambda: compose_platform(settings, elements=element_registry())
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://platform"
        ) as client:
            yield client


async def test_waiting_session_survives_api_restart_without_extra_root_or_graph_child(
    durable, application, mongo_database
):
    settings = PlatformSettings(
        host=durable.settings.host,
        storage="mongo",
        interactions="disabled",
        mongo_uri=os.environ["UNIFAI_TEST_MONGO_URI"],
        mongo_database=mongo_database.name,
        authentication="development",
        development_user=application.owner.id,
        application_modules=("support.programs",),
        reconcile_interval=0.05,
    )
    async with compose_worker(durable.settings):
        async with api(settings) as first:
            definition = ProgramDefinition(
                program_id="persistent-wait",
                name="Persistent wait",
                owner=application.owner,
                implementation=ApplicationDefinition(implementation="waiting", version="1"),
            )
            saved = await first.put(
                "/api/programs/persistent-wait", json=definition.model_dump(mode="json")
            )
            assert saved.status_code == 200, saved.text
            published = await first.post("/api/programs/persistent-wait/revisions")
            assert published.status_code == 201, published.text
            session = await first.post(
                "/api/sessions",
                json={
                    "program": {"program_id": definition.program_id, "revision": 1},
                },
            )
            assert session.status_code == 201, session.text
            session_id = session.json()["run_id"]
            admitted = await first.post(
                f"/api/sessions/{session_id}/executions", json={"execution_id": "persistent-turn"}
            )
            assert admitted.status_code == 202, admitted.text
            original = await first.get("/api/executions/persistent-turn")
            native_id = original.json()["context"]["engine_handle"]
            assert original.json()["phase"] == "running"
        # The API lifespan has closed its host and clients. The remote run is still live.
        moved = settings.model_copy(
            update={
                "host": settings.host.model_copy(
                    update={"task_queue": settings.host.task_queue + "-changed"}
                ),
                "reconcile_interval": 60,
            }
        )
        async with api(moved) as misplaced:
            for method, path, body in (
                ("get", "/api/executions/persistent-turn", None),
                ("get", "/api/executions/persistent-turn/result", None),
                (
                    "post",
                    f"/api/sessions/{session_id}/executions",
                    {"execution_id": "persistent-turn"},
                ),
                (
                    "post",
                    "/api/executions/persistent-turn/messages",
                    {"name": "answer", "data": "wrong-location"},
                ),
            ):
                response = await misplaced.request(method, path, json=body)
                assert response.status_code == 503, response.text
                assert response.json()["detail"]["code"] == "execution_location_unavailable"
        async with api(settings) as restarted:
            admitted = await restarted.post(
                f"/api/sessions/{session_id}/executions", json={"execution_id": "persistent-turn"}
            )
            assert admitted.status_code == 202, admitted.text
            original = await restarted.get("/api/executions/persistent-turn")
            assert original.json()["context"]["engine_handle"] == native_id
            async with asyncio.timeout(20):
                message = await restarted.post(
                    "/api/executions/persistent-turn/messages",
                    json={"name": "answer", "data": "recovered"},
                )
                assert message.status_code == 202, message.text
                result = await restarted.get("/api/executions/persistent-turn/result")
            assert result.json()["phase"] == "completed", result.text
            current = await restarted.get(f"/api/sessions/{session_id}")
            assert current.json()["last_result"] == {"answer": "recovered"}, current.text
            history = await durable.client.get_workflow_handle(native_id).fetch_history()
            assert not any(
                event.event_type == EventType.EVENT_TYPE_START_CHILD_WORKFLOW_EXECUTION_INITIATED
                for event in history.events
            )
