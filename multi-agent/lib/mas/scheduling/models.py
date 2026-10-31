"""
Workflow scheduling domain models.

Defines the WorkflowSchedule aggregate, ScheduleDefinition value object,
and supporting enums for the workflow scheduling domain.
"""

import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mas.core.identity import Identity

_MIN_INTERVAL = timedelta(minutes=1)

_CRON_FIELD_RE = re.compile(r"^[A-Za-z0-9*/,-]+$")

_VALID_TIMEZONES = frozenset(available_timezones())

_USER_PROMPT_KEY = "user_prompt"


def _is_valid_cron(expression: str) -> bool:
    fields = expression.split()
    if len(fields) != 5:
        return False
    return all(_CRON_FIELD_RE.match(field) for field in fields)


class PromptSource(StrEnum):
    MANUAL = "manual"
    SHORTCUT_COPY = "shortcut_copy"


class ScheduleStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ScheduleOverlapPolicy(StrEnum):
    SKIP = "skip"
    BUFFER_ONE = "buffer_one"
    CANCEL_OTHER = "cancel_other"


class ScheduleDefinition(BaseModel):
    """Value object -- the scheduling configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")

    interval: timedelta | None = None
    cron_expression: str | None = None
    overlap_policy: ScheduleOverlapPolicy = ScheduleOverlapPolicy.SKIP
    timezone: str = "UTC"
    start_at: datetime | None = None
    end_at: datetime | None = None
    remaining_actions: int | None = None
    enabled: bool = True

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @model_validator(mode="after")
    def _exactly_one_trigger(self) -> ScheduleDefinition:
        if not self.interval and not self.cron_expression:
            raise ValueError("Either interval or cron_expression is required")
        if self.interval and self.cron_expression:
            raise ValueError("Specify interval or cron_expression, not both")
        if self.interval is not None and self.interval < _MIN_INTERVAL:
            raise ValueError(f"interval must be at least {_MIN_INTERVAL}")
        if self.cron_expression is not None and not _is_valid_cron(self.cron_expression):
            raise ValueError(
                "cron_expression must be a 5-field cron string (minute hour day month weekday)"
            )
        if self.timezone not in _VALID_TIMEZONES:
            raise ValueError(f"Unknown timezone: {self.timezone}")
        if self.remaining_actions is not None and self.remaining_actions < 0:
            raise ValueError("remaining_actions must be non-negative")
        if self.start_at and self.end_at and self.start_at >= self.end_at:
            raise ValueError("start_at must be before end_at")
        return self


class RunOutcome(StrEnum):
    """Fixed outcome set for scheduled workflow runs."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunStatusEntry(BaseModel):
    """Single entry in the recent-runs ring buffer."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    status: RunOutcome
    started_at: datetime | None = None


class RunStats(BaseModel):
    """Lightweight run-history summary embedded in the schedule aggregate."""

    total_runs: int = 0
    last_run_at: datetime | None = None
    recent_statuses: list[RunStatusEntry] = Field(default_factory=list)


class WorkflowSchedule(BaseModel):
    """Workflow schedule — identity-owned configuration that causes a
    blueprint to execute on a recurring schedule.

    Each tick produces a session.  The schedule is the configuration;
    ``inputs.user_prompt`` is the content; sessions are the output.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    blueprint_id: str
    identity: Identity
    inputs: dict[str, Any] = Field(default_factory=dict)
    source: PromptSource = PromptSource.MANUAL
    schedule: ScheduleDefinition
    schedule_status: ScheduleStatus = ScheduleStatus.ACTIVE
    engine_handle: str | None = None
    completed_at: datetime | None = None
    run_stats: RunStats = Field(default_factory=RunStats)
    credential_user_id: str = ""

    @property
    def user_prompt(self) -> str:
        """Convenience accessor for the prompt text in inputs."""
        return str(self.inputs.get(_USER_PROMPT_KEY, ""))

    @model_validator(mode="after")
    def _require_user_prompt(self) -> WorkflowSchedule:
        raw = self.inputs.get(_USER_PROMPT_KEY)
        if not isinstance(raw, str):
            raise ValueError("inputs.user_prompt is required")
        stripped = raw.strip()
        if not stripped:
            raise ValueError("inputs.user_prompt must not be empty")
        if stripped != raw:
            self.inputs[_USER_PROMPT_KEY] = stripped
        return self
