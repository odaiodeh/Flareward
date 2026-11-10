"""Real signed-cookie authentication issues scoped transfer access, never a general API session."""

import pytest
from pydantic import SecretStr
from runengine.adapters.coordination.config import LocalHostConfig
from support.artifacts import chunks, publication
from support.identity import authenticated_cookie
from support.server import api_process

from lumora.bootstrap.settings.platform_settings import PlatformSettings
from lumora.services.connections.adapters.redis import owned_redis


@pytest.mark.e2e
async def test_native_cookie_issued_artifact_credential_cannot_access_other_api_roles(
    redis_uri, tmp_path
):
    settings = PlatformSettings(
        host=LocalHostConfig(),
        storage="memory",
        authentication="session",
        secret_key=SecretStr("artifact-cookie-test-secret"),
        redis_uri=SecretStr(redis_uri),
        artifact_directory=tmp_path / "objects",
    )
    async with owned_redis(redis_uri, decode_responses=True) as redis:
        async with authenticated_cookie(
            redis, "artifact-owner", settings.secret_key.get_secret_value()
        ) as cookie:
            async with api_process(settings, tmp_path / "api.log") as http:
                request = {"scope": {"actions": ["read", "publish"], "namespaces": ["project"]}}
                assert (await http.post("/api/artifact-access", json=request)).status_code == 401
                issued = await http.post(
                    "/api/artifact-access", json=request, headers={"Cookie": "session=" + cookie}
                )
                assert issued.status_code == 201, issued.text
                credential = issued.json()["credential"]
                worker = {"Authorization": "Bearer " + credential}
                assert (
                    await http.get("/api/artifact-access/self", headers=worker)
                ).status_code == 200
                assert (
                    await http.get("/api/catalog/execution-profiles", headers=worker)
                ).status_code == 401
                assert (
                    await http.post("/api/artifact-access", json=request, headers=worker)
                ).status_code == 401
                manifest = publication(namespace="project")
                uploaded = await http.post(
                    "/api/artifacts",
                    headers={**worker, "X-Artifact-Metadata": manifest.model_dump_json()},
                    content=chunks(),
                )
                assert uploaded.status_code == 201, uploaded.text
                identifier = uploaded.json()["reference"]["artifact_id"]
                assert (
                    await http.get(f"/api/artifacts/{identifier}/content", headers=worker)
                ).content == b"candidate"
                async with authenticated_cookie(
                    redis, "other-owner", settings.secret_key.get_secret_value()
                ) as other:
                    assert (
                        await http.get(
                            f"/api/artifacts/{identifier}", headers={"Cookie": "session=" + other}
                        )
                    ).status_code == 404
                assert credential not in (tmp_path / "api.log").read_text()
