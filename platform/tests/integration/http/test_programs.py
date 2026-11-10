"""FastAPI exercises real application services and the local runtime asynchronously."""

import httpx
import pytest
from support.program_authoring import assert_unfinished_program_lifecycle
from support.resource_snapshots import MemoryResourceSources, saved_resource_graph
from support.scenarios import publish

from lumora.api.app import create_app
from lumora.programs.domain.models import ApplicationDefinition, ProgramBody, ProgramDefinition
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize("injected", ["owner", "program_id"])
async def test_owned_body_cannot_smuggle_independent_identity_or_echo_private_input(
    platform, injected
):
    async def authenticate(request):
        return platform.owner

    app = create_app(platform.programs, platform.executions, authenticate)
    definition = ProgramDefinition(
        program_id="invalid-owned",
        name="Invalid owned identity",
        owner=platform.owner,
        implementation=ApplicationDefinition(
            implementation="composed",
            version="1",
            children={
                "greet": ProgramBody(
                    implementation=ApplicationDefinition(implementation="greeting", version="1")
                )
            },
        ),
    ).model_dump(mode="json")
    body = definition["implementation"]["children"]["greet"]
    body[injected] = "private-injected-identity"
    body["implementation"]["config"] = {"unexpected": "private-configuration-value"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        response = await http.put(
            "/api/programs/invalid-owned", json={"definition": definition, "expected_version": 0}
        )
    assert response.status_code == 422
    assert "private-injected-identity" not in response.text
    assert "private-configuration-value" not in response.text
    assert not (await platform.programs.list(platform.owner)).programs


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_unfinished_draft_validation_and_publication_use_one_lifecycle(platform, profile):
    async def authenticate(request):
        return platform.owner

    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        await assert_unfinished_program_lifecycle(http, platform.owner, profile=profile)
    with pytest.raises(KeyError):
        await platform.records.get("refused")


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
        saved = await client.put(
            "/api/programs/greeting",
            json={"definition": definition.model_dump(mode="json"), "expected_version": 0},
        )
        assert saved.status_code == 200
        revision = await client.post(
            "/api/programs/greeting/revisions", json={"expected_version": 1}
        )
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


async def test_invalid_root_inputs_are_private_and_refused_before_execution_admission(platform):
    async def authenticate(request):
        return platform.owner

    root = ProgramDefinition(
        program_id="typed-root",
        name="Typed root",
        owner=platform.owner,
        implementation=ApplicationDefinition(implementation="greeting", version="1"),
        input_schema={"type": "object", "properties": {"name": {"type": "integer"}}},
    )
    saved = await platform.programs.save(root, platform.owner)
    revision = await platform.programs.publish(
        root.program_id, platform.owner, expected_version=saved.version
    )
    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        response = await http.post(
            "/api/executions",
            json={
                "execution_id": "invalid-root-input",
                "program": revision.reference.model_dump(mode="json"),
                "inputs": {"name": "private-input-value"},
            },
        )
    assert response.status_code == 422
    assert "private-input-value" not in response.text
    with pytest.raises(KeyError):
        await platform.records.get("invalid-root-input")


async def test_nonfinite_json_is_rejected_instead_of_becoming_null_in_a_snapshot(platform):
    async def authenticate(request):
        return platform.owner

    revision = await publish(
        platform, "finite-input", ApplicationDefinition(implementation="greeting", version="1")
    )
    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        response = await http.post(
            "/api/executions",
            content=(
                '{"execution_id":"nonfinite",'
                '"program":{"program_id":"finite-input","revision":1},'
                '"inputs":{"name":NaN}}'
            ),
            headers={"Content-Type": "application/json"},
        )
    assert revision.revision == 1 and response.status_code == 422
    with pytest.raises(KeyError):
        await platform.records.get("nonfinite")


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
        assert (await client.get("/api/programs")).json()["programs"] == []
        assert (await client.get("/api/programs/private")).status_code == 403
        assert (await client.get("/api/programs/private/revisions")).status_code == 403
        assert (
            await client.post("/api/programs/private/validation", json={"expected_version": 1})
        ).status_code == 403
        denied_publish = await client.post(
            "/api/programs/private/revisions", json={"expected_version": 1}
        )
        assert denied_publish.status_code == 403


async def test_library_edits_and_publication_are_fenced_by_observed_version(platform):
    async def authenticate(request):
        return platform.owner

    app = create_app(platform.programs, platform.executions, authenticate)
    definition = ProgramDefinition(
        program_id="editable",
        name="Original",
        owner=platform.owner,
        implementation=ApplicationDefinition(implementation="greeting", version="1"),
    ).model_dump(mode="json")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        created = await http.put(
            "/api/programs/editable",
            json={
                "definition": definition,
                "expected_version": 0,
                "presentation": {"positions": {"call": {"x": 1, "y": 2}}},
            },
        )
        assert created.status_code == 200, created.text
        assert created.json()["version"] == 1
        first = await http.post("/api/programs/editable/revisions", json={"expected_version": 1})
        assert first.status_code == 201, first.text
        updated = await http.put(
            "/api/programs/editable",
            json={
                "definition": {**definition, "name": "Edited"},
                "expected_version": 1,
            },
        )
        assert updated.status_code == 200 and updated.json()["version"] == 2
        assert updated.json()["presentation"] == created.json()["presentation"]
        stale = await http.put(
            "/api/programs/editable",
            json={
                "definition": definition,
                "expected_version": 1,
            },
        )
        assert stale.status_code == 409
        assert (await http.get("/api/programs/editable")).json() == updated.json()
        retry = await http.post("/api/programs/editable/revisions", json={"expected_version": 1})
        assert retry.json() == first.json()
        published = await http.post(
            "/api/programs/editable/revisions", json={"expected_version": 2}
        )
        assert published.status_code == 201, published.text
        page = (await http.get("/api/programs", params={"limit": 1})).json()
        assert page["programs"][0]["name"] == "Edited"
        assert not (await http.get("/api/programs", params={"after": page["next_cursor"]})).json()[
            "programs"
        ]
        revisions = (await http.get("/api/programs/editable/revisions", params={"limit": 1})).json()
        older = (
            await http.get(
                "/api/programs/editable/revisions", params={"before": revisions["next_cursor"]}
            )
        ).json()
        assert older["revisions"][0]["program"]["revision"] == first.json()["revision"]
        assert (
            await http.post("/api/programs/editable/revisions", json={"expected_version": 99})
        ).status_code == 409
        assert (await http.post("/api/programs/editable/revisions")).status_code == 422


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


async def test_saved_resource_selection_requires_a_configured_source_without_creating_a_draft(
    platform,
):
    async def authenticate(request):
        return platform.owner

    graph = saved_resource_graph()
    source = MemoryResourceSources(platform.owner)
    definition = ProgramDefinition(
        program_id="unconfigured",
        name="Unconfigured source",
        owner=platform.owner,
        implementation=graph,
    )
    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        response = await http.put(
            "/api/programs/unconfigured",
            json={
                "definition": definition.model_dump(mode="json"),
                "expected_version": 0,
                "resource_selections": [
                    {"source": source.reference(graph.steps[0].element).model_dump(mode="json")}
                ],
            },
        )
        assert response.status_code == 503, response.text
        assert (await http.get("/api/programs/unconfigured")).status_code == 404


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
