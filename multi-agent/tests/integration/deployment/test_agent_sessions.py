"""Saved multi-agent sessions cross real HTTP, Redis, Mongo, and Temporal worker boundaries."""

import os
from uuid import uuid4

import pytest
from outbound.interactions.wire import root_key
from outbound.redis_client import owned_redis
from pydantic import SecretStr
from runengine.adapters.coordination.config import TemporalHostConfig
from support.agent_session_assertions import assert_agent_turn
from support.agent_session_http import create_agent_session, execute_agent_turn
from support.identity import authenticated_cookie
from support.server import api_process
from support.temporal import replay, worker_process
from temporalio.client import Client

from config.interaction_settings import InteractionBackend
from config.platform_settings import AuthenticationKind
from config.worker_settings import WorkerSettings


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_deployed_real_agents_share_resources_and_continue_the_same_session(
    secret_settings, profile, tmp_path
):
    endpoint, redis_uri = (
        os.environ.get(name) for name in ("UNIFAI_TEST_TEMPORAL_ENDPOINT", "UNIFAI_TEST_REDIS_URI")
    )
    if not endpoint or not redis_uri:
        pytest.skip("Set Temporal, Mongo, and Redis test services for agent-session E2E")
    settings = secret_settings.model_copy(
        update={
            "host": TemporalHostConfig(
                endpoint=endpoint, task_queue="unifai-agents-" + uuid4().hex
            ),
            "library": True,
            "authentication": AuthenticationKind.SESSION,
            "secret_key": SecretStr("agent-cookie-" + uuid4().hex),
            "interactions": InteractionBackend.REDIS,
            "redis_uri": SecretStr(redis_uri),
            "element_modules": ("support.agent_session",),
            "reconcile_interval": 0.05,
        }
    )
    worker = WorkerSettings.model_validate(settings.model_dump(mode="python"))
    native = await Client.connect(endpoint)
    seed = uuid4().hex
    async with (
        owned_redis(redis_uri, decode_responses=True) as redis,
        authenticated_cookie(redis, "owner", settings.secret_key.get_secret_value()) as cookie,
        worker_process(worker, tmp_path / "worker.log"),
    ):
        session_id = None
        previous_review = None
        for turn in (1, 2):
            # Restart the API between turns; session/workspace state comes from storage.
            async with api_process(settings, tmp_path / f"api-{turn}.log") as http:
                assert (await http.get("/api/blueprints")).status_code == 401
                http.cookies.set("session", cookie)
                if session_id is None:
                    session_id, definition = await create_agent_session(http, seed, profile=profile)
                    assert len(definition["implementation"]["resources"]) == 9
                execution_id = uuid4().hex
                try:
                    record, session = await execute_agent_turn(
                        http, session_id, execution_id, f"Research request {turn}"
                    )
                    previous_review = assert_agent_turn(
                        session, seed, execution_id, turn, previous_review
                    )
                    events = await http.get(f"/api/executions/{execution_id}/stream")
                    assert events.status_code == 200 and '"llm_token"' in events.text, events.text
                    assert record.context.session_id == session_id
                    assert record.context.tags["credential_user_id"] == "owner"
                    await replay(native, worker, record.context.engine_handle)
                finally:
                    keys = [
                        key async for key in redis.scan_iter(match=root_key(execution_id) + "*")
                    ]
                    if keys:
                        await redis.delete(*keys)
