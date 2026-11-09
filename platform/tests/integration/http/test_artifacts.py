"""Authenticated native artifact APIs stream bytes and survive actual API restart."""

import asyncio
import hashlib

import httpx
import pytest
from runengine.adapters.coordination.config import LocalHostConfig
from starlette.requests import ClientDisconnect
from support.artifacts import chunks, publication
from support.server import api_process

from flareward.api.app import create_app
from flareward.api.artifacts import ArtifactResponse
from flareward.bootstrap.settings.platform_settings import PlatformSettings
from flareward.services.artifacts.adapters.filesystem import FileArtifactRepository
from flareward.services.artifacts.domain.models import ArtifactRecord, BlobArtifactRef
from flareward.services.artifacts.service import ArtifactService
from flareward.services.identity.domain import Identity


async def test_artifact_bytes_and_metadata_survive_real_api_restart_and_enforce_owner(tmp_path):
    settings = PlatformSettings(
        host=LocalHostConfig(),
        storage="memory",
        authentication="development",
        development_user="owner",
        artifact_directory=tmp_path / "objects",
    )
    data = b"durable candidate\n"
    metadata = publication(data).model_copy(update={"name": "candidate-\u03bb.txt"})
    async with api_process(settings, tmp_path / "first.log") as http:
        response = await http.post(
            "/api/artifacts",
            content=chunks(data),
            headers={"X-Artifact-Metadata": metadata.model_dump_json(ensure_ascii=True)},
        )
        assert response.status_code == 201, response.text
        record = response.json()
        retry = await http.post(
            "/api/artifacts",
            content=chunks(data),
            headers={"X-Artifact-Metadata": metadata.model_dump_json(ensure_ascii=True)},
        )
        assert retry.status_code == 201 and retry.json() == record
    identifier = record["reference"]["artifact_id"]
    async with api_process(settings, tmp_path / "restarted.log") as http:
        assert (await http.get(f"/api/artifacts/{identifier}")).json() == record
        content = await http.get(f"/api/artifacts/{identifier}/content")
        assert content.status_code == 200 and content.content == data
        assert hashlib.sha256(content.content).hexdigest() == record["reference"]["sha256"]
        assert content.headers["etag"] == '"' + record["reference"]["sha256"] + '"'
        assert content.headers["cache-control"] == "private, no-store"
        assert content.headers["content-disposition"] == "attachment"
        assert "sandbox" in content.headers["content-security-policy"]
    async with api_process(
        settings.model_copy(update={"development_user": "other"}), tmp_path / "foreign.log"
    ) as http:
        assert (await http.get(f"/api/artifacts/{identifier}")).status_code == 404
        assert (await http.get(f"/api/artifacts/{identifier}/content")).status_code == 404


async def test_artifact_http_admission_integrity_and_conflicts_are_safe(platform, tmp_path):
    async def authenticate(request):
        return platform.owner

    root = tmp_path / "objects"
    app = create_app(
        platform.programs,
        platform.executions,
        authenticate,
        artifacts=ArtifactService(FileArtifactRepository(root), max_bytes=9),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:

        async def upload(metadata, data=b"candidate"):
            return await http.post(
                "/api/artifacts",
                content=chunks(data),
                headers={"X-Artifact-Metadata": metadata.model_dump_json()},
            )

        assert (
            await upload(publication(b"too big content"), b"too big content")
        ).status_code == 413
        assert (await upload(publication(), b"different")).status_code == 422
        assert not list(root.iterdir())
        first = await upload(publication())
        assert first.status_code == 201, first.text
        assert (await upload(publication(b"changed"), b"changed")).status_code == 409
        forged = await http.post(
            "/api/artifacts",
            content=b"private-body",
            headers={"X-Artifact-Metadata": '{"owner":"forged-private-value"}'},
        )
        assert forged.status_code == 422 and "forged-private-value" not in forged.text
        assert "private-body" not in forged.text and str(root) not in forged.text


@pytest.mark.parametrize("version, failure", [("2.3", OSError), ("2.4", ClientDisconnect)])
async def test_artifact_response_closes_the_owned_stream_on_disconnect(version, failure):
    released = []
    disconnected = asyncio.Event()

    async def body():
        try:
            yield b"data"
        finally:
            released.append(True)

    async def receive():
        await disconnected.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body":
            disconnected.set()
            raise OSError("Disconnected client")

    record = ArtifactRecord(
        reference=BlobArtifactRef(artifact_id="0" * 64, sha256="1" * 64, size_bytes=4),
        owner=Identity.user("owner"),
        namespace="default",
        name="candidate",
        media_type="text/plain",
    )
    response = ArtifactResponse(body(), record)
    with pytest.raises(failure):
        await response({"type": "http", "asgi": {"spec_version": version}}, receive, send)
    assert released == [True]
