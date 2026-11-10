"""Signed-cookie sessions recover saved policy across API restart during a Temporal wait."""

import asyncio
import json
import os
from uuid import uuid4

import pytest
from pydantic import SecretStr
from runengine.adapters.coordination.config import TemporalHostConfig
from support.identity import authenticated_cookie
from support.interaction_http import pending
from support.resource_http import create_resource
from support.server import api_process
from support.temporal import replay, worker_process, workflow_handle
from temporalio.client import Client, WorkflowFailureError

from lumora.bootstrap.settings.interaction_settings import InteractionBackend
from lumora.bootstrap.settings.platform_settings import AuthenticationKind
from lumora.bootstrap.settings.worker_settings import WorkerSettings
from lumora.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from lumora.services.connections.adapters.redis import owned_redis
from lumora.services.interactions.adapters.redis_store import RedisInteractionStore
from lumora.services.interactions.adapters.wire import root_key


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_approval_and_saved_rules_recover_across_api_restart(
    secret_settings, mongo_database, tmp_path, profile
):
    endpoint = os.environ.get("LUMORA_TEST_TEMPORAL_ENDPOINT")
    redis_uri = os.environ.get("LUMORA_TEST_REDIS_URI")
    if not endpoint or not redis_uri:
        pytest.skip("Set Temporal, Mongo and Redis services for approval recovery E2E")
    settings = secret_settings.model_copy(
        update={
            "host": TemporalHostConfig(
                endpoint=endpoint, task_queue="lumora-review-" + uuid4().hex
            ),
            "library": True,
            "authentication": AuthenticationKind.SESSION,
            "secret_key": SecretStr(uuid4().hex),
            "interactions": InteractionBackend.REDIS,
            "redis_uri": SecretStr(redis_uri),
            "element_modules": ("support.elements",),
            "reconcile_interval": 0.05,
            "approval_timeout": 60,
        }
    )
    worker = WorkerSettings.model_validate(settings.model_dump(mode="python"))
    native = await Client.connect(endpoint, namespace=settings.host.namespace)
    roots = [uuid4().hex, uuid4().hex]
    async with (
        owned_redis(redis_uri, decode_responses=True) as redis,
        authenticated_cookie(redis, "owner", settings.secret_key.get_secret_value()) as cookie,
        worker_process(worker, tmp_path / "worker.log"),
    ):
        store = RedisInteractionStore(redis)
        try:
            async with api_process(settings, tmp_path / "api.log") as http:
                http.cookies.set("session", cookie)
                node = await create_resource(
                    http,
                    "nodes",
                    "platform_approval",
                    "Review",
                    {"requests": 2},
                    execution={"profile": profile},
                )
                blueprint = await http.post(
                    "/api/blueprints",
                    json={
                        "spec": {
                            "name": "Recoverable review",
                            "nodes": [{"rid": "$ref:" + node}],
                            "plan": [{"uid": "review", "node": "$ref:" + node}],
                        }
                    },
                )
                assert blueprint.status_code == 201, blueprint.text
                created = await http.post(
                    "/api/sessions/user.session.create",
                    json={"blueprintId": blueprint.json()["blueprint_id"], "hitlEnabled": True},
                )
                assert created.status_code == 200, created.text
                session_id = created.json()
                started = await http.post(
                    "/api/sessions/user.session.submit",
                    json={"sessionId": session_id, "executionId": roots[0], "inputs": {}},
                )
                assert started.status_code == 202, started.text
                ticket = await pending(http, roots[0])
                saved = await http.post(
                    "/api/sessions/session.approval.rule",
                    json={
                        "sessionId": session_id,
                        "executionId": roots[0],
                        "action": "auto_approve",
                        "nodeUid": "review",
                        "toolName": "fixture-write",
                    },
                )
                assert saved.status_code == 200, saved.text
                persisted = saved.json()["overrides"]
            # No API remains to repair this cache. The Temporal worker still owns its wait.
            await redis.delete(root_key(roots[0]) + ":rules")
            assert await store.load_rules(roots[0]) is None
            async with api_process(settings, tmp_path / "api-restarted.log") as http:
                assert (
                    await http.get(
                        "/api/sessions/session.approval.rules", params={"sessionId": session_id}
                    )
                ).status_code == 401
                http.cookies.set("session", cookie)
                restored = await http.get(
                    "/api/sessions/session.approval.rules", params={"sessionId": session_id}
                )
                assert restored.status_code == 200 and restored.json()["overrides"] == persisted
                async with asyncio.timeout(8):
                    while (live := await store.load_rules(roots[0])) is None:
                        await asyncio.sleep(0.02)
                assert live.to_dict() == persisted
                assert (await pending(http, roots[0]))["request"] == ticket["request"]
                response = await http.post(
                    "/api/sessions/session.approval",
                    json={
                        "sessionId": session_id,
                        "executionId": roots[0],
                        "requestId": ticket["request"]["request_id"],
                        "decision": "approve",
                    },
                )
                assert response.status_code == 200, response.text
                first = await http.get(f"/api/executions/{roots[0]}/result")
                assert first.json()["phase"] == "completed", first.text
                assert json.loads(first.json()["result"]["output"])["decisions"] == [
                    "approve",
                    "approve",
                ]
                next_turn = await http.post(
                    "/api/sessions/user.session.submit",
                    json={"sessionId": session_id, "executionId": roots[1], "inputs": {}},
                )
                assert next_turn.status_code == 202, next_turn.text
                second = await http.get(f"/api/executions/{roots[1]}/result")
                assert second.json()["phase"] == "completed", second.text
                assert json.loads(second.json()["result"]["output"])["decisions"] == [
                    "approve",
                    "approve",
                ]
                for result in (first, second):
                    await replay(native, worker, result.json()["context"]["engine_handle"])
        finally:
            for root in roots:
                await store.cancel(root)
            executions = MongoExecutionRepository(mongo_database)
            for root in roots:
                try:
                    record = await executions.get(root)
                except KeyError:
                    continue
                handle = workflow_handle(native, record.engine_handle)
                try:
                    async with asyncio.timeout(15):
                        await handle.result()
                except WorkflowFailureError:
                    pass  # Failure/cancellation is terminal; owned native work has drained.
            for root in roots:
                keys = [key async for key in redis.scan_iter(match=root_key(root) + ":*")]
                if keys:
                    await redis.delete(*keys)
