"""Native review transport owns actual cookies, private workflow access and a live API."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import httpx
from cryptography.fernet import Fernet
from pydantic import SecretStr

from flareward.async_work import await_owned
from flareward.bootstrap.settings.platform_settings import PlatformSettings
from flareward.programs.domain.models import (
    ProgramDefinition,
    ProgramImplementation,
    ProgramRevision,
)
from flareward.services.connections.adapters.redis import owned_redis
from flareward.services.identity.domain import Identity
from flareward.services.reviews.access import ReviewGrant, review_credential_key
from flareward.services.reviews.domain.models import ReviewRecord
from support.identity import authenticated_cookie
from support.native_settings import session_settings
from support.reviews import review_policy
from support.server import api_process


async def pending_review(
    http: httpx.AsyncClient,
    root: str,
    human: dict[str, str],
    reviewer: dict[str, str],
    *,
    design_number: int | None = None,
    timeout: float = 30,
) -> ReviewRecord:
    async with asyncio.timeout(timeout):
        while True:
            inbox = await http.get("/api/reviews/inbox", headers=reviewer)
            assert inbox.status_code == 200, inbox.text
            for item in inbox.json()["reviews"]:
                review = ReviewRecord.model_validate(item)
                if review.root_execution_id != root or review.status != "pending":
                    continue
                subject = review.specification.subject
                if design_number is None or (
                    isinstance(subject, dict) and subject.get("number") == design_number
                ):
                    return review
            observed = await http.get(f"/api/executions/{root}", headers=human)
            assert observed.status_code == 200, observed.text
            assert observed.json()["phase"] not in {"failed", "cancelled", "completed"}, (
                observed.text
            )
            await asyncio.sleep(0.05)


@dataclass(frozen=True)
class ReviewAPI:
    http: httpx.AsyncClient
    owner: Identity
    root: str
    grant: ReviewGrant
    credential: SecretStr = field(repr=False)
    human: dict[str, str] = field(repr=False)
    reviewer: dict[str, str] = field(repr=False)
    log: Path
    settings: PlatformSettings = field(repr=False)
    directory: Path

    @property
    def client(self) -> dict[str, str]:
        return {"Authorization": "Bearer " + self.credential.get_secret_value()}

    @property
    def operator_environment(self) -> dict[str, str]:
        return {
            "FLAREWARD_REVIEW_ENDPOINT": str(self.http.base_url),
            "FLAREWARD_REVIEW_ACCESS_DIRECTORY": str(self.directory),
            "FLAREWARD_REVIEW_ALLOW_INSECURE": "true",
        }

    async def publish(self, name: str, implementation: ProgramImplementation) -> ProgramRevision:
        definition = ProgramDefinition(
            program_id=name, name=name, owner=self.owner, implementation=implementation
        )
        saved = await self.http.put(
            "/api/programs/" + name,
            headers=self.human,
            json={"definition": definition.model_dump(mode="json"), "expected_version": 0},
        )
        assert saved.status_code == 200, saved.text
        published = await self.http.post(
            f"/api/programs/{name}/revisions", headers=self.human, json={"expected_version": 1}
        )
        assert published.status_code == 201, published.text
        return ProgramRevision.model_validate(published.json())

    async def pending(self) -> ReviewRecord:
        return await pending_review(self.http, self.root, self.human, self.reviewer)


def review_settings(owner: Identity, database: str, redis_uri: str) -> PlatformSettings:
    return session_settings(database, redis_uri).model_copy(
        update={
            "reviews_enabled": True,
            "review_policies": {"release@1": review_policy(owner)},
            "application_modules": (
                "plugins.human_review.programs.human_review",
                "support.programs",
            ),
            "element_modules": ("plugins.human_review.elements.specification",),
        }
    )


@asynccontextmanager
async def review_api(
    owner: Identity,
    database: str,
    redis_uri: str,
    directory: Path,
    *,
    factory: str = "flareward.bootstrap.asgi:create_app",
    settings: PlatformSettings | None = None,
    ttl_seconds: int = 3600,
    renewable_for_seconds: int | None = None,
    managed_delivery: bool = False,
) -> AsyncIterator[ReviewAPI]:
    root = uuid4().hex
    credentials = directory / "credentials"
    credentials.mkdir(mode=0o700)
    log = directory / "review-api.log"
    settings = settings or review_settings(owner, database, redis_uri)
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
        cookies = [
            await resources.enter_async_context(
                authenticated_cookie(redis, user, settings.secret_key.get_secret_value())
            )
            for user in (owner.id, "reviewer")
        ]
        human, reviewer = ({"Cookie": "session=" + value} for value in cookies)
        http = await resources.enter_async_context(
            api_process(
                settings,
                log,
                factory=factory,
                environment=lambda base: {
                    "FLAREWARD_REVIEW_ENDPOINT": base,
                    "FLAREWARD_REVIEW_ACCESS_DIRECTORY": str(credentials),
                    "FLAREWARD_REVIEW_ALLOW_INSECURE": "true",
                },
            )
        )
        issued = await http.post(
            "/api/review-access",
            headers={**human, "Idempotency-Key": "root-review-access"}
            if managed_delivery
            else human,
            json={
                "ttl_seconds": ttl_seconds,
                "renewable_for_seconds": renewable_for_seconds,
                "scope": {
                    "root_execution_id": root,
                    "policies": ["release@1"],
                    "actions": ["open", "read", "close"],
                },
            },
        )
        assert issued.status_code == 201, issued.text
        grant = ReviewGrant.model_validate(issued.json()["grant"])
        credential = SecretStr(issued.json()["credential"])

        def provision() -> None:
            descriptor = os.open(
                credentials / review_credential_key(owner, root),
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            with os.fdopen(descriptor, "w") as destination:
                destination.write(credential.get_secret_value())

        if not managed_delivery:
            await await_owned(asyncio.to_thread(provision))
        yield ReviewAPI(
            http, owner, root, grant, credential, human, reviewer, log, settings, credentials
        )
