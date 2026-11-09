"""Materialize immutable inputs into a caller-owned workspace using storage ports."""

from flareward.executions.domain.context import ExecutionContext
from flareward.services.artifacts.inline_content import content_chunks
from flareward.services.artifacts.ports import ArtifactGateway, WorkspaceFiles
from flareward.services.workspaces.domain.files import (
    ArtifactFile,
    InlineFile,
    InputFile,
    WorkspaceFile,
)


class ArtifactWorkspacePreparation:
    def __init__(self, gateway: ArtifactGateway, files: WorkspaceFiles) -> None:
        self._gateway, self._files = gateway, files

    async def prepare(
        self, files: tuple[InputFile, ...], workspace: str, context: ExecutionContext
    ) -> None:
        for source in files:
            destination = WorkspaceFile(workspace=workspace, path=source.path)
            if isinstance(source, ArtifactFile):
                async with self._gateway.open(source.artifact) as content:
                    await self._files.materialize(destination, source.artifact, content, context)
            else:
                await self._files.materialize(
                    destination, source.content.identity, content_chunks(source.content), context
                )


class InlineWorkspacePreparation:
    """Stage content without acquiring any artifact-store or workflow credential."""

    def __init__(self, files: WorkspaceFiles) -> None:
        self._files = files

    async def prepare(
        self, files: tuple[InputFile, ...], workspace: str, context: ExecutionContext
    ) -> None:
        if any(not isinstance(file, InlineFile) for file in files):
            raise ValueError("Inline workspace preparation requires file content")
        for source in files:
            assert isinstance(source, InlineFile)
            await self._files.materialize(
                WorkspaceFile(workspace=workspace, path=source.path),
                source.content.identity,
                content_chunks(source.content),
                context,
            )
