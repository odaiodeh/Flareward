"""Bounded artifact capabilities; credentials are not artifact references or program inputs."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_serializer,
    model_validator,
)

from mas.core.identity import Identity
from mas.domain.artifacts import ArtifactId, ArtifactNamespace
from mas.domain.credential_grants import WorkflowGrant


class ArtifactAction(StrEnum):
    READ = "read"
    PUBLISH = "publish"


class ArtifactAccessScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    actions: frozenset[ArtifactAction] = Field(min_length=1)
    namespaces: frozenset[ArtifactNamespace] = Field(default_factory=frozenset, max_length=32)
    artifact_ids: frozenset[ArtifactId] = Field(default_factory=frozenset, max_length=128)
    max_bytes: int = Field(default=67_108_864, ge=1, le=1_073_741_824)

    @model_validator(mode="after")
    def bounded_access(self) -> Self:
        if ArtifactAction.PUBLISH in self.actions and not self.namespaces:
            raise ValueError("Publication access requires explicit namespaces")
        if ArtifactAction.READ in self.actions and not (self.namespaces or self.artifact_ids):
            raise ValueError("Read access requires namespaces or artifact identities")
        return self

    @field_serializer("actions", "namespaces", "artifact_ids")
    def ordered(self, values: frozenset[str] | frozenset[ArtifactAction]) -> list[str]:
        return [str(value) for value in sorted(values)]

    def allows(self, action: ArtifactAction, namespace: str, artifact_id: str = "") -> bool:
        return action in self.actions and (
            namespace in self.namespaces
            or (action == ArtifactAction.READ and artifact_id in self.artifact_ids)
        )


class ArtifactAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    scope: ArtifactAccessScope
    ttl_seconds: int = Field(default=3600, ge=60, le=2_592_000)


class ArtifactAccessGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    grant_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    owner: Identity
    scope: ArtifactAccessScope
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    revoked: bool = False


class ArtifactWorkflowScope(ArtifactAccessScope):
    root_execution_id: str = Field(min_length=1, max_length=256)


class ArtifactWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    scope: ArtifactWorkflowScope
    ttl_seconds: int = Field(ge=1, le=2_592_000)
    renewable_for_seconds: int | None = Field(default=None, strict=True, ge=1, le=2_592_000)

    @model_validator(mode="after")
    def valid_renewal(self) -> Self:
        if self.renewable_for_seconds is not None and self.renewable_for_seconds < self.ttl_seconds:
            raise ValueError("Credential renewal horizon must cover its initial lease")
        return self


class ArtifactWorkflowGrant(WorkflowGrant):
    scope: ArtifactWorkflowScope


class StoredArtifactWorkflowAccess(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    grant: ArtifactWorkflowGrant
    secret_sha256: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)


class StoredArtifactAccess(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    grant: ArtifactAccessGrant
    secret_sha256: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)


@dataclass(frozen=True)
class IssuedArtifactAccess:
    grant: ArtifactAccessGrant
    credential: SecretStr


@dataclass(frozen=True)
class ArtifactActor:
    identity: Identity
    scope: ArtifactAccessScope | None = None
