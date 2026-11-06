"""Thread Service for centralized thread management."""

import logging
from abc import ABC, abstractmethod

from mas.application.workloads.storage import WorkloadStorage
from mas.domain.workloads.thread import Thread, ThreadStatus

logger = logging.getLogger(__name__)


class IThreadService(ABC):
    """Centralized service for ALL thread-related operations."""

    # ========== THREAD LIFECYCLE ==========

    @abstractmethod
    def create_root_thread(self, title: str, objective: str, initiator: str) -> Thread:
        """Create a new root thread."""
        pass

    @abstractmethod
    def create_child_thread(
        self, parent: Thread, title: str, objective: str, initiator: str
    ) -> Thread:
        """Create child thread and update parent atomically."""
        pass

    @abstractmethod
    def save_thread(self, thread: Thread) -> Thread:
        """Save thread to storage."""
        pass

    @abstractmethod
    def get_thread(self, thread_id: str) -> Thread | None:
        """Get thread by ID."""
        pass

    @abstractmethod
    def update_thread(self, thread: Thread) -> Thread:
        """Update thread in storage."""
        pass

    @abstractmethod
    def delete_thread(self, thread_id: str) -> bool:
        """Delete thread and cleanup hierarchy."""
        pass

    # ========== HIERARCHY OPERATIONS ==========

    @abstractmethod
    def find_root_thread(self, thread_id: str) -> str | None:
        """Find root thread ID by traversing up hierarchy."""
        pass

    @abstractmethod
    def get_hierarchy_path(self, thread_id: str) -> list[str]:
        """Get complete hierarchy path from root to thread."""
        pass

    @abstractmethod
    def get_all_descendants(self, thread_id: str) -> list[Thread]:
        """Get all descendant threads (children, grandchildren, etc.)."""
        pass

    @abstractmethod
    def detect_delegation_cycle(self, from_thread_id: str, to_initiator: str) -> bool:
        """Check if delegation would create a cycle."""
        pass

    @abstractmethod
    def get_thread_depth(self, thread_id: str) -> int:
        """Get depth of thread in hierarchy."""
        pass

    # ========== WORK PLAN RESOLUTION ==========

    @abstractmethod
    def find_work_plan_owner(self, thread_id: str, owner_uid: str) -> str | None:
        """Find thread that owns work plan for the given owner_uid."""
        pass

    # ========== QUERIES ==========

    @abstractmethod
    def list_threads_by_initiator(self, initiator: str) -> list[Thread]:
        """Get all threads by initiator."""
        pass

    @abstractmethod
    def list_root_threads(self) -> list[Thread]:
        """Get all root threads (threads with no parent)."""
        pass

    @abstractmethod
    def list_active_threads(self) -> list[Thread]:
        """Get all active threads."""
        pass

    @abstractmethod
    def get_child_threads(self, parent_thread_id: str) -> list[Thread]:
        """Get direct child threads of a parent."""
        pass


