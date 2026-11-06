"""Shared actual-App identity, assets and private login lifetime for feature scenarios."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from mas.core.async_work import await_owned
from mas.core.identity import Identity
from pymongo import AsyncMongoClient

from support.engineering_api import EngineeringAPI
from support.native_settings import session_settings
from support.server import api_process


def _write_cookie(path: Path, cookie: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as destination:
        destination.write(cookie)


@dataclass(frozen=True)
class FeatureBrowserSession:
    owner: Identity
    database: str
    redis_uri: str
    cookie_file: Path
    environment: dict[str, str]

    async def show_login(self, api: EngineeringAPI) -> None:
        await asyncio.to_thread(
            _write_cookie, self.cookie_file, api.human["Cookie"].removeprefix("session=")
        )
        print(str(api.http.base_url).rstrip("/") + "/fixture/feature-login", flush=True)


@asynccontextmanager
async def feature_browser_session(
    assets: Path, directory: Path
) -> AsyncIterator[FeatureBrowserSession]:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    database = "unifai_feature_browser_" + uuid4().hex
    cookie_file = directory / "owner-cookie"
    environment = {
        "PLACEMENT_BROWSER_ASSETS": str(assets.resolve()),
        "BROWSER_TEAM_PREFIX": "feature-" + uuid4().hex,
        "FEATURE_BROWSER_COOKIE_FILE": str(cookie_file),
    }
    previous = {name: os.environ.get(name) for name in environment}
    os.environ.update(environment)
    mongo = AsyncMongoClient(os.environ["UNIFAI_TEST_MONGO_URI"])
    redis_uri = os.environ["UNIFAI_TEST_REDIS_URI"]
    try:
        async with api_process(
            session_settings(database, redis_uri),
            directory / "identity.log",
            factory="support.browser_identity:create_app",
            health_path="/health",
        ) as identity:
            # Reviewer assignment never grants another owner's artifact content.
            yield FeatureBrowserSession(
                Identity.user("reviewer"),
                database,
                redis_uri,
                cookie_file,
                {
                    "UNIFAI_IDENTITY_URL": str(identity.base_url).rstrip("/"),
                    "UNIFAI_ADMIN_CONFIG_DATABASE": database,
                },
            )
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        await await_owned(mongo.drop_database(database))
        await await_owned(mongo.close())
        await await_owned(asyncio.to_thread(cookie_file.unlink, missing_ok=True))
        print("Removed feature browser fixture " + database, flush=True)
