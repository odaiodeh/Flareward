"""WorkPlan data models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WorkItemStatus(StrEnum):
    """Status of a work item."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class WorkItemKind(StrEnum):
    """Kind of work item execution."""

    LOCAL = "local"  # Execute locally on this node
    REMOTE = "remote"  # Delegate to adjacent node


class ToolArguments(BaseModel):
    """Dynamic tool arguments for work items."""

    class Config:
        extra = "allow"  # Allow arbitrary additional fields

    def __init__(self, data: dict[str, Any] | None = None, **kwargs):
        """Initialize with either a dict or keyword arguments."""
        if data is not None:
            if kwargs:
                raise ValueError("Cannot provide both 'data' dict and keyword arguments")
            super().__init__(**data)
        else:
            super().__init__(**kwargs)

    def __len__(self) -> int:
        """Return the number of arguments."""
        return len(self.__dict__)

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access."""
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dict-like assignment."""
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return hasattr(self, key)


class LocalExecution(BaseModel):
    """Local work execution record (for LOCAL work items)."""

    outcome: str = Field(
        ...,
        description=(
            "Complete execution result: what was done, how it was done, and "
            "what was achieved. Natural narrative format."
        ),
    )
    executed_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="When execution completed",
    )


class DelegationExchange(BaseModel):
    """Complete request-response exchange in a delegation conversation."""

    # Ordering and identification
    sequence: int = Field(..., description="Turn number in conversation (0=first, 1=second, etc.)")
    task_id: str = Field(..., description="Unique task ID for this delegation")

    # Request side (what orchestrator asked)
    query: str = Field(..., description="What was specifically asked/delegated")
    delegated_to: str = Field(..., description="UID of agent this was delegated to")
    delegated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="When delegation was sent",
    )

    # Response side (what agent answered)
    response_content: str | None = Field(None, description="Agent's response text")
    response_data: dict[str, Any] | None = Field(
        None, description="Structured data (AgentResult, etc.)"
    )
    responded_by: str | None = Field(
        None, description="Who responded (usually same as delegated_to)"
    )
    responded_at: str | None = Field(None, description="When response was received")

    # State tracking
    processed: bool = Field(
        default=False,
        description="Whether LLM has acted on this response (re-delegated or marked status)",
    )

    @property
    def is_pending(self) -> bool:
        """Check if waiting for response."""
        return self.response_content is None

    @property
    def needs_attention(self) -> bool:
        """Check if has response but LLM hasn't acted on it yet."""
        return self.response_content is not None and not self.processed


