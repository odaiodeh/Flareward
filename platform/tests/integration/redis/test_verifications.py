"""An independent source check attests to the native API; evidence survives API restart."""

import asyncio
import hashlib
import os
import subprocess
import sys
from functools import partial

import pytest
from pydantic import SecretStr
from runengine.adapters.coordination.config import LocalHostConfig
from support.identity import authenticated_cookie
from support.server import api_process

from lumora.async_work import await_owned
from lumora.bootstrap.settings.platform_settings import (
    PlatformSettings,
    VerificationAuthorityConfig,
)
from lumora.executions.domain.context import ExecutionContext
from lumora.services.connections.adapters.redis import owned_redis
from lumora.services.identity.domain import Identity
from lumora.services.verification.domain.models import (
    CheckRequirement,
    CheckVerdict,
    VerificationSubject,
)
from lumora.services.verification.models import (
    StartVerification,
    SubmitCheckEvidence,
    VerificationPolicy,
)
from lumora.services.workspaces.domain.files import WorkspaceLayout, WorkspaceMode
from plugins.git.elements.adapter import GitCLIRepository
from plugins.git.elements.config import GitBinding, GitSettings


@pytest.mark.e2e
@pytest.mark.parametrize(
    "expected,outcome", [("first candidate", "accepted"), ("wrong content", "rejected")]
)
async def test_independent_git_check_has_separate_authority_and_durable_exact_candidate_evidence(
    redis_uri, mongo_database, local_repository, tmp_path, expected, outcome
):
    owner = Identity.user("verification-owner")
    credential = "private-ci-fixture-" + "c" * 32
    authority = {"Authorization": "Bearer " + credential, "X-Verification-Authority": "ci"}
    policy = VerificationPolicy(
        owners=(owner,),
        subject_kind="git-revision@1",
        requirements=(CheckRequirement(check="source-test@1", verifiers=frozenset({"ci"})),),
    )
    settings = PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        authentication="session",
        secret_key=SecretStr("verification-cookie-fixture"),
        mongo_uri=SecretStr(os.environ["LUMORA_TEST_MONGO_URI"]),
        mongo_database=mongo_database.name,
        redis_uri=SecretStr(redis_uri),
        verification_enabled=True,
        verification_policies={"source-quality@1": policy},
        verification_authorities={
            "ci": VerificationAuthorityConfig(
                credential_sha256=hashlib.sha256(credential.encode()).hexdigest(),
                owners=(owner,),
            )
        },
    )
    source = GitCLIRepository(
        "source",
        GitBinding(location=str(local_repository.path), owners=(owner,)),
        owner,
        GitSettings(workspace_root=tmp_path / "ci-compute"),
    )
    candidate = await source.resolve("HEAD")
    request = StartVerification(
        key="candidate-check",
        policy="source-quality@1",
        subject=VerificationSubject(
            kind="git-revision@1", identity=candidate.model_dump(mode="json")
        ),
    )
    async with owned_redis(redis_uri, decode_responses=True) as redis:
        async with authenticated_cookie(
            redis, owner.id, settings.secret_key.get_secret_value()
        ) as cookie:
            human = {"Cookie": "session=" + cookie}
            async with api_process(settings, tmp_path / "api-before.log") as http:
                created = await http.post(
                    "/api/verifications", headers=human, json=request.model_dump(mode="json")
                )
                assert created.status_code == 200, created.text
                plan_id = created.json()["state"]["plan"]["plan_id"]
                context = ExecutionContext(
                    identity=owner, root_execution_id=plan_id, execution_id="ci"
                )
                workspace = WorkspaceLayout.binding(
                    plan_id, "ci", "check", "source", WorkspaceMode.ISOLATED
                )
                await source.checkout(candidate, workspace, context)
                check = await await_owned(
                    asyncio.to_thread(
                        partial(
                            subprocess.run,
                            [
                                sys.executable,
                                "-I",
                                "-c",
                                "import sys; from pathlib import Path; "
                                "sys.exit(0 if Path('answer.txt').read_text() "
                                "== sys.argv[1] else 1)",
                                expected,
                            ],
                            cwd=tmp_path / "ci-compute" / workspace,
                            env={"PATH": os.environ.get("PATH", "")},
                            capture_output=True,
                            timeout=10,
                        )
                    )
                )
                verdict = CheckVerdict.PASSED if check.returncode == 0 else CheckVerdict.FAILED
                body = SubmitCheckEvidence(
                    plan_id=plan_id,
                    subject=request.subject,
                    check="source-test@1",
                    run_id="ci-check-1",
                    verdict=verdict,
                ).model_dump(mode="json")
                assert (
                    await http.post("/api/verification-evidence", headers=human, json=body)
                ).status_code == 401
                assert (
                    await http.get(f"/api/verifications/{plan_id}", headers=authority)
                ).status_code == 401
                assert (
                    await http.post(
                        "/api/verifications",
                        headers=authority,
                        json=request.model_dump(mode="json"),
                    )
                ).status_code == 401
                recorded = await http.post(
                    "/api/verification-evidence", headers=authority, json=body
                )
                assert recorded.status_code == 200 and recorded.json()["outcome"] == outcome
                assert credential not in recorded.text
                changed = await local_repository.commit("different candidate")
                mismatched = {
                    **body,
                    "subject": {
                        "kind": "git-revision@1",
                        "identity": {"repository": "source", "commit": changed},
                    },
                }
                assert (
                    await http.post(
                        "/api/verification-evidence", headers=authority, json=mismatched
                    )
                ).status_code == 409
                async with authenticated_cookie(
                    redis, "other-owner", settings.secret_key.get_secret_value()
                ) as other:
                    assert (
                        await http.get(
                            f"/api/verifications/{plan_id}", headers={"Cookie": "session=" + other}
                        )
                    ).status_code == 404
            async with api_process(settings, tmp_path / "api-after.log") as http:
                restored = await http.get(f"/api/verifications/{plan_id}", headers=human)
                assert restored.status_code == 200 and restored.json() == recorded.json()
                retry = await http.post("/api/verification-evidence", headers=authority, json=body)
                assert retry.status_code == 200 and retry.json() == recorded.json()
    stored = await mongo_database.program_verifications.find_one({"_id": plan_id})
    assert credential not in stored["data"]
    assert all(credential not in path.read_text() for path in tmp_path.glob("api-*.log"))
