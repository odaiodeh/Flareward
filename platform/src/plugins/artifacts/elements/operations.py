"""Reusable file handoff behavior depends on transfer and workspace ports, never backend SDKs."""

import hashlib
import json
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from lumora.elements.operation import BaseOperation, OperationContext
from lumora.services.artifacts.domain.models import (
    BlobArtifactRef,
    ContentIdentity,
    PublishArtifact,
)
from lumora.services.artifacts.ports import ArtifactGateway, WorkspaceFiles
from lumora.services.workspaces.domain.files import WorkspaceFile, WorkspaceLayout, WorkspaceMode


class PublishedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    artifact: BlobArtifactRef


class MaterializeArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    artifact: BlobArtifactRef
    path: str = Field(min_length=1, max_length=4096)


class MaterializedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    artifact: BlobArtifactRef
    workspace: str
    path: str


def file_publication(
    identity: ContentIdentity, path: str, namespace: str, context: OperationContext
) -> PublishArtifact:
    execution = context.execution
    if not execution.execution_id or not execution.root_execution_id:
        raise ValueError("Publication requires execution identity")
    return PublishArtifact(
        **identity.model_dump(),
        namespace=namespace,
        key=hashlib.sha256(
            json.dumps(
                [execution.root_execution_id, execution.execution_id, context.key, path],
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        name=PurePosixPath(path).name,
    )


class PublishFileOperation(BaseOperation[WorkspaceFile, PublishedArtifact]):
    def __init__(self, gateway: ArtifactGateway, files: WorkspaceFiles, namespace: str) -> None:
        self._gateway, self._files, self._namespace = gateway, files, namespace

    async def execute(self, request: WorkspaceFile, context: OperationContext) -> PublishedArtifact:
        if not context.execution.execution_id or not context.execution.root_execution_id:
            raise ValueError("Publication requires execution identity")
        async with self._files.source(request, context.execution) as source:
            manifest = file_publication(source.identity, request.path, self._namespace, context)
            record = await self._gateway.publish(manifest, source.content)
        return PublishedArtifact(artifact=record.reference)


class MaterializeFileOperation(BaseOperation[MaterializeArtifact, MaterializedArtifact]):
    def __init__(
        self,
        gateway: ArtifactGateway,
        files: WorkspaceFiles,
        workspace: str,
        mode: WorkspaceMode = WorkspaceMode.ISOLATED,
    ) -> None:
        self._gateway, self._files, self._workspace, self._mode = gateway, files, workspace, mode

    async def execute(
        self, request: MaterializeArtifact, context: OperationContext
    ) -> MaterializedArtifact:
        execution = context.execution
        workspace = WorkspaceLayout.binding(
            execution.root_execution_id,
            execution.execution_id,
            context.key,
            self._workspace,
            self._mode,
        )
        file = WorkspaceFile(workspace=workspace, path=request.path)
        async with self._gateway.open(request.artifact) as content:
            await self._files.materialize(file, request.artifact, content, execution)
        return MaterializedArtifact(
            artifact=request.artifact, workspace=file.workspace, path=file.path
        )
