"""Provider and file-operation registrations use existing dependency references and factories."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from flareward.elements.construction.context import ElementBuildContext
from flareward.elements.factory import BaseFactory
from flareward.elements.specification import BaseElementSpec
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.domain.references import ProviderRef
from flareward.services.artifacts.domain.models import (
    ArtifactNamespace,
    BlobArtifactRef,
    InlineContent,
)
from flareward.services.artifacts.preparation import (
    ArtifactWorkspacePreparation,
    InlineWorkspacePreparation,
)
from flareward.services.workspaces.domain.files import InlineFile, WorkspaceFile, WorkspaceMode
from plugins.artifacts.elements.content_operations import (
    LoadArtifactContent,
    PublishFileContent,
    ReadWorkspaceContent,
)
from plugins.artifacts.elements.filesystem import WorkspaceFileSystem
from plugins.artifacts.elements.http import ArtifactTransportSettings, HTTPArtifactGateway
from plugins.artifacts.elements.operations import (
    MaterializeArtifact,
    MaterializedArtifact,
    MaterializeFileOperation,
    PublishedArtifact,
    PublishFileOperation,
)


class ArtifactConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    access_token: SecretStr | None = Field(default=None, repr=False, min_length=1)


class ArtifactStoreConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    store: ProviderRef


class PublishFileConfig(ArtifactStoreConfig):
    namespace: ArtifactNamespace = "default"


class MaterializeFileConfig(ArtifactStoreConfig):
    workspace: str = Field(default="work", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
    workspace_mode: WorkspaceMode = WorkspaceMode.ISOLATED


class ContentTransferConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_bytes: int = Field(default=65_536, ge=1, le=1_048_576)


class LoadContentConfig(ArtifactStoreConfig, ContentTransferConfig):
    pass


def _workspace_files(max_bytes: int) -> WorkspaceFileSystem:
    return WorkspaceFileSystem(
        Path(os.environ.get("FLAREWARD_WORKSPACE_ROOT", "/tmp/flareward-workspaces")),
        max_bytes=max_bytes,
    )


class ArtifactConnectionFactory(BaseFactory[ArtifactConnection, HTTPArtifactGateway]):
    def accepts(self, cfg: ArtifactConnection, element_type: str) -> bool:
        return element_type == "artifact_store"

    def create(self, cfg: ArtifactConnection, **dependencies: Any) -> HTTPArtifactGateway:
        deps: ElementBuildContext = dependencies["deps"]
        if deps.execution_ctx is None:
            raise ValueError("Artifact transfer requires execution identity")
        return HTTPArtifactGateway(
            ArtifactTransportSettings.model_validate({}),
            deps.execution_ctx.context,
            cfg.access_token,
            source=deps.workflow_credentials,
        )


class PublishFileFactory(BaseFactory[PublishFileConfig, PublishFileOperation]):
    def accepts(self, cfg: PublishFileConfig, element_type: str) -> bool:
        return element_type == "publish_artifact"

    def create(self, cfg: PublishFileConfig, **dependencies: Any) -> PublishFileOperation:
        store = dependencies["store"]
        files = _workspace_files(store.max_bytes)
        return PublishFileOperation(store, files, cfg.namespace)


class MaterializeFileFactory(BaseFactory[MaterializeFileConfig, MaterializeFileOperation]):
    def accepts(self, cfg: MaterializeFileConfig, element_type: str) -> bool:
        return element_type == "materialize_artifact"

    def create(self, cfg: MaterializeFileConfig, **dependencies: Any) -> MaterializeFileOperation:
        store = dependencies["store"]
        files = _workspace_files(store.max_bytes)
        return MaterializeFileOperation(store, files, cfg.workspace, cfg.workspace_mode)


class WorkspacePreparationFactory(BaseFactory[ArtifactStoreConfig, ArtifactWorkspacePreparation]):
    def accepts(self, cfg: ArtifactStoreConfig, element_type: str) -> bool:
        return element_type == "artifact_workspace"

    def create(self, cfg: ArtifactStoreConfig, **dependencies: Any) -> ArtifactWorkspacePreparation:
        store = dependencies["store"]
        files = _workspace_files(store.max_bytes)
        return ArtifactWorkspacePreparation(store, files)


class LoadContentFactory(BaseFactory[LoadContentConfig, LoadArtifactContent]):
    def accepts(self, cfg: LoadContentConfig, element_type: str) -> bool:
        return element_type == "load_artifact_content"

    def create(self, cfg: LoadContentConfig, **dependencies: Any) -> LoadArtifactContent:
        return LoadArtifactContent(dependencies["store"], cfg.max_bytes)


class ReadContentFactory(BaseFactory[ContentTransferConfig, ReadWorkspaceContent]):
    def accepts(self, cfg: ContentTransferConfig, element_type: str) -> bool:
        return element_type == "read_workspace_content"

    def create(self, cfg: ContentTransferConfig, **dependencies: Any) -> ReadWorkspaceContent:
        return ReadWorkspaceContent(_workspace_files(cfg.max_bytes), cfg.max_bytes)


class PublishContentFactory(BaseFactory[PublishFileConfig, PublishFileContent]):
    def accepts(self, cfg: PublishFileConfig, element_type: str) -> bool:
        return element_type == "publish_file_content"

    def create(self, cfg: PublishFileConfig, **dependencies: Any) -> PublishFileContent:
        return PublishFileContent(dependencies["store"], cfg.namespace)


class InlinePreparationFactory(BaseFactory[ContentTransferConfig, InlineWorkspacePreparation]):
    def accepts(self, cfg: ContentTransferConfig, element_type: str) -> bool:
        return element_type == "inline_workspace"

    def create(self, cfg: ContentTransferConfig, **dependencies: Any) -> InlineWorkspacePreparation:
        return InlineWorkspacePreparation(_workspace_files(cfg.max_bytes))


class ArtifactConnectionSpec(BaseElementSpec):
    category = ResourceCategory.PROVIDER
    type_key = "artifact_store"
    name = "Artifact store"
    description = "Scoped authenticated artifact transfer through the configured platform endpoint"
    config_schema = ArtifactConnection
    factory_cls = ArtifactConnectionFactory


class PublishFileSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "publish_artifact"
    name = "Publish artifact"
    description = "Publish verified workspace bytes outside the execution environment"
    config_schema = PublishFileConfig
    factory_cls = PublishFileFactory
    input_schema = WorkspaceFile
    result_schema = PublishedArtifact


class MaterializeFileSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "materialize_artifact"
    name = "Materialize artifact"
    description = "Verify and atomically materialize an artifact in the current execution workspace"
    config_schema = MaterializeFileConfig
    factory_cls = MaterializeFileFactory
    input_schema = MaterializeArtifact
    result_schema = MaterializedArtifact


class WorkspacePreparationSpec(BaseElementSpec):
    category = ResourceCategory.PROVIDER
    type_key = "artifact_workspace"
    name = "Artifact workspace preparation"
    description = "Stage immutable input files into the workspace selected by a coding operation"
    config_schema = ArtifactStoreConfig
    factory_cls = WorkspacePreparationFactory


class LoadContentSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "load_artifact_content"
    name = "Load artifact content"
    description = "Read bounded verified bytes without delegating artifact-store authority"
    config_schema = LoadContentConfig
    factory_cls = LoadContentFactory
    input_schema = BlobArtifactRef
    result_schema = InlineContent


class ReadContentSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "read_workspace_content"
    name = "Read workspace content"
    description = "Return a bounded contained file value without a storage credential"
    config_schema = ContentTransferConfig
    factory_cls = ReadContentFactory
    input_schema = WorkspaceFile
    result_schema = InlineFile


class PublishContentSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "publish_file_content"
    name = "Publish file content"
    description = "Publish a bounded file value through the caller's scoped artifact authority"
    config_schema = PublishFileConfig
    factory_cls = PublishContentFactory
    input_schema = InlineFile
    result_schema = PublishedArtifact


class InlinePreparationSpec(BaseElementSpec):
    category = ResourceCategory.PROVIDER
    type_key = "inline_workspace"
    name = "Inline workspace preparation"
    description = "Stage bounded input file content without acquiring storage credentials"
    config_schema = ContentTransferConfig
    factory_cls = InlinePreparationFactory


ELEMENT_SPECIFICATIONS = (
    ArtifactConnectionSpec,
    PublishFileSpec,
    MaterializeFileSpec,
    WorkspacePreparationSpec,
    LoadContentSpec,
    ReadContentSpec,
    PublishContentSpec,
    InlinePreparationSpec,
)
