"""Validated reporting projections; operational completion does not establish acceptance."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field

from lumora.executions.domain.models import ExecutionPhase
from lumora.models import Model
from lumora.programs.domain.models import ProgramRef
from lumora.services.identity.domain import IdentityType


class TimeRange(StrEnum):
    TODAY = "today"
    WEEK = "7days"
    MONTH = "30days"
    ALL = "all"

    def since(self, now: datetime) -> datetime | None:
        now = now.astimezone(UTC)
        if self == TimeRange.TODAY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if self == TimeRange.WEEK:
            return now - timedelta(days=7)
        if self == TimeRange.MONTH:
            return now - timedelta(days=30)
        return None


class ResourceCount(Model):
    category: str
    count: int = Field(ge=0)
    types: dict[str, int] = Field(default_factory=dict)


class OwnerOverview(Model):
    blueprint_drafts: int = Field(ge=0)
    program_drafts: int = Field(ge=0)
    observed_active_sessions: int = Field(ge=0)
    blueprint_sessions: dict[str, int] = Field(default_factory=dict)
    resources: tuple[ResourceCount, ...] = ()


class RunCounts(Model):
    run_count: int = Field(ge=0)
    status_breakdown: dict[ExecutionPhase, int]


class OwnerActivity(RunCounts):
    identity_id: str
    identity_type: IdentityType
    programs_used: int = Field(default=0, ge=0)


class ProgramUsage(RunCounts):
    program: ProgramRef
    program_name: str | None = None
    unique_owners: int = Field(default=0, ge=0)
    avg_duration_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    last_run_at: AwareDatetime | None = None

    completion_rate: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)


class ActivityPoint(Model):
    period: str
    count: int = Field(ge=0)


class SystemReport(Model):
    root_executions: int = Field(ge=0)
    unique_owners: int = Field(ge=0)
    programs_used: int = Field(ge=0)
    status_breakdown: dict[ExecutionPhase, int]
    owner_activity: tuple[OwnerActivity, ...] = Field(max_length=100)
    top_owners: tuple[OwnerActivity, ...] = Field(max_length=8)
    owner_offset: int = Field(ge=0)
    owner_limit: int = Field(ge=1, le=100)
    top_programs: tuple[ProgramUsage, ...] = Field(max_length=10)
    time_series: tuple[ActivityPoint, ...] = Field(max_length=366)
    time_series_truncated: bool
    generated_at: AwareDatetime
    observation: Literal["stored_execution_projection"] = "stored_execution_projection"
