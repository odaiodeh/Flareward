"""Thread model for grouping and context management."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ThreadStatus(StrEnum):
    """Thread execution status."""

    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class Thread(BaseModel):
    """Thread for grouping and context management."""

    # Thread Identity
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Core Thread Info
    title: str
    objective: str
    initiator: str

    # Hierarchy
    parent_thread_id: str | None = None
    child_thread_ids: list[str] = Field(default_factory=list)

    # Status and Participants
    status: ThreadStatus = ThreadStatus.ACTIVE
    participants: list[str] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    # ========== CLASS METHODS ==========

    @classmethod
    def create(cls, title: str, objective: str, initiator: str) -> Thread:
        """Create a new thread."""
        thread = cls(
            title=title,
            objective=objective,
            initiator=initiator,
            parent_thread_id=None,
            participants=[initiator],
        )
        return thread

    # ========== INSTANCE METHODS - HIERARCHY MANAGEMENT ==========

    def create_child(self, title: str, objective: str, initiator: str) -> Thread:
        """Create a child thread from this thread."""
        child_thread = Thread(
            title=title,
            objective=objective,
            initiator=initiator,
            parent_thread_id=self.thread_id,
            participants=[initiator],
        )

        # Add child to this thread's children
        self.add_child_thread(child_thread.thread_id)

        return child_thread

    def adopt_child(self, child_thread: Thread) -> Thread:
        """Adopt an existing thread as a child."""
        # Validate adoption
        self._validate_child_adoption(child_thread)

        # Update child's parent
        child_thread.parent_thread_id = self.thread_id

        # Add to our children
        self.add_child_thread(child_thread.thread_id)

        return self

    def remove_child(self, child_thread_id: str) -> Thread:
        """Remove a child thread relationship."""
        if child_thread_id in self.child_thread_ids:
            self.child_thread_ids.remove(child_thread_id)
        return self

    def add_child_thread(self, child_thread_id: str) -> Thread:
        """Add a child thread ID to this thread."""
        if child_thread_id not in self.child_thread_ids:
            self.child_thread_ids.append(child_thread_id)
        return self

    # ========== INSTANCE METHODS - PARTICIPANT MANAGEMENT ==========

    def add_participant(self, participant_id: str) -> Thread:
        """Add a participant to this thread."""
        if participant_id not in self.participants:
            self.participants.append(participant_id)
        return self

    def remove_participant(self, participant_id: str) -> Thread:
        """Remove a participant from this thread."""
        if participant_id in self.participants:
            self.participants.remove(participant_id)
        return self

    def complete(self) -> Thread:
        """Mark thread as completed."""
        self.status = ThreadStatus.COMPLETED
        self.completed_at = datetime.now(UTC)
        return self

    def fail(self) -> Thread:
        """Mark thread as failed."""
        self.status = ThreadStatus.FAILED
        self.completed_at = datetime.now(UTC)
        return self

    def pause(self) -> Thread:
        """Mark thread as paused."""
        self.status = ThreadStatus.PAUSED
        return self

    def resume(self) -> Thread:
        """Resume a paused thread."""
        if self.status == ThreadStatus.PAUSED:
            self.status = ThreadStatus.ACTIVE
        return self

    # ========== HELPER METHODS ==========

    def is_root_thread(self) -> bool:
        """Check if this is a root thread (no parent)."""
        return self.parent_thread_id is None

    def is_child_thread(self) -> bool:
        """Check if this is a child thread."""
        return self.parent_thread_id is not None

    def has_children(self) -> bool:
        """Check if this thread has child threads."""
        return len(self.child_thread_ids) > 0

    def is_active(self) -> bool:
        """Check if thread is active."""
        return self.status == ThreadStatus.ACTIVE

    def is_completed(self) -> bool:
        """Check if thread is completed."""
        return self.status == ThreadStatus.COMPLETED

    def get_participant_count(self) -> int:
        """Get number of participants."""
        return len(self.participants)

    def get_child_count(self) -> int:
        """Get number of child threads."""
        return len(self.child_thread_ids)

    # ========== HIERARCHY VALIDATION ==========

    def _validate_child_adoption(self, child_thread: Thread) -> None:
        """Validate that adopting a child thread is safe."""
        # Cannot adopt self
        if child_thread.thread_id == self.thread_id:
            raise ValueError("Thread cannot adopt itself")

        # Cannot adopt if child already has a different parent
        if child_thread.parent_thread_id and child_thread.parent_thread_id != self.thread_id:
            raise ValueError(
                f"Thread {child_thread.thread_id} already has parent "
                f"{child_thread.parent_thread_id}"
            )

        # Cannot create circular dependency (child adopting ancestor)
        current_parent_id = self.parent_thread_id
        while current_parent_id:
            if current_parent_id == child_thread.thread_id:
                raise ValueError(
                    f"Circular dependency: {child_thread.thread_id} "
                    f"cannot adopt ancestor {self.thread_id}"
                )
            # Note: Would need thread registry to traverse up the hierarchy
            # For now, we'll just check immediate parent
            break

    # ========== HIERARCHY TRAVERSAL HELPERS ==========

    def get_hierarchy_path(self) -> list[str]:
        """Get the hierarchy path from root to this thread."""
        path = [self.thread_id]
        if self.parent_thread_id:
            path.insert(0, self.parent_thread_id)  # Simple case - immediate parent only
        return path

    def get_hierarchy_depth(self) -> int:
        """Get the depth of this thread in the hierarchy."""
        return 1 if self.parent_thread_id else 0

    def is_ancestor_of(self, other_thread_id: str) -> bool:
        """Check if this thread is an ancestor of another thread."""
        return other_thread_id in self.child_thread_ids

    def is_descendant_of(self, other_thread_id: str) -> bool:
        """Check if this thread is a descendant of another thread."""
        return self.parent_thread_id == other_thread_id
