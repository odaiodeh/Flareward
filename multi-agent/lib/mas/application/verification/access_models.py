"""Workflow capabilities can manage scoped plans, never submit verifier evidence."""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_serializer,
    model_validator,
)

from mas.core.identity import Identity
from mas.domain.credential_grants import WorkflowGrant

type VerificationPolicyId = Annotated[str, Field(min_length=1, max_length=128)]


def verification_credential_key(owner: Identity, root_execution_id: str) -> str:
    return hashlib.sha256(
        json.dumps([owner.type.value, owner.id, root_execution_id], separators=(",", ":")).encode()
    ).hexdigest()


class VerificationAction(StrEnum):
    CREATE = "create"
    READ = "read"
    CANCEL = "cancel"
    RUN_CHECK = "run_check"


class VerificationPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    policies: frozenset[VerificationPolicyId] = Field(min_length=1, max_length=32)
    actions: frozenset[VerificationAction] = Field(min_length=1)

    @field_serializer("policies", "actions")
    def ordered(self, values: frozenset[str] | frozenset[VerificationAction]) -> list[str]:
        return sorted(str(value) for value in values)

    def allows(self, action: VerificationAction, policy: str) -> bool:
        return action in self.actions and policy in self.policies


class VerificationAccessScope(VerificationPermissions):
    root_execution_id: str = Field(min_length=1, max_length=128)


class VerificationAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    scope: VerificationAccessScope
    ttl_seconds: int = Field(default=3600, ge=60, le=2_592_000)
    renewable_for_seconds: int | None = Field(default=None, strict=True, ge=60, le=2_592_000)

    @model_validator(mode="after")
    def valid_renewal(self) -> Self:
        if self.renewable_for_seconds is not None and self.renewable_for_seconds < self.ttl_seconds:
            raise ValueError("Credential renewal horizon must cover its initial lease")
        return self


class VerificationAccessGrant(WorkflowGrant):
    scope: VerificationAccessScope


class StoredVerificationAccess(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    grant: VerificationAccessGrant
    secret_sha256: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)


@dataclass(frozen=True)
class IssuedVerificationAccess:
    grant: VerificationAccessGrant
    credential: SecretStr


@dataclass(frozen=True)
class VerificationActor:
    identity: Identity
    scope: VerificationAccessScope | None = None
