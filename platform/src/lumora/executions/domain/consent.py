"""Bounded human consent for an exact recurring source, distinct from root credentials."""

from datetime import timedelta
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from lumora.executions.domain.access import WorkflowAccess
from lumora.models import Model
from lumora.services.identity.domain import Identity


class WorkflowConsent(Model):
    consent_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    source_id: str = Field(min_length=1)
    owner: Identity
    approved_by: Identity
    approved_at: AwareDatetime
    expires_at: AwareDatetime
    definition_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    prepared_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    requirements: tuple[WorkflowAccess, ...] = Field(min_length=1, max_length=16)
    revoked: bool = False

    @model_validator(mode="after")
    def validate_consent(self) -> Self:
        if (
            not self.owner.id
            or not self.approved_by.is_user
            or not self.approved_by.id
            or (self.owner.is_user and not self.owner.owns(self.approved_by))
            or not self.approved_at < self.expires_at <= self.approved_at + timedelta(days=30)
        ):
            raise ValueError("Workflow consent requires human approval and a bounded lifetime")
        if len({item.purpose for item in self.requirements}) != len(self.requirements):
            raise ValueError("Workflow consent may request each purpose only once")
        return self
