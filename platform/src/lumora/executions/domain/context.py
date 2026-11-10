"""Immutable execution metadata; mutable runtime holders live in the application."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field, JsonValue

from lumora.models import Model
from lumora.services.identity.domain import Identity

# Session staging (SessionInputProjector) sets this tag so OAuth (e.g. Google MCP) looks up
# tokens for the acting human while ``identity`` remains the team (or other owner).
CREDENTIAL_USER_ID_TAG = "credential_user_id"

HITL_ENABLED_TAG = "hitl_enabled"
APPROVAL_RULES_TAG = "approval_rules"


class ExecutionContext(Model):
    """Portable execution metadata with explicit identity and JSON-only tags."""

    session_id: str = ""
    execution_id: str = ""
    root_execution_id: str = ""
    parent_execution_id: str | None = None
    ancestor_execution_ids: tuple[str, ...] = ()
    identity: Identity
    scope: str = "public"
    engine_name: str = ""
    engine_handle: str | None = None

    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_active_at: datetime | None = None
    finished_at: datetime | None = None

    tags: dict[str, JsonValue] = Field(default_factory=dict)

    @property
    def identity_id(self) -> str:
        return self.identity.id

    def with_scope(self, scope: str) -> ExecutionContext:
        return self.model_copy(update={"scope": scope})

    def with_credential_user(self, credential_user_id: str = "") -> ExecutionContext:
        """Copy with per-user OAuth key in ``tags`` (used when ``identity`` is a team).

        A team id is never a valid OAuth credential user, so passing the team's
        own id is silently ignored — callers do not need to pre-filter.
        """
        cu = (credential_user_id or "").strip()
        if not cu or (self.identity.is_team and cu == self.identity.id):
            return self
        tags = dict(self.tags or {})
        tags[CREDENTIAL_USER_ID_TAG] = cu
        return self.model_copy(update={"tags": tags})

    def credential_user_id(self) -> str:
        """Return the credential user id for OAuth lookups.

        For individual sessions this is the identity id.  For team sessions
        the per-member credential user is stored in ``tags``; if absent (e.g.
        the session was not submitted via the HTTP layer) the caller will
        receive an empty string and must handle the missing-credential case.
        """
        cu = (self.tags or {}).get(CREDENTIAL_USER_ID_TAG, "")
        if cu:
            return str(cu).strip()
        if self.identity.is_team:
            return ""
        return self.identity.id

    def with_hitl(self, enabled: bool) -> ExecutionContext:
        """Copy with the HITL-enabled flag in ``tags``.

        Stamped from ``SessionMeta.hitl_enabled`` during staging so that
        nodes configured with ``HITLMode.DYNAMIC`` can read it at runtime.
        """
        tags = dict(self.tags or {})
        tags[HITL_ENABLED_TAG] = enabled
        return self.model_copy(update={"tags": tags})

    @property
    def hitl_enabled(self) -> bool:
        """Whether dynamic HITL is active (sourced from session metadata)."""
        return bool((self.tags or {}).get(HITL_ENABLED_TAG, False))

    def mark_active(self) -> ExecutionContext:
        return self.model_copy(update={"last_active_at": datetime.now(UTC)})

    def mark_finished(self) -> ExecutionContext:
        now = datetime.now(UTC)
        return self.model_copy(update={"finished_at": now, "last_active_at": now})
