"""Shared native signed-session settings; business fixtures add their own policies."""

import os

from pydantic import SecretStr
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig

from config.platform_settings import PlatformSettings


def session_settings(database: str, redis_uri: str) -> PlatformSettings:
    return PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        interactions="disabled",
        authentication="session",
        secret_key=SecretStr("native-cookie-fixture"),
        mongo_uri=SecretStr(os.environ["UNIFAI_TEST_MONGO_URI"]),
        mongo_database=database,
        redis_uri=SecretStr(redis_uri),
        execution_profiles={
            "thread": ThreadRunnerConfig(),
            "process": ProcessRunnerConfig(max_workers=1),
        },
        default_execution_profile="thread",
        reconcile_interval=0.1,
    )
