"""Cohesive thread/workspace services depend only on the workload storage port."""

from abc import ABC, abstractmethod

from lumora.elements.workloads.storage import WorkloadStorage
from lumora.elements.workloads.thread_service import IThreadService, ThreadService
from lumora.elements.workloads.workspace_service import IWorkspaceService, WorkspaceService


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


class UnifiedWorkloadService(IWorkloadService):
    """Concrete implementation providing all workload services."""

    def __init__(self, storage: WorkloadStorage) -> None:
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
