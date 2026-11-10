"""Source identities are independent of managed blob storage and execution engines."""

from pathlib import PurePosixPath
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lumora.services.artifacts.domain.models import InlineContent
from lumora.services.workspaces.domain.files import WorkspaceFile

RepositoryId = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")]
GitCommitId = Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")]


class GitRevision(BaseModel):
    """An immutable source candidate, without transport locations or credentials."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    repository: RepositoryId
    commit: GitCommitId


class GitFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    revision: GitRevision
    path: str = Field(min_length=1, max_length=4096)

    @field_validator("path")
    @classmethod
    def contained_path(cls, value: str) -> str:
        return str(PurePosixPath(WorkspaceFile.relative_path(value)))


class GitFileContent(GitFile):
    content: InlineContent
