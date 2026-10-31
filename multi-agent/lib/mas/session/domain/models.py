from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from mas.core.dto import GroupedCount
from mas.core.resource_models import BlueprintExecutionStats
from mas.session.domain.status import SessionStatus


class TimeSeriesPoint(BaseModel):
    """
    Single data point in a time series.

    The period granularity (hourly, daily, monthly) is determined
    by the repository implementation based on the requested time range.
    The period is truncated to the start of the bucket
    (e.g., start of the hour, day, or month).
    """

    period: datetime = Field(
        ...,
        description=(
            "Start of the time bucket (truncated to hour, day, or month depending on granularity)"
        ),
    )
    count: int = Field(..., description="Number of items in this period")


class SystemAnalyticsData(BaseModel):
    """
    Aggregated system analytics data returned by the repository layer.

    Groups session data by user+status and user+blueprint for building
    admin dashboard views (active users, top blueprints, etc.).

    The user_blueprint_counts field serves double duty:
    - User perspective: which blueprints did each user run?
    - Blueprint perspective: which users ran each blueprint?
    Both views are derived from the same (user_id, blueprint_id) grouping.

    The blueprint_stats field provides pre-aggregated execution metrics
    per blueprint (duration, success rate, last run, users list).

    Implementations should optimize for efficiency (e.g., batching
    multiple aggregations into a single database operation).
    """

    user_status_counts: list[GroupedCount] = Field(
        default_factory=list, description="Sessions grouped by user_id and status"
    )
    user_blueprint_counts: list[GroupedCount] = Field(
        default_factory=list,
        description=(
            "Sessions grouped by user_id and blueprint_id (used for both user and blueprint views)"
        ),
    )
    blueprint_stats: list[BlueprintExecutionStats] = Field(
        default_factory=list, description="Per-blueprint aggregated execution metrics"
    )


class SessionMeta(BaseModel):
    """Session metadata — canonical container for all session-level context.

    The model intentionally accepts unknown fields (``extra="allow"``) so that
    callers can attach arbitrary key-value pairs without a schema change.  This
    makes ``POST /session.meta`` a single, forward-compatible write endpoint:
    the GUI can push its full notion of session state in one call and new fields
    are persisted automatically.

    Live/ephemeral fields (``typing_users``, ``participants``) are stored here
    when sent by the caller, but the ``session.meta`` endpoint additionally
    syncs them to the collaboration store (Redis) so real-time features work.
    """

    model_config = ConfigDict(extra="allow")

    title: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    source: str | None = None
    schedule_id: str | None = None
    prompt_text: str | None = None
    status_message: str | None = None
    hitl_enabled: bool = False
    # Live/presence fields — forwarded to the collaboration store when present.
    participants: list[str] | None = None  # user ids currently in the session
    typing_users: list[str] | None = None  # user ids currently typing


class SessionChat(BaseModel):
    """Lightweight projection of a session's chat-relevant graph state."""

    messages: list = Field(default_factory=list)
    output: str = ""
    status: str | None = None
    status_message: str | None = None
    blueprint_id: str | None = None
    blueprint_exists: bool = True


class ScheduleRunSummary(BaseModel):
    """One execution record in a workflow schedule's run history.

    Lives in the session domain (rather than ``mas.scheduling``) because each
    run is a session — projected from session documents by
    ``SessionService.get_runs_by_schedule()``.
    """

    session_id: str
    status: SessionStatus = SessionStatus.PENDING
    started_at: str | None = None  # ISO-8601
    metadata: SessionMeta = Field(default_factory=SessionMeta)
