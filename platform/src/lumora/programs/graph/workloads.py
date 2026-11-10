"""Graph channels implement the workload storage port within one invocation."""

from lumora.elements.workloads.domain.thread import Thread
from lumora.elements.workloads.domain.workspace import Workspace
from lumora.programs.graph.state.graph_state import Channel
from lumora.programs.graph.state.state_view import StateView


class GraphWorkloadStorage:
    """GraphState-bound storage implementation."""

    def __init__(self, state: StateView) -> None:
        self._state = state

    def save_thread(self, thread: Thread) -> Thread:
        """Save thread to GraphState."""
        threads = self._state.get(Channel.THREADS, {})
        threads[thread.thread_id] = thread.model_dump()
        self._state[Channel.THREADS] = threads

        # Ensure workspace exists
        workspaces = self._state.get(Channel.WORKSPACES, {})
        if thread.thread_id not in workspaces:
            workspace = Workspace.create(thread.thread_id)
            workspaces[thread.thread_id] = workspace.model_dump()
            self._state[Channel.WORKSPACES] = workspaces

        return thread

    def get_thread(self, thread_id: str) -> Thread | None:
        """Get thread by ID from state."""
        threads = self._state.get(Channel.THREADS, {})
        thread_data = threads.get(thread_id)

        if thread_data:
            return Thread(**thread_data)
        return None

    def delete_thread(self, thread_id: str) -> bool:
        """Delete thread from GraphState."""
        threads = self._state.get(Channel.THREADS, {})

        if thread_id not in threads:
            return False

        # Delete thread
        del threads[thread_id]
        self._state[Channel.THREADS] = threads

        # Delete workspace
        workspaces = self._state.get(Channel.WORKSPACES, {})
        if thread_id in workspaces:
            del workspaces[thread_id]
            self._state[Channel.WORKSPACES] = workspaces

        return True

    def list_threads(self) -> list[Thread]:
        """List all threads from state."""
        threads = self._state.get(Channel.THREADS, {})
        return [Thread(**thread_data) for thread_data in threads.values()]

    def get_workspace(self, thread_id: str) -> Workspace:
        """Get workspace for thread from state."""
        workspaces = self._state.get(Channel.WORKSPACES, {})

        if thread_id not in workspaces:
            # Create new workspace
            workspace = Workspace.create(thread_id)
            workspaces[thread_id] = workspace.model_dump()
            self._state[Channel.WORKSPACES] = workspaces
            return workspace

        return Workspace(**workspaces[thread_id])

    def update_workspace(self, workspace: Workspace) -> Workspace:
        """Update workspace in state."""
        workspaces = self._state.get(Channel.WORKSPACES, {})
        workspaces[workspace.thread_id] = workspace.model_dump()
        self._state[Channel.WORKSPACES] = workspaces
        return workspace
