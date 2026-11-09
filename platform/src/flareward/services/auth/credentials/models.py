"""
Auth-layer models — scheme-agnostic.

All credential, token, and client-config models live here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from flareward.services.auth.credentials.endpoint_validation import validate_oauth_endpoint


def _is_expired(expires_at: datetime | None, buffer_seconds: int = 60) -> bool:
    """Shared timezone-aware expiry check."""
    if expires_at is None:
        return False
    exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    return exp <= datetime.now(UTC) + timedelta(seconds=buffer_seconds)


class TokenStatus(StrEnum):
    ACTIVE = "active"
    REFRESH_FAILED = "refresh_failed"
    REVOKED = "revoked"


class StaticAuthMethod(StrEnum):
    """Built-in auth dropdown options. Registry servers use free-form identifiers."""

    NONE = "none"
    ACCESS_TOKEN = "access_token"

    @classmethod
    def values(cls) -> frozenset[str]:
        """All static dropdown values (e.g. for reserved-id / bind skips).

        Returns:
            frozenset of reserved static auth identifiers (e.g. ``none``,
            ``access_token``).
        """
        return frozenset(m.value for m in cls)


class TokenSet(BaseModel):
    """Fresh credential set produced by any auth scheme."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    scope: str | None = None

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        return _is_expired(self.expires_at, buffer_seconds)


class StoredCredential(BaseModel):
    """
    Persisted per-user, per-server credential.

    Lookup key: ``(user_id, server_identifier)``.
    """

    id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    server_identifier: str = Field(
        default="",
        description="Auth server issuer URL (e.g. https://accounts.google.com)",
    )
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
    status: TokenStatus = TokenStatus.ACTIVE
    scheme_type: str = "oauth2"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def is_valid(self, buffer_seconds: int = 60) -> bool:
        if self.status != TokenStatus.ACTIVE:
            return False
        return not _is_expired(self.expires_at, buffer_seconds)


class ClientConfig(BaseModel):
    """Client config for an auth server (OAuth app registration, etc.)."""

    client_id: str
    client_secret: str | None = None
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    token_endpoint_auth_method: str = "client_secret_post"
    scopes: list[str] = Field(default_factory=list)
    resource_uri: str | None = None
    extra_authorize_params: dict[str, str] = Field(default_factory=dict)
    protocol_type: str = "oauth2"
    server_identifier: str = ""
    display_name: str = ""
    categories: list[str] = Field(default_factory=list)

    @field_validator("server_identifier")
    @classmethod
    def _normalize_and_reject_reserved_ids(cls, v: str) -> str:
        # Match store normalization (rstrip("/")) before reserved-id checks so
        # values like "none/" cannot bypass and later collide with StaticAuthMethod.
        normalized = (v or "").rstrip("/")
        if normalized in StaticAuthMethod.values():
            raise ValueError(f"server_identifier {v!r} is reserved for static auth methods")
        return normalized

    @field_validator("authorization_endpoint", "token_endpoint")
    @classmethod
    def _validate_oauth_endpoints(cls, v: str, info: ValidationInfo) -> str:
        return validate_oauth_endpoint(v or "", field_name=info.field_name)


class RecoveryResult(BaseModel):
    """Outcome of an attempt_recovery call."""

    model_config = {"frozen": True}

    recovered: bool
    should_retry: bool
    reason: str
    new_token_set: TokenSet | None = None
