"""Human-approved, immutable event subscriptions; delivery is distinct from execution."""

from datetime import timedelta
from typing import Annotated, Self

from pydantic import AfterValidator, AwareDatetime, ConfigDict, Field, JsonValue, model_validator

from flareward.executions.domain.access import WorkflowAccess
from flareward.json_values import portable_json
from flareward.models import Model
from flareward.programs.domain.models import ProgramRef
from flareward.services.identity.domain import Identity


class ProgramEventSource(Model):
    model_config = ConfigDict(hide_input_in_errors=True)
    source_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    name: str = Field(min_length=1, max_length=200)
    owner: Identity
    approved_by: Identity
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    program: ProgramRef
    event_type: str = Field(min_length=1, max_length=128)
    input_schema: Annotated[dict[str, JsonValue], AfterValidator(portable_json)]
    workflow_access: tuple[WorkflowAccess, ...] = Field(default=(), max_length=16)
    prepared_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    revoked: bool = False

    @model_validator(mode="after")
    def approved_source(self) -> Self:
        if (
            not self.owner.id
            or not self.approved_by.is_user
            or not self.approved_by.id
            or (self.owner.is_user and not self.owner.owns(self.approved_by))
            or not self.approved_at < self.expires_at <= self.approved_at + timedelta(days=30)
        ):
            raise ValueError("Event sources require human approval and a bounded lifetime")
        if len({item.purpose for item in self.workflow_access}) != len(self.workflow_access):
            raise ValueError("Event sources may request each workflow purpose only once")
        return self


class ProgramEvent(Model):
    model_config = ConfigDict(hide_input_in_errors=True)
    event_id: str = Field(min_length=1, max_length=256)
    event_type: str = Field(min_length=1, max_length=128)
    inputs: Annotated[JsonValue, AfterValidator(portable_json)]
