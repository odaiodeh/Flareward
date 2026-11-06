"""Bounded transfer credentials cannot widen namespaces, cross owners, or manage credentials."""

from dataclasses import replace

import httpx
from fastapi import HTTPException
from inbound.http_api.app import create_app
from mas.application.artifacts.access import ArtifactAccessService
from mas.application.artifacts.service import ArtifactService
from mas.core.identity import Identity
from outbound.artifacts.access import SQLiteArtifactAccessRepository
from outbound.artifacts.filesystem import FileArtifactRepository
from support.artifact_workflow import ArtifactWorkflowCase, MemoryArtifactWorkflowRepository
from support.artifacts import chunks, publication


async def test_transfer_grants_remain_scoped_and_revocation_persists(platform, tmp_path):
    async def authenticate(request):
        name = request.headers.get("X-Human")
        if name not in {"owner", "other"}:
            raise HTTPException(status_code=401, detail="Human session required")
        return Identity.user(name)

    repository = SQLiteArtifactAccessRepository(tmp_path / "access")
    await repository.initialize()
    app = create_app(
        platform.programs,
        platform.executions,
        authenticate,
        artifacts=ArtifactService(FileArtifactRepository(tmp_path / "objects")),
        artifact_access=ArtifactAccessService(repository),
    )
    human = {"X-Human": "owner"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        issued = await http.post(
            "/api/artifact-access",
            headers=human,
            json={
                "scope": {
                    "actions": ["read", "publish"],
                    "namespaces": ["project"],
                    "max_bytes": 16,
                }
            },
        )
        assert issued.status_code == 201, issued.text
        token, grant = issued.json()["credential"], issued.json()["grant"]
        bearer = {"Authorization": "Bearer " + token}
        combined = {**bearer, **human}
        assert (await http.get("/api/artifact-access", headers=combined)).status_code == 401
        assert (
            await http.post(
                "/api/artifact-access",
                headers=combined,
                json={"scope": {"actions": ["read"], "namespaces": ["project"]}},
            )
        ).status_code == 401
        assert issued.headers["cache-control"] == "no-store"
        assert token not in (tmp_path / "access/access.sqlite").read_bytes().decode(errors="ignore")
        own = await http.get("/api/artifact-access/self", headers=bearer)
        assert own.status_code == 200 and own.json() == grant
        assert (
            await http.get("/api/programs/anything/revisions/1", headers=bearer)
        ).status_code == 401
        assert (
            await http.post(
                "/api/artifact-access",
                headers=bearer,
                json={"scope": {"actions": ["read"], "namespaces": ["other"]}},
            )
        ).status_code == 401

        async def upload(namespace, key="write", headers=bearer):
            manifest = publication(namespace=namespace, key=key)
            return await http.post(
                "/api/artifacts",
                headers={**headers, "X-Artifact-Metadata": manifest.model_dump_json()},
                content=chunks(),
            )

        first = await upload("project")
        assert first.status_code == 201, first.text
        identifier = first.json()["reference"]["artifact_id"]
        assert (await upload("elsewhere")).status_code == 403
        oversized = publication(b"x" * 17, namespace="project", key="over-limit")
        assert (
            await http.post(
                "/api/artifacts",
                headers={**bearer, "X-Artifact-Metadata": oversized.model_dump_json()},
                content=b"x" * 17,
            )
        ).status_code == 413
        foreign_namespace = await upload("elsewhere", headers=human)
        hidden = foreign_namespace.json()["reference"]["artifact_id"]
        assert (await http.get(f"/api/artifacts/{hidden}", headers=bearer)).status_code == 404
        other_owner = await upload("project", headers={"X-Human": "other"})
        hidden_owner = other_owner.json()["reference"]["artifact_id"]
        assert (await http.get(f"/api/artifacts/{hidden_owner}", headers=bearer)).status_code == 404
        assert (
            await http.get(f"/api/artifacts/{identifier}/content", headers=bearer)
        ).content == b"candidate"
        read_only = await http.post(
            "/api/artifact-access",
            headers=human,
            json={"scope": {"actions": ["read"], "artifact_ids": [identifier], "max_bytes": 4}},
        )
        assert read_only.status_code == 201, read_only.text
        read_headers = {"Authorization": "Bearer " + read_only.json()["credential"]}
        assert (
            await http.get(f"/api/artifacts/{identifier}", headers=read_headers)
        ).status_code == 200
        assert (await http.get(f"/api/artifacts/{hidden}", headers=read_headers)).status_code == 404
        assert (
            await http.get(f"/api/artifacts/{identifier}/content", headers=read_headers)
        ).status_code == 413
        assert (await upload("project", headers=read_headers)).status_code == 403
        listed = await http.get("/api/artifact-access", headers=human)
        assert token not in listed.text and "secret_sha256" not in listed.text
        assert (
            await http.delete(
                f"/api/artifact-access/{grant['grant_id']}", headers={"X-Human": "other"}
            )
        ).status_code == 404
        assert (
            await http.delete(f"/api/artifact-access/{grant['grant_id']}", headers=human)
        ).status_code == 204
        assert (await http.get("/api/artifact-access/self", headers=bearer)).status_code == 401
        invalid = await http.get(
            "/api/artifact-access/self",
            headers={"Authorization": "Bearer " + token + "wrong", **human},
        )
        assert invalid.status_code == 401 and token not in invalid.text
    restored = SQLiteArtifactAccessRepository(tmp_path / "access")
    await restored.initialize()
    assert (await restored.get(grant["grant_id"])).grant.revoked


async def test_workflow_artifact_authority_cannot_escape_scope_or_become_human(platform, tmp_path):
    case = ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    _, token = await case.provision()

    async def authenticate(request):
        raise HTTPException(status_code=401, detail="Human session required")

    repository = SQLiteArtifactAccessRepository(tmp_path / "access")
    await repository.initialize()
    app = create_app(
        platform.programs,
        platform.executions,
        authenticate,
        artifacts=ArtifactService(FileArtifactRepository(tmp_path / "objects")),
        artifact_access=ArtifactAccessService(repository),
    )
    app.state.platform = replace(app.state.platform, artifact_workflow_access=case.service)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        bearer = {"Authorization": "Bearer " + token}
        own = await http.get("/api/artifact-access/self", headers=bearer)
        assert own.status_code == 200 and own.json()["scope"]["root_execution_id"] == "root"
        for endpoint in ("/api/programs", "/api/artifact-access"):
            assert (await http.get(endpoint, headers=bearer)).status_code == 401
        assert (
            await http.post(
                "/api/artifact-access",
                headers=bearer,
                json={"scope": {"actions": ["read"], "namespaces": ["project"]}},
            )
        ).status_code == 401
        manifest = publication(namespace="project")
        uploaded = await http.post(
            "/api/artifacts",
            headers={**bearer, "X-Artifact-Metadata": manifest.model_dump_json()},
            content=chunks(),
        )
        assert uploaded.status_code == 201, uploaded.text
        artifact = uploaded.json()["reference"]["artifact_id"]
        assert (
            await http.get(f"/api/artifacts/{artifact}/content", headers=bearer)
        ).content == b"candidate"
        foreign = publication(namespace="another-project")
        assert (
            await http.post(
                "/api/artifacts",
                headers={**bearer, "X-Artifact-Metadata": foreign.model_dump_json()},
                content=chunks(),
            )
        ).status_code == 403
        case.authority.live = False
        refused = await http.get(f"/api/artifacts/{artifact}/content", headers=bearer)
        assert refused.status_code == 401 and token not in refused.text
