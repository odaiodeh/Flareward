"""Bounded transfers separate file bytes, workspace authority and artifact authority."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import create_autospec

import pytest
from support.artifacts import chunks, inline_content
from support.operations import operation_context

from lumora.services.artifacts.domain.models import ArtifactRecord, BlobArtifactRef
from lumora.services.artifacts.ports import (
    ArtifactGateway,
    ArtifactIntegrityError,
    ArtifactLimitExceeded,
    FileSource,
    WorkspaceFiles,
)
from lumora.services.artifacts.preparation import InlineWorkspacePreparation
from lumora.services.workspaces.domain.files import ArtifactFile, InlineFile, WorkspaceFile
from plugins.artifacts.elements.content_operations import (
    LoadArtifactContent,
    PublishFileContent,
    ReadWorkspaceContent,
)


@pytest.fixture
def source():
    content = inline_content()
    reference = BlobArtifactRef(artifact_id="a" * 64, **content.identity.model_dump())
    return content, reference


@pytest.mark.parametrize("failure", [None, PermissionError("denied"), asyncio.CancelledError()])
async def test_loading_verifies_content_and_closes_the_borrowed_stream(source, failure):
    content, reference = source
    gateway = create_autospec(ArtifactGateway, instance=True)
    closed = []

    @asynccontextmanager
    async def opened(ref):
        assert ref == reference
        try:
            if failure is not None:
                raise failure
            yield chunks(content.decoded())
        finally:
            closed.append(True)

    gateway.open.side_effect = opened
    operation = LoadArtifactContent(gateway, 100)
    if failure is None:
        assert await operation.execute(reference, operation_context()) == content
    else:
        with pytest.raises(type(failure)):
            await operation.execute(reference, operation_context())
    assert closed == [True]


async def test_declared_oversize_refuses_storage_access(source):
    _, reference = source
    gateway = create_autospec(ArtifactGateway, instance=True)
    with pytest.raises(ArtifactLimitExceeded):
        await LoadArtifactContent(gateway, 1).execute(reference, operation_context())
    gateway.open.assert_not_called()


@pytest.mark.parametrize("bytes_returned", [b"changed", b"x" * 101])
async def test_workspace_export_rejects_changed_or_excessive_bytes(source, bytes_returned):
    content, _ = source
    files = create_autospec(WorkspaceFiles, instance=True)
    closed = []

    @asynccontextmanager
    async def opened(file, execution):
        try:
            yield FileSource(content.identity, chunks(bytes_returned))
        finally:
            closed.append(True)

    files.source.side_effect = opened
    with pytest.raises((ArtifactIntegrityError, ArtifactLimitExceeded)):
        await ReadWorkspaceContent(files, 100).execute(
            WorkspaceFile(workspace="root/work", path="answer.py"), operation_context()
        )
    assert closed == [True]


async def test_export_and_publication_preserve_exact_content_and_scoped_intent(source):
    content, reference = source
    files = create_autospec(WorkspaceFiles, instance=True)
    gateway = create_autospec(ArtifactGateway, instance=True)
    gateway.max_bytes = 100
    scope = operation_context()
    request = WorkspaceFile(workspace="root/work", path="src/answer.py")

    @asynccontextmanager
    async def opened(file, execution):
        assert file == request and execution == scope.execution
        yield FileSource(content.identity, chunks(content.decoded()))

    async def publish(manifest, stream):
        assert manifest.namespace == "engineering" and manifest.name == "answer.py"
        assert manifest.sha256 == reference.sha256 and manifest.size_bytes == reference.size_bytes
        assert b"".join([chunk async for chunk in stream]) == content.decoded()
        return ArtifactRecord(
            reference=reference,
            owner=scope.execution.identity,
            namespace=manifest.namespace,
            name=manifest.name,
            media_type=manifest.media_type,
        )

    files.source.side_effect = opened
    gateway.publish.side_effect = publish
    exported = await ReadWorkspaceContent(files, 100).execute(request, scope)
    assert exported == InlineFile(path=request.path, content=content)
    publisher = PublishFileContent(gateway, "engineering")
    assert (await publisher.execute(exported, scope)).artifact == reference
    first = gateway.publish.await_args.args[0].key
    await publisher.execute(exported, scope)
    assert gateway.publish.await_args.args[0].key == first
    await publisher.execute(exported, operation_context(root="other"))
    assert gateway.publish.await_args.args[0].key != first


async def test_inline_preparation_needs_no_gateway_and_refuses_references_before_writing(source):
    content, reference = source
    files = create_autospec(WorkspaceFiles, instance=True)
    service = InlineWorkspacePreparation(files)
    scope = operation_context()
    destination = InlineFile(path="src/answer.py", content=content)

    async def materialize(file, identity, stream, execution):
        assert file == WorkspaceFile(workspace="root/work", path=destination.path)
        assert identity == content.identity and execution == scope.execution
        assert b"".join([chunk async for chunk in stream]) == content.decoded()

    files.materialize.side_effect = materialize
    await service.prepare((destination,), "root/work", scope.execution)
    files.materialize.reset_mock()
    with pytest.raises(ValueError, match="requires file content"):
        await service.prepare(
            (destination, ArtifactFile(artifact=reference, path="other.py")),
            "root/work",
            scope.execution,
        )
    files.materialize.assert_not_awaited()