class ThreadService(IThreadService):
    """Concrete implementation of thread service."""

    def __init__(self, storage: WorkloadStorage):
        """Initialize with storage implementation."""
        self._storage = storage
        self._max_depth = 50  # Cycle protection

    def create_root_thread(self, title: str, objective: str, initiator: str) -> Thread:
        """Create and save root thread."""
        thread = Thread.create(title, objective, initiator)
        return self._storage.save_thread(thread)

    def create_child_thread(
        self, parent: Thread, title: str, objective: str, initiator: str
    ) -> Thread:
        """Create child and update parent atomically."""
        child = parent.create_child(title, objective, initiator)

        # Save both parent and child
        self._storage.save_thread(parent)
        self._storage.save_thread(child)

        return child

    def save_thread(self, thread: Thread) -> Thread:
        """Save thread to storage."""
        return self._storage.save_thread(thread)

    def get_thread(self, thread_id: str) -> Thread | None:
        """Get thread by ID."""
        return self._storage.get_thread(thread_id)

    def update_thread(self, thread: Thread) -> Thread:
        """Update thread in storage."""
        return self._storage.save_thread(thread)

    def delete_thread(self, thread_id: str) -> bool:
        """Delete thread and cleanup hierarchy."""
        thread = self._storage.get_thread(thread_id)
        if not thread:
            return False

        # Remove from parent's children if applicable
        if thread.parent_thread_id:
            parent = self._storage.get_thread(thread.parent_thread_id)
            if parent and thread_id in parent.child_thread_ids:
                parent.child_thread_ids.remove(thread_id)
                self._storage.save_thread(parent)

        return self._storage.delete_thread(thread_id)

    def find_root_thread(self, thread_id: str) -> str | None:
        """Full hierarchy traversal to find root."""
        current_id = thread_id
        depth = 0

        while depth < self._max_depth:
            thread = self._storage.get_thread(current_id)
            if not thread:
                return current_id  # Best we can do

            if not thread.parent_thread_id:
                return current_id  # Found root

            current_id = thread.parent_thread_id
            depth += 1

        # Max depth protection triggered
        logger.warning(
            "workload.max_depth",
            extra={
                "thread_id": thread_id,
                "max_depth": self._max_depth,
                "operation": "find_root_thread",
            },
        )
        return current_id

    def get_hierarchy_path(self, thread_id: str) -> list[str]:
        """Get complete hierarchy path."""
        path = []
        current_id = thread_id
        depth = 0

        while current_id and depth < self._max_depth:
            path.append(current_id)
            thread = self._storage.get_thread(current_id)
            if not thread or not thread.parent_thread_id:
                break
            current_id = thread.parent_thread_id
            depth += 1

        return list(reversed(path))  # Root to leaf

    def get_all_descendants(self, thread_id: str) -> list[Thread]:
        """Get all descendant threads recursively."""
        descendants = []

        def collect_descendants(parent_id: str, depth: int = 0):
            if depth > self._max_depth:
                return

            children = self.get_child_threads(parent_id)
            for child in children:
                descendants.append(child)
                collect_descendants(child.thread_id, depth + 1)

        collect_descendants(thread_id)
        return descendants

    def detect_delegation_cycle(self, from_thread_id: str, to_initiator: str) -> bool:
        """Check if delegation creates cycle."""
        initiators = self._get_hierarchy_initiators(from_thread_id)
        return to_initiator in initiators

    def get_thread_depth(self, thread_id: str) -> int:
        """Get hierarchy depth."""
        path = self.get_hierarchy_path(thread_id)
        return len(path) - 1  # 0-based depth

    def find_work_plan_owner(self, thread_id: str, owner_uid: str) -> str | None:
        """Find thread that owns work plan for the given owner_uid."""
        current_id = thread_id
        depth = 0

        logger.info(
            "workload.thread_lookup",
            extra={"owner_uid": owner_uid, "thread_id": thread_id, "phase": "start"},
        )

        while depth < self._max_depth:
            # Check if owner_uid has a work plan in current thread
            try:
                workspace = self._storage.get_workspace(current_id)
                if workspace and owner_uid in workspace.context.work_plans:
                    logger.info(
                        "workload.thread_lookup",
                        extra={
                            "owner_uid": owner_uid,
                            "thread_id": current_id,
                            "depth": depth,
                            "found": True,
                        },
                    )
                    return current_id  # Found it!
                else:
                    logger.info(
                        "workload.thread_lookup",
                        extra={
                            "owner_uid": owner_uid,
                            "thread_id": current_id,
                            "depth": depth,
                            "found": False,
                        },
                    )
            except Exception as e:
                # Workspace doesn't exist for this thread, continue searching
                logger.info(
                    "workload.thread_lookup",
                    extra={
                        "owner_uid": owner_uid,
                        "thread_id": current_id,
                        "depth": depth,
                        "error": str(e),
                    },
                )
                pass

            # Move up to parent thread
            thread = self._storage.get_thread(current_id)
            if not thread or not thread.parent_thread_id:
                logger.info(
                    "workload.thread_lookup",
                    extra={
                        "owner_uid": owner_uid,
                        "thread_id": current_id,
                        "found": False,
                        "reason": "reached_root",
                    },
                )
                return None  # Reached root, not found

            logger.info(
                "workload.thread_lookup",
                extra={
                    "owner_uid": owner_uid,
                    "thread_id": current_id,
                    "parent_thread_id": thread.parent_thread_id,
                    "depth": depth,
                    "phase": "move_to_parent",
                },
            )
            current_id = thread.parent_thread_id
            depth += 1

        logger.warning(
            "workload.max_depth",
            extra={
                "owner_uid": owner_uid,
                "thread_id": thread_id,
                "max_depth": self._max_depth,
                "operation": "find_work_plan_owner",
            },
        )
        return None  # Max depth reached

    def list_threads_by_initiator(self, initiator: str) -> list[Thread]:
        """Get all threads by initiator."""
        all_threads = self._storage.list_threads()
        return [thread for thread in all_threads if thread.initiator == initiator]

    def list_root_threads(self) -> list[Thread]:
        """Get all root threads."""
        all_threads = self._storage.list_threads()
        return [thread for thread in all_threads if not thread.parent_thread_id]

    def list_active_threads(self) -> list[Thread]:
        """Get all active threads."""
        all_threads = self._storage.list_threads()
        return [thread for thread in all_threads if thread.status == ThreadStatus.ACTIVE]

    def get_child_threads(self, parent_thread_id: str) -> list[Thread]:
        """Get direct child threads."""
        parent = self._storage.get_thread(parent_thread_id)
        if not parent:
            return []

        children = []
        for child_id in parent.child_thread_ids:
            child = self._storage.get_thread(child_id)
            if child:
                children.append(child)

        return children

    # ========== PRIVATE HELPERS ==========

    def _get_hierarchy_initiators(self, thread_id: str) -> set[str]:
        """Get all initiators in delegation chain."""
        initiators = set()
        current_id = thread_id
        depth = 0

        while current_id and depth < self._max_depth:
            thread = self._storage.get_thread(current_id)
            if not thread:
                break
            initiators.add(thread.initiator)
            current_id = thread.parent_thread_id
            depth += 1

        return initiators
