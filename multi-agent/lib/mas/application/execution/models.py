"""Application requests and persisted execution-delivery contracts."""

import hashlib
import json
from typing import Annotated, Self

from pydantic import AfterValidator, AwareDatetime, Field, JsonValue, model_validator

from mas.domain.execution.access import WorkflowAccess
from mas.domain.execution.budgets import WorkLimits
from mas.domain.execution.placement import PreparedProgramPlacement
from mas.domain.execution_preferences import ExecutionProfileCatalog
from mas.domain.json_values import portable_json
from mas.domain.models import Model
from mas.domain.programs.models import ProgramRef


class SubmissionClaim(Model):
    """Private application delivery lease, never a worker or environment lease."""

    token: str = Field(pattern=r"^[a-f0-9]{32}$")
    expires_at: AwareDatetime


class PreparedExecution(Model):
    """Opaque adapter snapshot; application services persist it without interpreting it."""

    format: str
    payload_json: str
    location: str = ""
    content_digest: str = ""
    work_limits: WorkLimits | None = None
    admitted_profiles: ExecutionProfileCatalog | None = None
    placement: PreparedProgramPlacement | None = None

    @model_validator(mode="after")
    def validate_digest(self) -> Self:
        value = json.loads(self.payload_json)
        if self.location:
            value = {"location": self.location, "request": value}
        if self.work_limits is not None:
            value = {"work_limits": self.work_limits.model_dump(mode="json"), "prepared": value}
        if self.admitted_profiles is not None:
            value = {
                "admitted_profiles": self.admitted_profiles.model_dump(mode="json"),
                "prepared": value,
            }
        if self.placement is not None:
            value = {"placement": self.placement.model_dump(mode="json"), "prepared": value}
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        if self.content_digest and self.content_digest != digest:
            raise ValueError("Prepared execution content digest mismatch")
        object.__setattr__(self, "content_digest", digest)
        return self


class AdmittedExecutionSettings(Model):
    """Safe settings frozen during admission; excludes the adapter payload."""

    work_limits: WorkLimits | None = None
    admitted_profiles: ExecutionProfileCatalog | None = None
    placement: PreparedProgramPlacement | None = None

    @classmethod
    def from_prepared(cls, prepared: PreparedExecution) -> Self:
        return cls(
            work_limits=prepared.work_limits,
            admitted_profiles=prepared.admitted_profiles,
            placement=prepared.placement,
        )


class StartExecution(Model):
    program: ProgramRef
    inputs: Annotated[JsonValue, AfterValidator(portable_json)] = Field(default_factory=dict)
    execution_id: str | None = Field(default=None, min_length=1)
    session_id: str | None = None
    workflow_access: tuple[WorkflowAccess, ...] = Field(default=(), max_length=16)
