"""Task model for agentic communication."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from lumora.elements.workloads.domain.models import AgentResult


class Task(BaseModel):
    """Task for agentic communication."""

    # Task Identity
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Core Task Content
    content: str  # Natural language description of what to do
    data: dict[str, Any] = Field(default_factory=dict)  # Supporting data

    # Coordination
    should_respond: bool = False  # Does this task need a response?
    response_to: str | None = None  # Original requester UID

    # Task Relationships
    correlation_task_id: str | None = None  # Links response to original request
    parent_task_id: str | None = None  # Task that spawned this subtask
    thread_id: str | None = None  # Execution context grouping

    # Processing Metadata
    created_by: str | None = None  # Agent that created this task
    processed_by: str | None = None  # Agent that processed this task
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None

    # Results (only when responding)
    result: AgentResult | dict[str, Any] | None = None
    error: str | None = None  # Error message (string for simplicity and consistency)

    # ========== CLASS METHODS (Existing) ==========

    @classmethod
    def create(
        cls,
        content: str,
        data: dict = None,
        should_respond: bool = False,
        parent_task_id: str = None,
        thread_id: str = None,
        created_by: str = None,
    ) -> Task:
        """Create a new task."""
        return cls(
            content=content,
            data=data or {},
            should_respond=should_respond,
            parent_task_id=parent_task_id,
            thread_id=thread_id,
            created_by=created_by,
        )

    @classmethod
    def create_subtask(
        cls,
        parent_task: Task,
        content: str,
        data: dict = None,
        should_respond: bool = False,
        created_by: str = None,
    ) -> Task:
        """Create subtask of another task."""
        return cls(
            content=content,
            data=data or {},
            should_respond=should_respond,
            parent_task_id=parent_task.task_id,  # Link to parent
            thread_id=parent_task.thread_id,  # Same execution context
            created_by=created_by,
        )

    @classmethod
    def respond_success(
        cls, original_task: Task, result: dict[str, Any] | AgentResult, processed_by: str
    ) -> Task:
        """Create successful response task with processing metadata."""
        return cls(
            content=f"Response to: {original_task.content}",
            result=result,
            should_respond=False,
            correlation_task_id=original_task.task_id,  # Link to original
            thread_id=original_task.thread_id,
            created_by=processed_by,  # Agent responding is creating this response task
            processed_by=processed_by,
            processed_at=datetime.now(UTC),
        )

    @classmethod
    def respond_error(cls, original_task: Task, error: str, processed_by: str) -> Task:
        """Create error response task with processing metadata."""
        return cls(
            content=f"Error response to: {original_task.content}",
            error=error,
            should_respond=False,
            correlation_task_id=original_task.task_id,
            thread_id=original_task.thread_id,
            created_by=processed_by,  # Agent responding is creating this error response task
            processed_by=processed_by,
            processed_at=datetime.now(UTC),
        )

    # ========== INSTANCE METHODS (New Fork Functionality) ==========

    def fork(
        self,
        content: str,
        processed_by: str,
        data: dict = None,
        result: dict[str, Any] | AgentResult = None,
    ) -> Task:
        """Fork this task with new content after processing."""
        return Task(
            content=content,
            data=data or {},
            result=result,
            should_respond=False,
            parent_task_id=self.task_id,  # This task becomes the parent
            thread_id=self.thread_id,  # Same workflow thread
            created_by=processed_by,
            created_at=datetime.now(UTC),
        )

    def fork_subtask(
        self, content: str, created_by: str, should_respond: bool = False, data: dict = None
    ) -> Task:
        """Fork a subtask for delegation/orchestration."""
        return Task(
            content=content,
            data=data or {},
            should_respond=should_respond,
            parent_task_id=self.task_id,
            thread_id=self.thread_id,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )

    def mark_processed(self, processed_by: str) -> Task:
        """Mark this task as processed by an agent."""
        self.processed_by = processed_by
        self.processed_at = datetime.now(UTC)
        return self

    # ========== HELPER METHODS ==========

    def is_response(self) -> bool:
        """Check if this is a response task."""
        return self.correlation_task_id is not None

    def is_subtask(self) -> bool:
        """Check if this is a subtask."""
        return self.parent_task_id is not None

    def is_root_task(self) -> bool:
        """Check if this is a root task (no parent)."""
        return self.parent_task_id is None

    def is_forked_task(self) -> bool:
        """Check if this task was forked from another (part of processing chain)."""
        return self.parent_task_id is not None and not self.is_response()

    def is_successful_response(self) -> bool:
        """Check if this is a successful response."""
        return self.result is not None

    def is_error_response(self) -> bool:
        """Check if this is an error response."""
        return self.error is not None

    def get_fork_depth(self) -> int:
        """Get depth in fork chain (0 = original task)."""
        return 1 if self.is_forked_task() else 0

    def get_lineage_info(self) -> dict[str, Any]:
        """Get summary of task lineage information."""
        return {
            "task_id": self.task_id,
            "parent_task_id": self.parent_task_id,
            "thread_id": self.thread_id,
            "created_by": self.created_by,
            "processed_by": self.processed_by,
            "is_root": self.is_root_task(),
            "is_forked": self.is_forked_task(),
            "is_response": self.is_response(),
            "fork_depth": self.get_fork_depth(),
        }