class WorkItemResult(BaseModel):
    """Complete result container for both LOCAL and REMOTE work items."""

    # For REMOTE items: delegation conversation history
    delegations: list[DelegationExchange] = Field(
        default_factory=list,
        description="Delegation conversation history (REMOTE items only). Empty for LOCAL items.",
    )

    # For LOCAL items: execution record
    local_execution: LocalExecution | None = Field(
        None, description="Local execution details (LOCAL items only). None for REMOTE items."
    )

    # Common fields (both LOCAL and REMOTE)
    success: bool = Field(default=False, description="Final success status (set when marked DONE)")
    final_summary: str | None = Field(None, description="Final synthesized result or conclusion")
    data: dict[str, Any] | None = Field(None, description="Structured result data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    artifacts: list[str] = Field(default_factory=list, description="List of created artifacts")

    @property
    def pending_exchange(self) -> DelegationExchange | None:
        """Get the currently pending delegation exchange (waiting for response), if any."""
        for ex in reversed(self.delegations):  # Check most recent first
            if ex.is_pending:
                return ex
        return None

    @property
    def latest_exchange(self) -> DelegationExchange | None:
        """Get the most recent delegation exchange."""
        return self.delegations[-1] if self.delegations else None

    @property
    def has_unprocessed_responses(self) -> bool:
        """Check if any delegation responses need LLM interpretation."""
        return any(ex.needs_attention for ex in self.delegations)

    def conversation_summary(self, truncate: bool = False, max_chars: int = 250) -> str:
        """Format delegation history with state indicators for LLM interpretation."""
        if not self.delegations:
            return ""

        # Helper to truncate content
        def _truncate_if_needed(content: str) -> str:
            if truncate and len(content) > max_chars:
                return content[:max_chars] + "..."
            return content

        # Single exchange: simple format
        if len(self.delegations) == 1:
            ex = self.delegations[0]
            if ex.is_pending:
                return f"⏳ WAITING for response from {ex.delegated_to}"
            elif ex.needs_attention:
                content = _truncate_if_needed(ex.response_content)
                return (
                    f"🔔 NEW RESPONSE from {ex.responded_by} "
                    f"(needs your interpretation):\n  {content}"
                )
            else:
                content = _truncate_if_needed(ex.response_content)
                return f"✓ Response from {ex.responded_by} (processed):\n  {content}"

        # Multi-turn conversation: detailed format
        lines = [f"Conversation History ({len(self.delegations)} turns):"]
        for ex in self.delegations:
            if ex.is_pending:
                lines.append(f"  [{ex.sequence}] ⏳ WAITING: Query sent to {ex.delegated_to}")
                lines.append(f"      Query: {ex.query}")
            elif ex.needs_attention:
                lines.append(
                    f"  [{ex.sequence}] 🔔 NEW: Response from {ex.responded_by} "
                    "(needs interpretation)"
                )
                lines.append(f"      Query: {ex.query}")
                content = _truncate_if_needed(ex.response_content)
                lines.append(f"      Response: {content}")
            else:
                lines.append(f"  [{ex.sequence}] ✓ PROCESSED: {ex.responded_by}")
                content = _truncate_if_needed(ex.response_content)
                lines.append(f"      Response: {content}")

        return "\n".join(lines)


class WorkItem(BaseModel):
    """A single work item in a work plan."""

    # Core identification
    id: str = Field(..., description="Unique identifier for this work item")
    title: str = Field(..., description="Short, descriptive title")
    description: str = Field(..., description="Detailed description of the work")

    # Dependencies and execution
    dependencies: list[str] = Field(
        default_factory=list, description="Work item IDs that must complete first"
    )
    status: WorkItemStatus = Field(default=WorkItemStatus.PENDING, description="Current status")
    kind: WorkItemKind = Field(default=WorkItemKind.LOCAL, description="Local or remote execution")

    # Assignment and execution details
    assigned_uid: str | None = Field(None, description="UID of assigned node")
    tool: str | None = Field(None, description="Tool to use for execution")
    args: ToolArguments = Field(default_factory=ToolArguments, description="Tool arguments")

    # Results and tracking
    result: WorkItemResult | None = Field(None, description="Execution result")
    error: str | None = Field(None, description="Error message if failed")
    child_thread_id: str | None = Field(
        None, description="Child thread ID for re-delegation context continuity"
    )
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(
        default=3, description="Maximum retry attempts before marking as failed"
    )

    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    def is_ready_for_execution(self, completed_item_ids: set[str]) -> bool:
        """Check if this item is ready for execution based on dependencies."""
        if self.status != WorkItemStatus.PENDING:
            return False

        # All dependencies must be completed
        for dep_id in self.dependencies:
            if dep_id not in completed_item_ids:
                return False

        return True

    def is_blocked(self, completed_item_ids: set[str]) -> bool:
        """Check if this item is blocked by incomplete dependencies."""
        if self.status != WorkItemStatus.PENDING:
            return False

        # Check if any dependencies are not completed
        for dep_id in self.dependencies:
            if dep_id not in completed_item_ids:
                return True

        return False

    def can_retry(self) -> bool:
        """Check if this item can be retried."""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> bool:
        """Increment retry count and mark as updated."""
        if not self.can_retry():
            return False
        self.retry_count += 1
        self.mark_updated()
        return True

    def has_unprocessed_responses(self) -> bool:
        """Check if this work item has unprocessed responses needing LLM action."""
        return (
            self.status == WorkItemStatus.IN_PROGRESS
            and self.kind == WorkItemKind.REMOTE
            and self.result is not None
            and self.result.has_unprocessed_responses
        )

    def mark_updated(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC).isoformat()


class WorkItemStatusCounts(BaseModel):
    """Count of work items by status."""

    pending: int = 0
    in_progress: int = 0
    done: int = 0
    failed: int = 0
    blocked: int = 0

    @property
    def total(self) -> int:
        """Total count of all items."""
        return self.pending + self.in_progress + self.done + self.failed + self.blocked


class WorkPlanStatus(BaseModel):
    """Complete status snapshot of a work plan."""

    exists: bool = False
    total_items: int = 0
    pending_items: int = 0
    in_progress_items: int = 0
    waiting_items: int = 0  # Calculated: IN_PROGRESS + kind=REMOTE
    done_items: int = 0
    failed_items: int = 0
    blocked_items: int = 0
    has_local_ready: bool = False
    has_remote_ready: bool = False  # True if any PENDING + kind=REMOTE items with dependencies met
    has_remote_waiting: bool = False  # True if any IN_PROGRESS + kind=REMOTE items exist
    has_responses: bool = (
        False  # True if any IN_PROGRESS + kind=REMOTE items have result with delegations
    )
    is_complete: bool = False


class WorkPlan(BaseModel):
    """A work plan containing multiple work items."""

    # Core identification
    summary: str = Field(..., description="High-level summary of the work plan")
    owner_uid: str = Field(..., description="UID of the node that owns this plan")
    thread_id: str = Field(..., description="Thread ID this plan belongs to")

    # Work items
    items: dict[str, WorkItem] = Field(default_factory=dict, description="Work items by ID")

    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def total_items(self) -> int:
        """Get the total number of work items in this plan."""
        return len(self.items)

    def get_completed_item_ids(self) -> set[str]:
        """Get IDs of successfully completed items (DONE only)."""
        completed = set()
        for item_id, item in self.items.items():
            if item.status == WorkItemStatus.DONE:
                completed.add(item_id)
        return completed

    def get_failed_item_ids(self) -> set[str]:
        """Get IDs of failed items."""
        failed = set()
        for item_id, item in self.items.items():
            if item.status == WorkItemStatus.FAILED:
                failed.add(item_id)
        return failed

    def get_ready_items(self) -> list[WorkItem]:
        """Get items that are ready for execution (dependencies satisfied)."""
        completed_ids = self.get_completed_item_ids()
        ready_items = []

        for item in self.items.values():
            if item.is_ready_for_execution(completed_ids):
                ready_items.append(item)

        return ready_items

    def get_blocked_items(self) -> list[WorkItem]:
        """Get items that are blocked by incomplete dependencies."""
        completed_ids = self.get_completed_item_ids()
        blocked_items = []

        for item in self.items.values():
            if item.is_blocked(completed_ids):
                blocked_items.append(item)

        return blocked_items

    def get_items_blocked_by_failure(self) -> list[WorkItem]:
        """Get items that are blocked specifically by failed dependencies."""
        completed_ids = self.get_completed_item_ids()
        failed_ids = self.get_failed_item_ids()
        blocked_by_failure = []

        for item in self.items.values():
            if item.status == WorkItemStatus.PENDING:
                # Check if any dependencies are failed
                has_failed_dep = any(dep_id in failed_ids for dep_id in item.dependencies)
                # And item is blocked (not all deps are DONE)
                is_blocked = item.is_blocked(completed_ids)

                if has_failed_dep and is_blocked:
                    blocked_by_failure.append(item)

        return blocked_by_failure

    def get_items_by_status(self, status: WorkItemStatus) -> list[WorkItem]:
        """Get all items with the specified status."""
        return [item for item in self.items.values() if item.status == status]

    def get_status_counts(self) -> WorkItemStatusCounts:
        """Get count of items by status."""
        counts = WorkItemStatusCounts()
        completed_ids = self.get_completed_item_ids()

        for item in self.items.values():
            if item.status == WorkItemStatus.PENDING:
                if item.is_blocked(completed_ids):
                    counts.blocked += 1
                else:
                    counts.pending += 1
            elif item.status == WorkItemStatus.IN_PROGRESS:
                counts.in_progress += 1
            elif item.status == WorkItemStatus.DONE:
                counts.done += 1
            elif item.status == WorkItemStatus.FAILED:
                counts.failed += 1

        return counts

    def is_complete(self) -> bool:
        """Check if all work items are complete (DONE or FAILED)."""
        if not self.items:
            return False

        for item in self.items.values():
            if item.status not in [WorkItemStatus.DONE, WorkItemStatus.FAILED]:
                return False

        return True

    def mark_updated(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC).isoformat()
