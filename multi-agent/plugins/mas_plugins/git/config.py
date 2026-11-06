"""Operator repository bindings are not part of authored workflow inputs."""

from enum import StrEnum
from pathlib import Path
from typing import Self
from urllib.parse import urlsplit

from mas.core.identity import Identity
from mas.domain.repositories import RepositoryId
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitObjectFormat(StrEnum):
    SHA1 = "sha1"
    SHA256 = "sha256"


class GitBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    location: str = Field(min_length=1, max_length=4096, repr=False)
    owners: tuple[Identity, ...] = Field(min_length=1)
    object_format: GitObjectFormat = GitObjectFormat.SHA1

    @field_validator("location")
    @classmethod
    def permitted_location(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("Repository location must not contain control characters")
        if Path(value).is_absolute():
            return value
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Expected an absolute local path or credential-free HTTPS repository")
        return value


class GitSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UNIFAI_GIT_", extra="ignore", hide_input_in_errors=True, populate_by_name=True
    )
    repositories: dict[RepositoryId, GitBinding] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=120, ge=1, le=1800)
    workspace_root: Path = Field(
        default=Path("/tmp/unifai-workspaces"), validation_alias="UNIFAI_WORKSPACE_ROOT"
    )

    @model_validator(mode="after")
    def absolute_root(self) -> Self:
        if not self.workspace_root.is_absolute():
            raise ValueError("Git workspace root must be absolute")
        return self
