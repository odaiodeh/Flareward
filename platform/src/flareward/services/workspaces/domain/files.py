"""Logical file bindings and workspace isolation; no filesystem operations live here."""

import hashlib
from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

from flareward.services.artifacts.domain.models import BlobArtifactRef, InlineContent


class WorkspaceMode(StrEnum):
    ISOLATED = "isolated"
    SHARED = "shared"


class WorkspaceLayout:
    @staticmethod
    def binding(root: str, execution: str, key: str, name: str, mode: WorkspaceMode) -> str:
        if not root or not execution or not key:
            raise ValueError("Workspace requires root, execution and invocation identity")
        namespace = hashlib.sha256(root.encode()).hexdigest()
        if mode == WorkspaceMode.ISOLATED:
            namespace += "/" + hashlib.sha256(f"{execution}\0{key}".encode()).hexdigest()
        return f"{namespace}/{name}"


class WorkspaceFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    workspace: str = Field(min_length=1, max_length=4096)
    path: str = Field(min_length=1, max_length=4096)

    @field_validator("workspace", "path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            path.is_absolute()
            or not path.parts
            or ".." in path.parts
            or "\\" in value
            or "\0" in value
        ):
            raise ValueError("Workspace paths must be relative and contained")
        return value


class ArtifactFile(BaseModel):
    """Immutable input content and its relative destination inside an owned workspace."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    artifact: BlobArtifactRef
    path: str = Field(min_length=1, max_length=4096)

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return WorkspaceFile.relative_path(value)


class InlineFile(BaseModel):
    """An explicitly bounded file value, separate from its eventual storage identity."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    path: str = Field(min_length=1, max_length=4096)
    content: InlineContent

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return WorkspaceFile.relative_path(value)


type InputFile = ArtifactFile | InlineFile
