"""FastAPI exercises real application services and the local runtime asynchronously."""

import httpx
from inbound.http_api.app import create_app
from mas.core.identity import Identity
from mas.programs.models import ApplicationDefinition, ProgramDefinition
from support.scenarios import publish


async def test_api_publishes_submits_and_returns_program_result(platform):
    async def authenticate(request):
        return platform.owner

    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as client:
        definition = ProgramDefinition(
            program_id="greeting",
            name="Greeting",
            owner=platform.owner,
            implementation=ApplicationDefinition(implementation="greeting", version="1"),
        )
        saved = await client.put("/api/programs/greeting", json=definition.model_dump(mode="json"))
        assert saved.status_code == 200
        revision = await client.post("/api/programs/greeting/revisions")
        assert revision.status_code == 201
        submitted = await client.post(
            "/api/executions",
            json={
                "program": {"program_id": "greeting", "revision": 1},
                "inputs": {"name": "FastAPI"},
                "execution_id": "api-run",
            },
        )
        assert submitted.status_code == 202
        result = await client.get("/api/executions/api-run/result")
        assert result.status_code == 200
        assert result.json()["result"] == {"answer": "hello FastAPI"}
        events = await client.get("/api/executions/api-run/events")
        assert events.status_code == 200
        assert "data: " in events.text


async def test_api_authorization_and_missing_resources(platform):
    revision = await publish(
        platform, "private", ApplicationDefinition(implementation="greeting", version="1")
    )

    async def authenticate(request):
        return Identity.user("someone-else")

    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as client:
        denied = await client.get("/api/programs/private/revisions/1")
        assert denied.status_code == 403
        missing = await client.get("/api/programs/missing/revisions/1")
        assert missing.status_code == 404
        denied_submit = await client.post(
            "/api/executions",
            json={
                "program": revision.reference.model_dump(mode="json"),
                "inputs": {"name": "x"},
            },
        )
        assert denied_submit.status_code == 403


async def test_api_cancels_a_waiting_program(platform):
    revision = await publish(
        platform, "wait", ApplicationDefinition(implementation="waiting", version="1")
    )

    async def authenticate(request):
        return platform.owner

    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as client:
        submitted = await client.post(
            "/api/executions",
            json={
                "program": revision.reference.model_dump(mode="json"),
                "execution_id": "cancel-api",
            },
        )
        assert submitted.status_code == 202
        cancelled = await client.post("/api/executions/cancel-api/cancel")
        assert cancelled.status_code == 202
        result = await client.get("/api/executions/cancel-api/result")
        assert result.status_code == 200
        assert result.json()["phase"] == "cancelled"


async def test_api_rejects_unknown_fields(platform):
    async def authenticate(request):
        return platform.owner

    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as client:
        response = await client.post("/api/executions", json={"unexpected": True})
        assert response.status_code == 422


async def test_blueprint_import_requires_configured_library(platform):
    async def authenticate(request):
        return platform.owner

    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as client:
        response = await client.put(
            "/api/programs/imported/blueprint", json={"blueprint_id": "stored-blueprint"}
        )
        assert response.status_code == 503


async def test_child_records_are_owner_scoped_and_cannot_be_adopted_as_root_submissions(platform):
    leaf = await publish(
        platform, "leaf", ApplicationDefinition(implementation="greeting", version="1")
    )
    parent = await publish(
        platform,
        "parent",
        ApplicationDefinition(
            implementation="composed",
            version="1",
            children={"greet": leaf.reference},
        ),
    )

    async def authenticate(request):
        return platform.owner

    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        submitted = await http.post(
            "/api/executions",
            json={
                "program": parent.reference.model_dump(mode="json"),
                "execution_id": "parent-run",
                "session_id": "chat",
                "inputs": {"name": "child"},
            },
        )
        assert submitted.status_code == 202, submitted.text
        await http.get("/api/executions/parent-run/result")
        children = await http.get("/api/executions/parent-run/children")
        assert children.status_code == 200, children.text
        assert len(children.json()) == 1
        child = children.json()[0]
        assert child["parent_execution_id"] == "parent-run" and child["session_id"] == "chat"
        assert child["result"] == {"answer": "hello child"}
        adopted = await http.post(
            "/api/executions",
            json={
                "program": leaf.reference.model_dump(mode="json"),
                "execution_id": child["execution_id"],
                "session_id": "chat",
                "inputs": {"name": "child"},
            },
        )
        assert adopted.status_code == 422, adopted.text

    async def another_owner(request):
        return Identity.user("another-owner")

    other = create_app(platform.programs, platform.executions, another_owner)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(other), base_url="http://platform"
    ) as http:
        assert (await http.get("/api/executions/parent-run/children")).status_code == 403
        assert (await http.get(f"/api/executions/{child['execution_id']}")).status_code == 403
