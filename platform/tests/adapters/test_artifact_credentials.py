"""Receiver credentials are private, root-bound and cannot fall back after managed failure."""

from unittest.mock import create_autospec

import httpx
import pytest
from pydantic import SecretStr
from support.artifact_workflow import ArtifactWorkflowCase, MemoryArtifactWorkflowRepository

from flareward.executions.domain.context import ExecutionContext
from flareward.services.access.credentials import (
    WorkflowCredentialSource,
    WorkflowCredentialUnavailable,
)
from flareward.services.artifacts.ports import ArtifactCredentialError, ArtifactStorageError
from plugins.artifacts.elements.http import ArtifactTransportSettings, HTTPArtifactGateway


@pytest.mark.parametrize("reason", ["symlink", "public", "oversized", "empty"])
def test_private_artifact_binding_rejects_unsafe_files(tmp_path, reason):
    path = tmp_path / "token"
    path.write_text("secret" if reason != "empty" else " ")
    path.chmod(0o600)
    if reason == "symlink":
        target = tmp_path / "target"
        path.rename(target)
        path.symlink_to(target)
    elif reason == "public":
        path.chmod(0o644)
    elif reason == "oversized":
        path.write_bytes(b"x" * 4097)
    case = ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    gateway = HTTPArtifactGateway(
        ArtifactTransportSettings(endpoint="https://artifacts.invalid", access_file=path),
        ExecutionContext(identity=case.owner, execution_id="root"),
    )
    with pytest.raises(ArtifactCredentialError):
        gateway._file_credential()


async def test_managed_failure_cannot_fall_back_to_an_operator_file(tmp_path):
    path = tmp_path / "operator-token"
    path.write_text("operator-secret")
    path.chmod(0o600)
    source = create_autospec(WorkflowCredentialSource, instance=True)
    source.resolve.side_effect = WorkflowCredentialUnavailable()
    case = ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    gateway = HTTPArtifactGateway(
        ArtifactTransportSettings(endpoint="https://artifacts.invalid", access_file=path),
        ExecutionContext(identity=case.owner, execution_id="root"),
        source=source,
    )
    with pytest.raises(ArtifactStorageError):
        await gateway.prepare_element()


@pytest.mark.parametrize("root", ["root", "another-root"])
async def test_receiver_validates_managed_root_before_transferring(monkeypatch, root):
    case = ArtifactWorkflowCase.create(MemoryArtifactWorkflowRepository())
    _, token = await case.provision()
    grant = await case.service.authenticate(token)
    source = create_autospec(WorkflowCredentialSource, instance=True)
    source.resolve.return_value = SecretStr(token)
    requests = []

    def response(request):
        requests.append(request)
        return httpx.Response(200, json=grant.model_dump(mode="json"))

    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(response), **kwargs),
    )
    context = ExecutionContext(identity=case.owner, execution_id="child", root_execution_id=root)
    gateway = HTTPArtifactGateway(
        ArtifactTransportSettings(endpoint="https://artifacts.invalid"), context, source=source
    )
    try:
        if root == "root":
            await gateway.prepare_element()
            assert gateway.max_bytes == grant.scope.max_bytes
        else:
            with pytest.raises(ArtifactCredentialError):
                await gateway.prepare_element()
        source.resolve.assert_awaited_once_with("artifact@1", case.owner, root)
        assert [request.url.path for request in requests] == ["/api/artifact-access/self"]
    finally:
        await gateway.aclose()
