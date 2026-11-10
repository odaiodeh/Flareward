"""Workspace preparation borrows owned ports and drains every opened artifact stream."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import create_autospec

import pytest
from support.artifacts import chunks

from lumora.executions.domain.context import ExecutionContext
from lumora.services.artifacts.domain.models import BlobArtifactRef
from lumora.services.artifacts.ports import ArtifactGateway, WorkspaceFiles
from lumora.services.artifacts.preparation import ArtifactWorkspacePreparation
from lumora.services.identity.domain import Identity
from lumora.services.workspaces.domain.files import ArtifactFile, WorkspaceFile


@pytest.mark.parametrize("failure", [None, PermissionError("denied"), asyncio.CancelledError()])
async def test_preparation_preserves_binding_and_closes_stream_on_every_outcome(failure):
    gateway = create_autospec(ArtifactGateway, instance=True)
    files = create_autospec(WorkspaceFiles, instance=True)
    reference = BlobArtifactRef(artifact_id="a" * 64, sha256="b" * 64, size_bytes=5)
    context = ExecutionContext(
        root_execution_id="root", execution_id="child", identity=Identity.user("owner")
    )
    closed, materialized = [], []

    @asynccontextmanager
    async def opened(artifact):
        assert artifact == reference
        try:
            yield chunks(b"input")
        finally:
            closed.append(True)

    async def materialize(file, artifact, content, execution):
        assert artifact == reference and execution == context
        if failure is not None:
            raise failure
        materialized.append((file, b"".join([chunk async for chunk in content])))

    gateway.open.side_effect, files.materialize.side_effect = opened, materialize
    service = ArtifactWorkspacePreparation(gateway, files)
    request = (ArtifactFile(artifact=reference, path="src/file.py"),)
    if failure is None:
        await service.prepare(request, "root/isolated/work", context)
        assert materialized == [
            (WorkspaceFile(workspace="root/isolated/work", path="src/file.py"), b"input")
        ]
    else:
        with pytest.raises(type(failure)):
            await service.prepare(request, "root/isolated/work", context)
    assert closed == [True]
