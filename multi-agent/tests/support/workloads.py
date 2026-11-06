"""An owned-port double and shared workload behavior, independent of graph state."""

from mas.application.workloads.storage import WorkloadStorage
from mas.application.workloads.unified_service import UnifiedWorkloadService
from mas.domain.workloads.thread import Thread
from mas.domain.workloads.workspace import Workspace


class MemoryWorkloadStorage:
    def __init__(self) -> None:
        self.threads: dict[str, Thread] = {}
        self.workspaces: dict[str, Workspace] = {}

    def save_thread(self, thread: Thread) -> Thread:
        self.threads[thread.thread_id] = thread.model_copy(deep=True)
        self.workspaces.setdefault(thread.thread_id, Workspace.create(thread.thread_id))
        return thread

    def get_thread(self, thread_id: str) -> Thread | None:
        thread = self.threads.get(thread_id)
        return thread.model_copy(deep=True) if thread else None

    def delete_thread(self, thread_id: str) -> bool:
        thread = self.threads.pop(thread_id, None)
        if thread is None:
            return False
        self.workspaces.pop(thread_id, None)
        return True

    def list_threads(self) -> list[Thread]:
        return [thread.model_copy(deep=True) for thread in self.threads.values()]

    def get_workspace(self, thread_id: str) -> Workspace:
        return self.workspaces.setdefault(thread_id, Workspace.create(thread_id)).model_copy(
            deep=True
        )

    def update_workspace(self, workspace: Workspace) -> Workspace:
        self.workspaces[workspace.thread_id] = workspace.model_copy(deep=True)
        return workspace


def workload_contract(storage: WorkloadStorage) -> None:
    services = UnifiedWorkloadService(storage)
    threads, workspaces = services.get_thread_service(), services.get_workspace_service()
    root = threads.create_root_thread("Research", "Check evidence", "coordinator")
    child = threads.create_child_thread(root, "Review", "Inspect findings", "reviewer")
    assert threads.find_root_thread(child.thread_id) == root.thread_id
    assert threads.get_thread_depth(child.thread_id) == 1
    workspaces.add_fact(child.thread_id, "Checked source")
    workspaces.set_variable(child.thread_id, "accepted", True)
    rebound = UnifiedWorkloadService(storage)
    assert rebound.get_workspace_service().get_facts(child.thread_id) == ["Checked source"]
    assert rebound.get_workspace_service().get_variable(child.thread_id, "accepted") is True
    assert rebound.get_thread_service().get_thread(root.thread_id).child_thread_ids == [
        child.thread_id
    ]
    assert threads.delete_thread(child.thread_id)
    assert threads.get_thread(child.thread_id) is None
    assert threads.get_thread(root.thread_id).child_thread_ids == []
