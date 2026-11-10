"""Real directory-handle isolation and atomic materialization, without provider or service mocks."""

import asyncio
import os

import pytest
from support.artifacts import chunks, publication

from lumora.executions.domain.context import ExecutionContext
from lumora.services.artifacts.domain.models import BlobArtifactRef
from lumora.services.artifacts.ports import (
    ArtifactConflict,
    ArtifactCredentialError,
    ArtifactIntegrityError,
)
from lumora.services.identity.domain import Identity
from lumora.services.workspaces.domain.files import WorkspaceFile, WorkspaceLayout, WorkspaceMode
from plugins.artifacts.elements.filesystem import WorkspaceFileSystem


@pytest.fixture
def files_case(tmp_path):
    context = ExecutionContext(
        identity=Identity.user("owner"), root_execution_id="root", execution_id="call"
    )
    file = WorkspaceFile(
        workspace=WorkspaceLayout.binding("root", "call", "work", "work", WorkspaceMode.ISOLATED),
        path="source.txt",
    )
    root = tmp_path / "compute"
    workspace = root / file.workspace
    workspace.mkdir(parents=True)
    return WorkspaceFileSystem(root, max_bytes=1024), context, file, workspace, tmp_path


async def test_source_rejects_symlinks_and_other_root_bindings(files_case):
    files, context, file, workspace, tmp_path = files_case
    outside = tmp_path / "private"
    outside.write_text("private-content")
    (workspace / file.path).symlink_to(outside)
    with pytest.raises(PermissionError) as error:
        async with files.source(file, context):
            pytest.fail("Symlink source must not be opened")
    assert str(tmp_path) not in str(error.value)
    other = file.model_copy(update={"workspace": "0" * 64 + "/work"})
    with pytest.raises(PermissionError):
        async with files.source(other, context):
            pytest.fail("Other execution workspace must not be opened")


async def test_named_pipe_is_rejected_without_blocking_an_owned_thread(files_case):
    files, context, file, workspace, _ = files_case
    pipe = workspace / file.path
    os.mkfifo(pipe)

    async def attempt():
        with pytest.raises(PermissionError):
            async with files.source(file, context):
                pytest.fail("Nonregular source was opened")

    task = asyncio.create_task(attempt())
    _, pending = await asyncio.wait({task}, timeout=0.5)
    if pending:
        # Unblock a regressed blocking open before failing, so the test owns no stuck thread.
        descriptor = await asyncio.to_thread(os.open, pipe, os.O_WRONLY | os.O_NONBLOCK)
        os.close(descriptor)
    await task
    assert not pending


async def test_materialization_is_atomic_idempotent_and_never_blindly_replaces(files_case):
    files, context, file, workspace, _ = files_case
    manifest = publication()
    reference = BlobArtifactRef(
        artifact_id="0" * 64, sha256=manifest.sha256, size_bytes=manifest.size_bytes
    )
    await files.materialize(file, reference, chunks(), context)
    await files.materialize(file, reference, chunks(), context)
    assert (workspace / file.path).read_bytes() == b"candidate"
    with pytest.raises(ArtifactIntegrityError):
        await files.materialize(
            file.model_copy(update={"path": "broken"}), reference, chunks(b"different"), context
        )
    assert not (workspace / "broken").exists()
    (workspace / file.path).write_bytes(b"changed")
    with pytest.raises(ArtifactConflict):
        await files.materialize(file, reference, chunks(), context)
    assert (workspace / file.path).read_bytes() == b"changed"
    assert not list(workspace.glob(".artifact-*"))


async def test_cancelled_materialization_has_no_partial_destination(files_case):
    files, context, file, workspace, _ = files_case
    manifest = publication()
    reference = BlobArtifactRef(
        artifact_id="0" * 64, sha256=manifest.sha256, size_bytes=manifest.size_bytes
    )
    entered = asyncio.Event()

    async def incomplete():
        yield b"can"
        entered.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(files.materialize(file, reference, incomplete(), context))
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not (workspace / file.path).exists() and not list(workspace.glob(".artifact-*"))


@pytest.mark.parametrize("consumer", ["publish", "materialize"])
async def test_workspace_io_does_not_reclassify_transfer_credential_errors(files_case, consumer):
    files, context, file, workspace, _ = files_case
    error = ArtifactCredentialError("Artifact credential was revoked")
    with pytest.raises(ArtifactCredentialError) as failure:
        if consumer == "publish":
            (workspace / file.path).write_bytes(b"candidate")
            async with files.source(file, context):
                raise error
        else:

            async def denied():
                yield b"can"
                raise error

            manifest = publication()
            reference = BlobArtifactRef(
                artifact_id="0" * 64, sha256=manifest.sha256, size_bytes=manifest.size_bytes
            )
            await files.materialize(file, reference, denied(), context)
    assert failure.value is error
    assert not list(workspace.glob(".artifact-*"))
