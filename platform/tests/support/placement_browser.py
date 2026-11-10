"""Own an isolated signed-cookie/API browser fixture; no production auth replacement."""

import argparse
import asyncio
import os
import time
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from cryptography.fernet import Fernet
from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import SecretStr
from pymongo import AsyncMongoClient
from redis.asyncio import Redis
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.invocation.config import K8sRunnerConfig, ProcessRunnerConfig, ThreadRunnerConfig

from lumora.api.dependencies import authenticated
from lumora.async_work import await_owned
from lumora.bootstrap.asgi import create_app as native_app
from lumora.bootstrap.settings.platform_settings import PlatformSettings
from lumora.services.connections.adapters.redis import owned_redis
from lumora.services.identity.domain import Identity
from support.browser_identity import teams
from support.identity import authenticated_cookie
from support.server import api_process
from support.sharing import invitation


def create_app():
    return add_browser_routes(native_app())


def add_browser_routes(app: FastAPI) -> FastAPI:

    @app.get("/fixture/login")
    async def login():
        response = RedirectResponse("/inventory")
        response.set_cookie(
            "session", os.environ["PLACEMENT_BROWSER_COOKIE"], httponly=True, samesite="strict"
        )
        return response

    @app.get("/fixture/auth/user")
    async def user(caller: Annotated[Identity, Depends(authenticated)]):
        return {
            "authenticated": True,
            "user": {
                "username": caller.id,
                "sub": caller.id,
                "name": "Browser fixture owner",
                "email": "fixture@example.invalid",
                "token_expires_at": time.time() + 1800,
            },
        }

    app.mount(
        "/fixture/ui",
        StaticFiles(directory=os.environ["PLACEMENT_BROWSER_ASSETS"]),
        name="fixture-ui",
    )
    return app


@asynccontextmanager
async def team_leases(redis: Redis, team_ids: tuple[str, ...]):
    try:
        yield
    finally:
        for team_id in team_ids:
            keys = [
                key async for key in redis.scan_iter(match=f"mas:collab:editlock:team:{team_id}:*")
            ]
            if keys:
                await await_owned(redis.delete(*keys))


async def serve(assets: Path, log: Path) -> None:
    mongo_uri = os.environ["LUMORA_TEST_MONGO_URI"]
    redis_uri = os.environ["LUMORA_TEST_REDIS_URI"]
    database_name = "lumora_browser_test_" + uuid4().hex
    secret = uuid4().hex
    settings = PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        interactions="disabled",
        authentication="session",
        secret_key=SecretStr(secret),
        mongo_uri=SecretStr(mongo_uri),
        mongo_database=database_name,
        admin_config_database=database_name,
        redis_uri=SecretStr(redis_uri),
        configuration_secrets=True,
        credential_encryption_key=SecretStr(Fernet.generate_key().decode()),
        library=True,
        edit_locks=True,
        execution_profiles={
            "thread": ThreadRunnerConfig(),
            "process": ProcessRunnerConfig(max_workers=1),
            "isolated": K8sRunnerConfig(image="fixture-preview-only:no-execution"),
        },
        default_execution_profile="thread",
    )
    mongo = AsyncMongoClient(mongo_uri)
    try:
        async with AsyncExitStack() as owned:
            await mongo[database_name].admin_config.insert_one(
                {
                    "key": "openai_model_capabilities",
                    "value": {
                        "capabilities": {
                            "fixture-model": {"reasoning": ["low"]},
                            "fixture-model-mini": {"reasoning": ["minimal"]},
                        }
                    },
                }
            )
            os.environ["BROWSER_TEAM_PREFIX"] = "ub-" + uuid4().hex
            identity = await owned.enter_async_context(
                api_process(
                    settings,
                    log.with_suffix(".identity.log"),
                    factory="support.browser_identity:create_app",
                    health_path="/health",
                )
            )
            settings = settings.model_copy(
                update={"identity_url": str(identity.base_url).rstrip("/")}
            )
            team_ids = tuple(team["team_id"] for team in teams())
            for name, owner, label in (
                ("personal", Identity.user("browser-owner"), "Personal sharing fixture"),
                ("first", Identity.team(team_ids[0]), "First team sharing fixture"),
                ("second", Identity.team(team_ids[1]), "Second team sharing fixture"),
            ):
                await mongo[database_name].shares.insert_one(
                    invitation(
                        "browser-" + name,
                        sender_identity=Identity.user("fixture-sender", "Fixture sender"),
                        recipient_identity=owner,
                        item_name=label,
                    ).model_dump(mode="json")
                )
            redis = await owned.enter_async_context(owned_redis(redis_uri, decode_responses=True))
            cookie = await owned.enter_async_context(
                authenticated_cookie(redis, "browser-owner", secret, ttl=1800)
            )
            await owned.enter_async_context(team_leases(redis, team_ids))
            os.environ["PLACEMENT_BROWSER_COOKIE"] = cookie
            os.environ["PLACEMENT_BROWSER_ASSETS"] = str(assets.resolve())
            http = await owned.enter_async_context(
                api_process(
                    settings,
                    log,
                    factory="support.workspace_browser:create_app",
                )
            )
            assert (await http.get("/api/catalog/execution-profiles")).status_code == 401
            http.cookies.set("session", cookie)

            async def resource(category, type_key, name, config, profile="thread", team_id=None):
                response = await http.post(
                    "/api/resources/resource.save",
                    json={
                        "category": category,
                        "type": type_key,
                        "name": name,
                        "config": config,
                        **({"teamId": team_id} if team_id else {}),
                        **(
                            {"execution": {"profile": profile}}
                            if category in ("nodes", "conditions")
                            else {}
                        ),
                    },
                )
                assert response.status_code == 201, response.text
                return response.json()["rid"]

            scopes = [(None, "Browser"), *zip(team_ids, ("Alpha", "Beta"))]
            for team_id, label in scopes:
                model = await resource(
                    "llms",
                    "mock",
                    f"{label} model",
                    {"base_url": "http://unused.invalid", "api_key": "EMPTY"},
                    team_id=team_id,
                )
                for suffix, profile in (("work", "process"), ("finish", "thread")):
                    await resource(
                        "nodes",
                        "mock_agent_node",
                        f"{label} {suffix}",
                        {"llm": "$ref:" + model},
                        profile,
                        team_id,
                    )
                await resource(
                    "conditions",
                    "router_boolean",
                    f"{label} condition",
                    {"boolean_value": True},
                    team_id=team_id,
                )
            print(str(http.base_url).rstrip("/") + "/fixture/login", flush=True)
            await asyncio.Event().wait()
    finally:
        for name in (
            "PLACEMENT_BROWSER_COOKIE",
            "PLACEMENT_BROWSER_ASSETS",
            "BROWSER_TEAM_PREFIX",
        ):
            os.environ.pop(name, None)
        try:
            await await_owned(mongo.drop_database(database_name))
        finally:
            await await_owned(mongo.close())
        print("Removed browser fixture " + database_name, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    options = parser.parse_args()
    try:
        asyncio.run(serve(options.assets, options.log))
    except KeyboardInterrupt:
        pass
