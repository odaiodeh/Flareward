"""Source identities are independent of managed blob storage and execution engines."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

RepositoryId = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")]
GitCommitId = Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")]


class GitRevision(BaseModel):
    """An immutable source candidate, without transport locations or credentials."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    repository: RepositoryId
    commit: GitCommitId
