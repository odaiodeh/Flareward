"""Own native verification transport, cookies and private root credentials for E2E scenarios."""

import asyncio
import hashlib
import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet
from pydantic import SecretStr
from pymongo.asynchronous.database import AsyncDatabase
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig

from flareward.async_work import await_owned
from flareward.bootstrap.settings.platform_settings import (
    PlatformSettings,
    VerificationAuthorityConfig,
)
from flareward.services.connections.adapters.redis import owned_redis
from flareward.services.identity.domain import Identity
from flareward.services.verification.access_models import (
    VerificationAccessGrant,
    verification_credential_key,
)
from flareward.services.verification.domain.models import VerificationPlan, VerificationState
from support.identity import authenticated_cookie
from support.server import api_process
from support.verification import evidence_request, verification_policy


@dataclass(frozen=True)
class VerificationAPI:
    http: httpx.AsyncClient
    database: AsyncDatabase[dict[str, Any]] = field(repr=False)
    owner: Identity
    root: str
    grant: VerificationAccessGrant
    credential: SecretStr = field(repr=False)
    human: dict[str, str] = field(repr=False)
    issuers: dict[str, SecretStr] = field(repr=False)
    directory: Path
    log: Path

    @property
    def client(self) -> dict[str, str]:
        return {"Authorization": "Bearer " + self.credential.get_secret_value()}

    @property
    def operator_environment(self) -> dict[str, str]:
        return {
            "FLAREWARD_VERIFICATION_ENDPOINT": str(self.http.base_url),
            "FLAREWARD_VERIFICATION_ACCESS_DIRECTORY": str(self.directory),
            "FLAREWARD_VERIFICATION_ALLOW_INSECURE": "true",
        }

    async def inspected_plan(self) -> VerificationPlan:
        async with asyncio.timeout(30):
            document = None
            while document is None:
                document = await self.database.program_verifications.find_one()
                if document is None:
                    await asyncio.sleep(0.02)
            plan = VerificationState.model_validate_json(document["data"]).plan
            assert plan.root_execution_id == self.root
            while f"GET /api/verifications/{plan.plan_id} " not in self.log.read_text():
                await asyncio.sleep(0.02)
            return plan

    async def attest(self, plan: VerificationPlan) -> None:
        for check, issuer in (("tests@1", "ci"), ("security@1", "scanner")):
            response = await self.http.post(
                "/api/verification-evidence",
                headers={
                    "X-Verification-Authority": issuer,
                    "Authorization": "Bearer " + self.issuers[issuer].get_secret_value(),
                },
                json=evidence_request(plan, check).model_dump(mode="json"),
            )
            assert response.status_code == 200, response.text


@asynccontextmanager
async def verification_api(
    owner: Identity,
    database: AsyncDatabase[dict[str, Any]],
    redis_uri: str,
    directory: Path,
    *,
    settings: PlatformSettings | None = None,
    factory: str = "flareward.bootstrap.asgi:create_app",
    policy: str = "release@1",
    actions: tuple[str, ...] = ("create", "read", "cancel"),
    host=None,
    managed_delivery: bool = False,
) -> AsyncIterator[VerificationAPI]:
    root, credentials, log = (
        uuid4().hex,
        directory / "credentials",
        directory / "verification-api.log",
    )
    credentials.mkdir(mode=0o700)
    issuers = {
        name: SecretStr("test-" + name + "-credential-" + "x" * 32) for name in ("ci", "scanner")
    }
    settings = settings or PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        authentication="session",
        secret_key=SecretStr("workflow-cookie-fixture"),
        mongo_uri=SecretStr(os.environ["FLAREWARD_TEST_MONGO_URI"]),
        mongo_database=database.name,
        redis_uri=SecretStr(redis_uri),
        verification_enabled=True,
        verification_policies={"release@1": verification_policy(owner)},
        verification_authorities={
            name: VerificationAuthorityConfig(
                credential_sha256=hashlib.sha256(value.get_secret_value().encode()).hexdigest(),
                owners=(owner,),
            )
            for name, value in issuers.items()
        },
    )
    settings = settings.model_copy(
        update={
            "host": host if host is not None else settings.host,
            "element_modules": tuple(
                dict.fromkeys(
                    (
                        *settings.element_modules,
                        "plugins.verification.elements.specification",
                    )
                )
            ),
            "application_modules": tuple(
                dict.fromkeys(
                    (
                        *settings.application_modules,
                        "plugins.verification.programs.waiting",
                        "support.programs",
                    )
                )
            ),
            "execution_profiles": {
                "thread": ThreadRunnerConfig(),
                "process": ProcessRunnerConfig(max_workers=1),
                **settings.execution_profiles,
            },
        }
    )
    if managed_delivery:
        settings = settings.model_copy(
            update={
                "recoverable_credential_issuance": True,
                "workflow_credential_directory": directory / "managed-workflow-access",
                "credential_encryption_key": SecretStr(Fernet.generate_key().decode()),
            }
        )
    async with AsyncExitStack() as resources:
        redis = await resources.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        cookie = await resources.enter_async_context(
            authenticated_cookie(redis, owner.id, settings.secret_key.get_secret_value())
        )
        http = await resources.enter_async_context(
            api_process(
                settings,
                log,
                factory=factory,
                environment=lambda base: {
                    "FLAREWARD_VERIFICATION_ENDPOINT": base,
                    "FLAREWARD_VERIFICATION_ACCESS_DIRECTORY": str(credentials),
                    "FLAREWARD_VERIFICATION_ALLOW_INSECURE": "true",
                },
            )
        )
        human = {"Cookie": "session=" + cookie}
        issued = await http.post(
            "/api/verification-access",
            headers={**human, "Idempotency-Key": "root-verification-access"}
            if managed_delivery
            else human,
            json={
                "scope": {
                    "root_execution_id": root,
                    "policies": [policy],
                    "actions": list(actions),
                },
            },
        )
        assert issued.status_code == 201, issued.text
        grant = VerificationAccessGrant.model_validate(issued.json()["grant"])
        credential = SecretStr(issued.json()["credential"])
        binding = credentials / verification_credential_key(owner, root)

        def provision() -> None:
            descriptor = os.open(binding, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as destination:
                destination.write(credential.get_secret_value())

        if not managed_delivery:
            await await_owned(asyncio.to_thread(provision))
        yield VerificationAPI(
            http, database, owner, root, grant, credential, human, issuers, credentials, log
        )
