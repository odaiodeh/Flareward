"""Secret-free requested capabilities and human approval for one root invocation."""

from typing import Annotated, Self

from pydantic import AfterValidator, AwareDatetime, Field, JsonValue, model_validator

from lumora.json_values import portable_json
from lumora.models import Model
from lumora.services.identity.domain import Identity


class WorkflowAccess(Model):
    purpose: str = Field(pattern=r"^[a-z][a-z0-9_.-]*@[1-9][0-9]*$", max_length=128)
    scope: Annotated[dict[str, JsonValue], AfterValidator(portable_json)]
    ttl_seconds: int = Field(default=3600, strict=True, ge=1, le=2_592_000)
    renewable_for_seconds: int | None = Field(default=None, strict=True, ge=1, le=2_592_000)

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if "root_execution_id" in self.scope:
            raise ValueError("Workflow access derives its root from the invocation")
        if self.renewable_for_seconds is not None and self.renewable_for_seconds < self.ttl_seconds:
            raise ValueError("Credential renewal horizon must cover its initial lease")
        return self

    def for_root(self, root: str) -> dict[str, JsonValue]:
        return {
            "scope": {**self.scope, "root_execution_id": root},
            "ttl_seconds": self.ttl_seconds,
            "renewable_for_seconds": self.renewable_for_seconds,
        }


class WorkflowAccessApproval(Model):
    owner: Identity
    root_execution_id: str = Field(min_length=1)
    approved_by: Identity
    approved_at: AwareDatetime
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    requirements: tuple[WorkflowAccess, ...] = Field(min_length=1, max_length=16)
    consent_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

    @model_validator(mode="after")
    def validate_approval(self) -> Self:
        if (
            not self.owner.id
            or not self.approved_by.is_user
            or not self.approved_by.id
            or (self.owner.is_user and not self.owner.owns(self.approved_by))
        ):
            raise ValueError("Workflow access requires authenticated human approval")
        if len({item.purpose for item in self.requirements}) != len(self.requirements):
            raise ValueError("Workflow access may request each purpose only once")
        return self
