"""Native signed-session API with managed bindings and no pre-issued workflow grants."""

import socket
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from pydantic import SecretStr
from runengine.adapters.coordination.config import TemporalHostConfig

from flareward.bootstrap.settings.platform_settings import (
    PlatformSettings,
    VerificationAuthorityConfig,
)
from flareward.services.connections.adapters.redis import owned_redis
from flareward.services.identity.domain import Identity
from support.identity import authenticated_cookie
from support.review_api import review_settings
from support.server import api_process
from support.verification import verification_policy


@dataclass(frozen=True)
class ManagedAccessAPI:
    http: httpx.AsyncClient
    owner: Identity
    human: dict[str, str] = field(repr=False)
    reviewer: dict[str, str] = field(repr=False)
    settings: PlatformSettings = field(repr=False)
    log: Path


def managed_access_settings(
    owner: Identity,
    database: str,
    redis_uri: str,
    directory: Path,
    *,
    host: TemporalHostConfig | None = None,
) -> PlatformSettings:
    settings = review_settings(owner, database, redis_uri).model_copy(
        update={
            "recoverable_credential_issuance": True,
            "event_sources_enabled": True,
            "workflow_credential_directory": directory / "managed-workflow-access",
            "credential_encryption_key": SecretStr(Fernet.generate_key().decode()),
            "verification_enabled": True,
            "verification_policies": {"release@1": verification_policy(owner)},
            "verification_authorities": {
                name: VerificationAuthorityConfig(credential_sha256=digest * 64, owners=(owner,))
                for name, digest in (("ci", "a"), ("scanner", "b"))
            },
            "element_modules": (
                "plugins.human_review.elements.specification",
                "plugins.verification.elements.specification",
            ),
            "application_modules": (
                "plugins.human_review.programs.human_review",
                "plugins.verification.programs.waiting",
                "support.programs",
            ),
            "reconcile_interval": 0.05,
        }
    )
    if host is not None:
        settings = settings.model_copy(update={"host": host})
    return settings


def managed_access_environment(base: str) -> dict[str, str]:
    return {
        "FLAREWARD_REVIEW_ENDPOINT": base,
        "FLAREWARD_REVIEW_ALLOW_INSECURE": "true",
        "FLAREWARD_VERIFICATION_ENDPOINT": base,
        "FLAREWARD_VERIFICATION_ALLOW_INSECURE": "true",
    }


@asynccontextmanager
async def managed_access_api(
    database: str,
    redis_uri: str,
    directory: Path,
    *,
    host: TemporalHostConfig | None = None,
    listener: socket.socket | None = None,
    application_modules: tuple[str, ...] = (),
) -> AsyncIterator[ManagedAccessAPI]:
    owner = Identity.user("admission-owner")
    settings = managed_access_settings(owner, database, redis_uri, directory, host=host)
    if application_modules:
        settings = settings.model_copy(
            update={"application_modules": (*settings.application_modules, *application_modules)}
        )
    log = directory / "managed-admission-api.log"
    async with AsyncExitStack() as resources:
        redis = await resources.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        human = await resources.enter_async_context(
            authenticated_cookie(redis, owner.id, settings.secret_key.get_secret_value())
        )
        reviewer = await resources.enter_async_context(
            authenticated_cookie(redis, "reviewer", settings.secret_key.get_secret_value())
        )
        http = await resources.enter_async_context(
            api_process(
                settings,
                log,
                environment=managed_access_environment,
                listener=listener,
            )
        )
        yield ManagedAccessAPI(
            http,
            owner,
            {"Cookie": "session=" + human},
            {"Cookie": "session=" + reviewer},
            settings,
            log,
        )
