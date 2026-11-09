"""Real HTTP, cookie/Redis identity, Mongo authoring, and a separately deployed Temporal worker."""

import os
import time
from uuid import uuid4

import pytest
from pydantic import SecretStr
from runengine.adapters.coordination.config import TemporalHostConfig
from support.blueprints import external_blueprint
from support.identity import session_cookie
from support.server import api_process
from support.temporal import replay, worker_process
from temporalio.client import Client

from flareward.bootstrap.settings.interaction_settings import InteractionBackend
from flareward.bootstrap.settings.platform_settings import AuthenticationKind
from flareward.bootstrap.settings.worker_settings import WorkerSettings
from flareward.programs.domain.models import ApplicationDefinition, PathBinding, ProgramDefinition
from flareward.programs.graph.state.graph_state import GraphState
from flareward.services.connections.adapters.redis import owned_redis
from flareward.services.identity.domain import Identity
from flareward.services.interactions.adapters.wire import root_key


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_deployed_authoring_session_restart_messages_and_cancellation(
    secret_settings, mongo_database, tmp_path, profile
):
    endpoint, redis_uri = (
        os.environ.get(name)
        for name in ("FLAREWARD_TEST_TEMPORAL_ENDPOINT", "FLAREWARD_TEST_REDIS_URI")
    )
    if not endpoint or not redis_uri:
        pytest.skip("Set Temporal, Mongo, and Redis test services for deployment E2E")
    secret = "network-cookie-secret"
    token = "network-private-configuration"
    settings = secret_settings.model_copy(
        update={
            "host": TemporalHostConfig(
                endpoint=endpoint, task_queue="flareward-e2e-" + uuid4().hex
            ),
            "interactions": InteractionBackend.REDIS,
            "redis_uri": SecretStr(redis_uri),
            "authentication": AuthenticationKind.SESSION,
            "secret_key": SecretStr(secret),
            "application_modules": ("support.programs",),
            "library": True,
            "reconcile_interval": 0.05,
        }
    )
    worker = WorkerSettings.model_validate(settings.model_dump(mode="python"))
    client = await Client.connect(endpoint)
    identity_key = "identity:session:" + uuid4().hex
    roots = [uuid4().hex for _ in range(3)]
    async with owned_redis(redis_uri, decode_responses=True) as redis:
        await redis.hset(
            identity_key,
            mapping={
                "username": "alice",
                "access_token": "fixture-token",
                "session_expires_at": time.time() + 120,
            },
        )
        await redis.expire(identity_key, 120)
        try:
            async with worker_process(worker, tmp_path / "worker.log") as running_worker:
                async with api_process(settings, tmp_path / "api.log") as http:
                    assert (await http.get("/api/blueprints")).status_code == 401
                    http.cookies.set(
                        "session",
                        session_cookie(identity_key.removeprefix("identity:session:"), secret),
                    )
                    model = await http.post(
                        "/api/resources",
                        json={
                            "category": "llms",
                            "type": "mock",
                            "name": "Network model",
                            "config": {
                                "type": "mock",
                                "base_url": "http://unused.invalid",
                                "api_key": token,
                            },
                        },
                    )
                    assert model.status_code == 201 and token not in model.text, model.text
                    node = await http.post(
                        "/api/resources",
                        json={
                            "category": "nodes",
                            "type": "mock_agent_node",
                            "name": "Network agent",
                            "config": {
                                "type": "mock_agent_node",
                                "llm": "$ref:" + model.json()["rid"],
                            },
                        },
                    )
                    assert node.status_code == 201, node.text
                    inspected = await http.post(
                        f"/api/resources/{node.json()['rid']}/validation", json={}
                    )
                    assert inspected.status_code == 200 and inspected.json()["is_valid"], (
                        inspected.text
                    )
                    card = await http.get(f"/api/resources/{node.json()['rid']}/card")
                    assert card.status_code == 200 and token not in card.text, card.text
                    created = await http.post(
                        "/api/blueprints",
                        json={
                            "spec": external_blueprint(node.json()["rid"]).model_dump(mode="json")
                        },
                    )
                    assert created.status_code == 201, created.text
                    assert token not in created.text
                    blueprint_id = created.json()["blueprint_id"]
                    validated = await http.post(
                        f"/api/blueprints/{blueprint_id}/validation", json={}
                    )
                    assert validated.status_code == 200 and validated.json()["is_valid"], (
                        validated.text
                    )
                    cards = await http.get(f"/api/blueprints/{blueprint_id}/cards")
                    assert cards.status_code == 200 and token not in cards.text, cards.text
                    assert set(cards.json()) == {node.json()["rid"], model.json()["rid"]}
                    imported = await http.put(
                        "/api/programs/network-graph/blueprint",
                        json={"blueprint_id": blueprint_id, "execution_profile": profile},
                    )
                    assert imported.status_code == 200, imported.text
                    published = await http.post(
                        "/api/programs/network-graph/revisions", json={"expected_version": 1}
                    )
                    assert published.status_code == 201, published.text
                    bindings = {
                        name: PathBinding(path=(name,)).model_dump(mode="json")
                        for name in GraphState.model_fields
                    }
                    session = await http.post(
                        "/api/sessions",
                        json={
                            "program": {"program_id": "network-graph", "revision": 1},
                            "blueprint_id": blueprint_id,
                            "input_bindings": bindings,
                            "output_bindings": bindings,
                        },
                    )
                    assert session.status_code == 201, session.text
                    session_id = session.json()["run_id"]
                    admitted = await http.post(
                        f"/api/sessions/{session_id}/executions",
                        json={"execution_id": roots[0], "inputs": {"user_prompt": "network input"}},
                    )
                    assert admitted.status_code == 202, admitted.text
                    result = await http.get(f"/api/executions/{roots[0]}/result")
                    assert result.status_code == 200 and result.json()["phase"] == "completed", (
                        result.text
                    )
                    assert result.json()["result"]["nodes_output"] == {
                        "respond": "Mock echo: network input"
                    }
                    assert result.json()["context"]["tags"]["credential_user_id"] == "alice"
                    assert "data: " in (await http.get(f"/api/executions/{roots[0]}/events")).text
                    await replay(client, worker, result.json()["context"]["engine_handle"])
                    waiting = ProgramDefinition(
                        program_id="network-wait",
                        name="Network wait",
                        owner=Identity.user("alice"),
                        implementation=ApplicationDefinition(implementation="waiting", version="1"),
                    )
                    assert (
                        await http.put(
                            "/api/programs/network-wait",
                            json={
                                "definition": waiting.model_dump(mode="json"),
                                "expected_version": 0,
                            },
                        )
                    ).status_code == 200
                    assert (
                        await http.post(
                            "/api/programs/network-wait/revisions", json={"expected_version": 1}
                        )
                    ).status_code == 201
                    request = {
                        "program": {"program_id": "network-wait", "revision": 1},
                        "execution_id": roots[1],
                    }
                    pending = await http.post("/api/executions", json=request)
                    assert pending.status_code == 202, pending.text
                    native_id = pending.json()["context"]["engine_handle"]
                # Restart the API and reconnect through the persisted record and same coordinator.
                async with api_process(settings, tmp_path / "api-restarted.log") as http:
                    http.cookies.set(
                        "session",
                        session_cookie(identity_key.removeprefix("identity:session:"), secret),
                    )
                    retried = await http.post("/api/executions", json=request)
                    assert (
                        retried.status_code == 202
                        and retried.json()["context"]["engine_handle"] == native_id
                    ), retried.text
                    message = await http.post(
                        f"/api/executions/{roots[1]}/messages",
                        json={"name": "answer", "data": "resumed through HTTP"},
                    )
                    assert message.status_code == 202, message.text
                    result = await http.get(f"/api/executions/{roots[1]}/result")
                    assert result.json()["result"] == {"answer": "resumed through HTTP"}, (
                        result.text
                    )
                    await replay(client, worker, native_id)
                    request["execution_id"] = roots[2]
                    assert (await http.post("/api/executions", json=request)).status_code == 202
                    assert (
                        await http.post(f"/api/executions/{roots[2]}/cancel")
                    ).status_code == 202
                    cancelled = await http.get(f"/api/executions/{roots[2]}/result")
                    assert cancelled.json()["phase"] == "cancelled", cancelled.text
                    running_worker.assert_running()
            documents = await mongo_database.blueprints.find().to_list()
            executions = await mongo_database.program_executions.find().to_list()
            resources = await mongo_database.resources.find().to_list()
            assert token not in str(documents) + str(executions) + str(resources)
            assert all(token not in path.read_text() for path in tmp_path.glob("*.log"))
        finally:
            keys = [identity_key]
            for root in roots:
                keys.extend([key async for key in redis.scan_iter(match=root_key(root) + "*")])
            await redis.delete(*keys)
