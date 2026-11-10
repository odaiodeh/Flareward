"""Human-issued workflow grant metadata; purpose scopes remain independently typed."""

from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from lumora.services.access.domain.leases import CredentialLease
from lumora.services.identity.domain import Identity


class WorkflowGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    grant_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    owner: Identity
    issued_by: Identity
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    revoked: bool = False
    renewal: CredentialLease | None = None

    @model_validator(mode="after")
    def valid_issuance(self) -> Self:
        if self.renewal is not None:
            self.renewal.validate_interval(self.issued_at, self.expires_at)
        if (
            not self.owner.id
            or not self.issued_by.is_user
            or not self.issued_by.id
            or self.expires_at <= self.issued_at
            or (self.owner.is_user and not self.owner.owns(self.issued_by))
        ):
            raise ValueError("Workflow grant requires valid human issuance and expiry")
        return self
