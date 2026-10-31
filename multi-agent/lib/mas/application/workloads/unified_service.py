"""Unified Workload Service - Composition root for all workload services."""

from abc import ABC, abstractmethod

from mas.application.workloads.storage import InMemoryStorage, IWorkloadStorage, StateBoundStorage
from mas.application.workloads.thread_service import IThreadService, ThreadService
from mas.application.workloads.workspace_service import IWorkspaceService, WorkspaceService
from mas.domain.workloads.thread import Thread
from mas.domain.workloads.workspace import Workspace
from mas.graph.state.state_view import StateView


class IWorkloadService(ABC):
    """Unified interface providing access to all workload services."""

    @abstractmethod
    def get_thread_service(self) -> IThreadService:
        """Get thread service for hierarchy and lifecycle operations."""
        pass

    @abstractmethod
    def get_workspace_service(self) -> IWorkspaceService:
        """Get workspace service for content management (includes work plans)."""
        pass

    # ========== LEGACY COMPATIBILITY METHODS ==========
    # These delegate to the appropriate services for backward compatibility

    def create_thread(self, title: str, objective: str, initiator: str) -> Thread:
        """Create thread (delegates to thread service)."""
        return self.get_thread_service().create_root_thread(title, objective, initiator)

    def get_thread(self, thread_id: str) -> Thread | None:
        """Get thread (delegates to thread service)."""
        return self.get_thread_service().get_thread(thread_id)

    def get_workspace(self, thread_id: str) -> Workspace:
        """Get workspace (delegates to workspace service)."""
        return self.get_workspace_service().get_workspace(thread_id)

    def add_fact(self, thread_id: str, fact: str) -> None:
        """Add fact (delegates to workspace service)."""
        self.get_workspace_service().add_fact(thread_id, fact)

    def set_variable(self, thread_id: str, key: str, value) -> None:
        """Set variable (delegates to workspace service)."""
        self.get_workspace_service().set_variable(thread_id, key, value)

    def get_variable(self, thread_id: str, key: str, default=None):
        """Get variable (delegates to workspace service)."""
        return self.get_workspace_service().get_variable(thread_id, key, default)


class UnifiedWorkloadService(IWorkloadService):
    """Concrete implementation providing all workload services."""

    def __init__(self, storage: IWorkloadStorage):
        """Initialize with storage implementation."""
        # Initialize service layer
        self._thread_service = ThreadService(storage)
        self._workspace_service = WorkspaceService(storage)

    def get_thread_service(self) -> IThreadService:
        """Get thread service."""
        return self._thread_service

    def get_workspace_service(self) -> IWorkspaceService:
        """Get workspace service (includes work plan operations)."""
        return self._workspace_service

    @classmethod
    def create_in_memory(cls) -> UnifiedWorkloadService:
        """Create instance with in-memory storage."""
        storage = InMemoryStorage()
        return cls(storage)

    @classmethod
    def create_state_bound(cls, state: StateView) -> UnifiedWorkloadService:
        """Create instance with GraphState-bound storage."""
        storage = StateBoundStorage(state)
        return cls(storage)
