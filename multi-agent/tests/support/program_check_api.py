"""Own signed identities and published verifier setup across native API lifetimes."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from mas.application.verification.check_ports import CheckRunnerPolicy
from mas.application.verification.models import VerificationPolicy
from mas.core.identity import Identity
from mas.domain.programs.models import ProgramRef
from mas.domain.verification import CheckRequirement, VerificationSubject
from mas_plugins.testing.program import PythonFunctionCheckConfig
from outbound.redis_client import owned_redis
from runengine.invocation.config import ExecutorConfig

from config.platform_settings import PlatformSettings
from support.artifacts import chunks, publication
from support.check_program_publication import CheckProgramSetup
from support.identity import authenticated_cookie
from support.native_settings import session_settings
from support.program_checks import verifier_definition
from support.python_checks import python_verifier_definition
from support.server import api_process


@dataclass(frozen=True)
class ProgramCheckAPI:
    settings: PlatformSettings = field(repr=False)
    directory: Path
    owner: Identity
    operator: Identity
    human: dict[str, str] = field(repr=False)
    verifier: dict[str, str] = field(repr=False)
    reference: ProgramRef
    subject: VerificationSubject
    local_evaluation_enabled: bool = True

    def serve(self, name: str) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        return api_process(
            self.settings,
            self.directory / (name + ".log"),
            environment=lambda _: {
                "UNIFAI_PYTHON_CHECK_EXECUTION_ENABLED": (
                    "true" if self.local_evaluation_enabled else "false"
                ),
                "UNIFAI_PYTHON_CHECK_DIRECTORY": str(self.directory / "check-workspaces"),
            },
        )

    async def start_check(self, http: httpx.AsyncClient) -> dict:
        response = await http.post(
            "/api/verifications",
            headers=self.human,
            json={
                "key": "candidate",
                "policy": "value@1",
                "subject": self.subject.model_dump(mode="json"),
            },
        )
        assert response.status_code == 200, response.text
        plan_id = response.json()["state"]["plan"]["plan_id"]
        response = await http.post(
            "/api/verification-checks",
            headers=self.human,
            json={"plan_id": plan_id, "runner": "program@1"},
        )
        assert response.status_code == 200, response.text
        return response.json()

    async def settled_check(
        self, http: httpx.AsyncClient, intent: str, *, timeout: float = 30
    ) -> dict:
        async with asyncio.timeout(timeout):
            while True:
                response = await http.post(
                    f"/api/verification-checks/{intent}/refresh", headers=self.human
                )
                assert response.status_code == 200, response.text
                check = response.json()
                if check["evidence_recorded"]:
                    break
                await asyncio.sleep(0.05)
            while check["job_state"] != "closed":
                response = await http.get(f"/api/verification-checks/{intent}", headers=self.human)
                assert response.status_code == 200, response.text
                check = response.json()
                await asyncio.sleep(0.05)
            return check


@asynccontextmanager
async def prepared_verifier(
    database: str,
    redis_uri: str,
    directory: Path,
    profile: str,
    value: int | bytes,
    *,
    checker: PythonFunctionCheckConfig | None = None,
    target: ExecutorConfig | None = None,
) -> AsyncIterator[ProgramCheckAPI]:
    owner, operator = Identity.user("candidate-owner"), Identity.user("trusted-verifier")
    initial = session_settings(database, redis_uri).model_copy(
        update={
            "element_modules": ("support.program_checks", "mas_plugins.testing.specification"),
            "application_modules": ("support.programs", "mas_plugins.testing.program"),
            "artifact_directory": directory / "artifacts",
        }
    )
    if target is not None:
        initial = initial.model_copy(
            update={"execution_profiles": {**initial.execution_profiles, profile: target}}
        )
    async with AsyncExitStack() as resources:
        redis = await resources.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        headers = [
            {
                "Cookie": "session="
                + await resources.enter_async_context(
                    authenticated_cookie(redis, identity.id, initial.secret_key.get_secret_value())
                )
            }
            for identity in (owner, operator)
        ]
        human, verifier = headers
        async with api_process(initial, directory / "publish.log") as http:
            if isinstance(value, bytes):
                published = await http.post(
                    "/api/artifacts",
                    content=chunks(value),
                    headers={**human, "X-Artifact-Metadata": publication(value).model_dump_json()},
                )
                assert published.status_code == 201, published.text
                artifact = published.json()["reference"]
                assert (
                    await http.get(f"/api/artifacts/{artifact['artifact_id']}", headers=verifier)
                ).status_code == 404
                subject = VerificationSubject(kind="blob-artifact@1", identity=artifact)
                definition = python_verifier_definition(operator, profile, checker)
            else:
                subject = VerificationSubject(kind="fixture-value@1", identity={"value": value})
                definition = verifier_definition(operator, profile)
            binding = await CheckProgramSetup(
                definition,
                CheckRunnerPolicy(
                    owners=(owner,),
                    policies=frozenset({"value@1"}),
                    check="tests@1",
                    verifier="program-ci",
                    subject_kind=subject.kind,
                ),
                input_artifact_max_bytes=65_536 if isinstance(value, bytes) else None,
            ).publish(http, verifier)
        settings = PlatformSettings.model_validate(
            {
                **initial.model_dump(mode="python"),
                "verification_enabled": True,
                "verification_policies": {
                    "value@1": VerificationPolicy(
                        owners=(owner,),
                        subject_kind=subject.kind,
                        requirements=(
                            CheckRequirement(
                                check="tests@1",
                                verifiers=frozenset({"program-ci"}),
                                requires_reports=True,
                            ),
                        ),
                        timeout_seconds=60,
                    )
                },
                "program_checks": {"program@1": binding},
            }
        )
        yield ProgramCheckAPI(
            settings,
            directory,
            owner,
            operator,
            human,
            verifier,
            binding.program,
            subject,
            local_evaluation_enabled=target is None,
        )
