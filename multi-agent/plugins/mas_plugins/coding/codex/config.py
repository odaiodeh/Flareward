"""Provider configuration; placement and sandbox policy are receiver-owned."""

from enum import StrEnum

from mas.core.ref.models import ProviderRef
from mas.domain.files import WorkspaceMode
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ReasoningEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CodexConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    api_key: SecretStr | None = Field(default=None, repr=False, min_length=1)
    model: str = Field(min_length=1, description="Explicit API model; no expensive default")
    instructions: str = ""
    workspace: str = Field(default="work", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
    workspace_mode: WorkspaceMode = WorkspaceMode.ISOLATED
    workspace_preparation: ProviderRef | None = None
    reasoning_effort: ReasoningEffort = ReasoningEffort.LOW
    timeout_seconds: float = Field(default=120, ge=1, le=1800, allow_inf_nan=False)
    max_commands: int = Field(default=20, ge=1, le=200)
    max_output_bytes: int = Field(default=1_048_576, ge=1024, le=16_777_216)
