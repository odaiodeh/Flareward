"""Small file handoff keeps storage authority outside the producing environment."""

from flareward.elements.operation import BaseOperation, OperationContext
from flareward.services.artifacts.domain.models import (
    BlobArtifactRef,
    ContentIdentity,
    InlineContent,
)
from flareward.services.artifacts.inline_content import collect_content, content_chunks
from flareward.services.artifacts.ports import (
    ArtifactGateway,
    ArtifactLimitExceeded,
    WorkspaceFiles,
)
from flareward.services.workspaces.domain.files import InlineFile, WorkspaceFile
from plugins.artifacts.elements.operations import PublishedArtifact, file_publication


class LoadArtifactContent(BaseOperation[BlobArtifactRef, InlineContent]):
    def __init__(self, gateway: ArtifactGateway, max_bytes: int) -> None:
        self._gateway, self._max_bytes = gateway, max_bytes

    async def execute(self, request: BlobArtifactRef, context: OperationContext) -> InlineContent:
        if request.size_bytes > self._max_bytes:
            raise ArtifactLimitExceeded("Artifact exceeds its content transfer limit")
        async with self._gateway.open(request) as content:
            return await collect_content(
                content,
                ContentIdentity(sha256=request.sha256, size_bytes=request.size_bytes),
                self._max_bytes,
            )


class ReadWorkspaceContent(BaseOperation[WorkspaceFile, InlineFile]):
    def __init__(self, files: WorkspaceFiles, max_bytes: int) -> None:
        self._files, self._max_bytes = files, max_bytes

    async def execute(self, request: WorkspaceFile, context: OperationContext) -> InlineFile:
        async with self._files.source(request, context.execution) as source:
            content = await collect_content(source.content, source.identity, self._max_bytes)
        return InlineFile(path=request.path, content=content)


class PublishFileContent(BaseOperation[InlineFile, PublishedArtifact]):
    def __init__(self, gateway: ArtifactGateway, namespace: str) -> None:
        self._gateway, self._namespace = gateway, namespace

    async def execute(self, request: InlineFile, context: OperationContext) -> PublishedArtifact:
        if request.content.identity.size_bytes > self._gateway.max_bytes:
            raise ArtifactLimitExceeded("Content exceeds its publication byte limit")
        manifest = file_publication(
            request.content.identity, request.path, self._namespace, context
        )
        record = await self._gateway.publish(manifest, content_chunks(request.content))
        return PublishedArtifact(artifact=record.reference)
