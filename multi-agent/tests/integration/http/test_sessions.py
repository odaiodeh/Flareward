"""HTTP session contracts use application services and a real local runtime."""

import httpx
from inbound.http_api.app import create_app
from mas.core.identity import Identity
from mas.domain.programs.models import ApplicationDefinition
from support.scenarios import publish


async def test_fastapi_session_turn_uses_application_services_and_enforces_owner(
    platform, sessions
):
    revision = await publish(
        platform, "session-api", ApplicationDefinition(implementation="greeting", version="1")
    )
    owner = platform.owner

    async def authenticate(request):
        request.state.authenticated_user = "alice"
        return owner

    app = create_app(platform.programs, platform.executions, authenticate, sessions=sessions)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app),
        base_url="http://platform",
    ) as client:
        response = await client.post(
            "/api/sessions",
            json={"program": revision.reference.model_dump(), "interaction": "conversation"},
        )
        assert response.status_code == 201
        session_id = response.json()["run_id"]
        started = await client.post(
            f"/api/sessions/{session_id}/executions",
            json={
                "execution_id": "http-turn",
                "inputs": {"name": "HTTP", "user_prompt": "hello"},
            },
        )
        assert started.status_code == 202
        assert (await client.get("/api/executions/http-turn/result")).status_code == 200
        observed = await client.get(f"/api/sessions/{session_id}")
        assert observed.json()["status"] == "COMPLETED"
        assert observed.json()["last_result"] == {"answer": "hello HTTP"}
        assert observed.json()["graph_state"]["messages"][0]["sender_id"] == "alice"
        owner = Identity.user("other")
        assert (await client.get(f"/api/sessions/{session_id}")).status_code == 403
        assert (await client.get("/api/sessions")).json() == []
