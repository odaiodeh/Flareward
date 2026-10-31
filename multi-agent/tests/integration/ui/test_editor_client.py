"""UI contracts and production clients share the installed TypeScript runner."""

import asyncio
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from mas.core.async_work import await_owned
from mas.core.identity import Identity
from outbound.interactions.wire import root_key
from outbound.redis_client import owned_redis
from pydantic import SecretStr
from support.server import api_process
from support.sharing import invitation

from config.interaction_settings import InteractionBackend

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def ui_node(request):
    if not request.config.getoption("--ui-clients"):
        pytest.skip("Select --ui-clients for actual TypeScript client integration")
    node = shutil.which("node")
    if node is None or not (ROOT / "ui/node_modules/vite").exists():
        pytest.fail(
            "UI client tests require Node and ui/pnpm install --frozen-lockfile", pytrace=False
        )
    return node


@pytest.fixture
def ui_mongo(ui_node):
    if not os.environ.get("UNIFAI_TEST_MONGO_URI"):
        pytest.fail("UI API clients require an isolated UNIFAI_TEST_MONGO_URI", pytrace=False)


async def run_contracts(node: str, suite: str, environment: dict[str, str] | None = None) -> str:
    result = await await_owned(
        asyncio.to_thread(
            subprocess.run,
            [node, "tests/run-api-contracts.mjs", suite],
            cwd=ROOT / "ui",
            env=environment,
            text=True,
            capture_output=True,
            timeout=60,
        )
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


async def test_graph_references_and_session_output_contracts(ui_node):
    output = await run_contracts(ui_node, "contracts")
    assert "UI graph and session output contracts passed" in output


@pytest.mark.parametrize("suite", ["api", "blueprints", "sessions", "shares"])
async def test_existing_typescript_editor_clients_use_native_services(
    ui_node, ui_mongo, secret_settings, mongo_database, tmp_path, suite
):
    settings = secret_settings.model_copy(update={"library": True})
    if suite == "shares":
        for invite in (
            invitation(
                "ui-received",
                sender_identity=Identity.user("sender", "Fixture sender"),
                recipient_identity=Identity.user("owner"),
            ),
            invitation("ui-sent", sender_identity=Identity.user("owner")),
            invitation("ui-foreign"),
        ):
            await mongo_database.shares.insert_one(invite.model_dump(mode="json"))
    redis_uri = os.environ.get("UNIFAI_TEST_REDIS_URI")
    if suite == "sessions":
        if not redis_uri:
            pytest.fail(
                "UI session streams require an isolated UNIFAI_TEST_REDIS_URI", pytrace=False
            )
        settings = settings.model_copy(
            update={
                "interactions": InteractionBackend.REDIS,
                "redis_uri": SecretStr(redis_uri),
                "element_modules": ("support.elements",),
            }
        )
    try:
        async with api_process(settings, tmp_path / "api.log") as http:
            environment = {
                **os.environ,
                "UNIFAI_TEST_UI_API_URL": str(http.base_url).rstrip("/") + "/api",
            }
            output = await run_contracts(ui_node, suite, environment)
            assert "clients passed against native FastAPI" in output
    finally:
        if suite == "sessions" and redis_uri:
            async with owned_redis(redis_uri, decode_responses=True) as redis:
                async for execution in mongo_database.program_executions.find({}, {"_id": 1}):
                    keys = [
                        key
                        async for key in redis.scan_iter(match=root_key(execution["_id"]) + ":*")
                    ]
                    if keys:
                        await await_owned(redis.delete(*keys))
