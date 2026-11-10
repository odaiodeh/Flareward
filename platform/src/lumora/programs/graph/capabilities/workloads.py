"""GraphWorkloadMixin for clean workload service access."""

from typing import ClassVar

from lumora.elements.workloads.domain.thread import Thread
from lumora.elements.workloads.streaming_hook import WorkPlanStreamingHook
from lumora.elements.workloads.thread_service import IThreadService
from lumora.elements.workloads.unified_service import IWorkloadService, UnifiedWorkloadService
from lumora.elements.workloads.workspace_service import IWorkspaceService
from lumora.programs.graph.state.graph_state import Channel
from lumora.programs.graph.workloads import GraphWorkloadStorage


class GraphWorkloadMixin:
    """Simplified mixin providing clean service access."""

    # Channel permissions for workload management
    MIXIN_READS: ClassVar[set[str]] = {Channel.THREADS, Channel.WORKSPACES, Channel.TASK_THREADS}
    MIXIN_WRITES: ClassVar[set[str]] = {Channel.THREADS, Channel.WORKSPACES, Channel.TASK_THREADS}

    def __init__(self, **kwargs):
        """Initialize mixin and call super() for proper MRO."""
        super().__init__(**kwargs)

    def get_workload_service(self) -> IWorkloadService:
        """Get unified workload service bound to current state."""
        state = self.get_state()
        workload_service = UnifiedWorkloadService(GraphWorkloadStorage(state))
        # Setup streaming hooks if node supports streaming
        if self._should_stream_workplan():
            workload_service = self._setup_workplan_streaming_hook(workload_service)

        return workload_service

    # ========== SERVICE ACCESS PROPERTIES ==========

    @property
    def threads(self) -> IThreadService:
        """Access thread service."""
        return self.get_workload_service().get_thread_service()

    @property
    def workspaces(self) -> IWorkspaceService:
        """Access workspace service (includes work plan operations)."""
        return self.get_workload_service().get_workspace_service()

    # ========== COMMON OPERATIONS (Optional convenience) ==========

    def create_child_thread(self, parent: Thread, title: str, objective: str) -> Thread:
        """Convenience: Create child thread."""
        return self.threads.create_child_thread(parent, title, objective, self.uid)

    def add_fact_to_workspace(self, thread_id: str, fact: str) -> None:
        """Convenience: Add fact to workspace."""
        self.workspaces.add_fact(thread_id, fact)

    def set_workspace_variable(self, thread_id: str, key: str, value) -> None:
        """Convenience: Set workspace variable."""
        self.workspaces.set_variable(thread_id, key, value)

    def get_workspace_variable(self, thread_id: str, key: str, default=None):
        """Convenience: Get workspace variable."""
        return self.workspaces.get_variable(thread_id, key, default)

    # ========== GRAPHSTATE INTEGRATION HELPER ==========

    def copy_messages_to_workspace(
        self, thread_id: str, limit: int = 10, strategy: str = "conversation"
    ) -> int:
        """Copy recent GraphState messages to workspace."""
        try:
            # Get GraphState messages using proper access pattern
            state = self.get_state()

            graphstate_messages = state.get(Channel.MESSAGES, [])

            # Delegate to workspace service (SOLID delegation)
            synced_count = self.workspaces.sync_messages(
                thread_id, graphstate_messages, limit, strategy
            )

            return synced_count

        except Exception:
            return 0

    # ========== WORKPLAN STREAMING SETUP ==========

    def _should_stream_workplan(self) -> bool:
        """Check if workplan streaming should be enabled."""
        return hasattr(self, "is_streaming") and hasattr(self, "_stream") and self.is_streaming()

    def _setup_workplan_streaming_hook(self, workload_service) -> IWorkloadService:
        """Register streaming hook for workplan operations."""

        def stream_callback(data: dict) -> None:
            if self.is_streaming():
                self._stream(data)

        streaming_hook = WorkPlanStreamingHook(stream_callback)
        workspace_service = workload_service.get_workspace_service()
        workspace_service.add_workplan_hook(streaming_hook)
        return workload_service
