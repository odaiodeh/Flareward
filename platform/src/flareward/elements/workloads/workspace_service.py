"""Workspace Service for centralized workspace content management."""

import logging
import threading
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from flareward.elements.messaging.domain.messages import ChatMessage
from flareward.elements.workloads.domain.models import (
    AgentResult,
    WorkItemKind,
    WorkItemStatus,
    WorkPlan,
    WorkPlanStatus,
)
from flareward.elements.workloads.domain.task import Task
from flareward.elements.workloads.domain.workspace import Workspace
from flareward.elements.workloads.hooks import WorkPlanHook, WorkPlanHookPoint
from flareward.elements.workloads.storage import WorkloadStorage

logger = logging.getLogger(__name__)


class IWorkspaceService(ABC):
    """Service focused solely on workspace content management."""

    # ========== WORKSPACE ACCESS ==========

    @abstractmethod
    def get_workspace(self, thread_id: str) -> Workspace:
        """Get workspace for thread."""
        pass

    @abstractmethod
    def update_workspace(self, workspace: Workspace) -> Workspace:
        """Update workspace in storage."""
        pass

    # ========== FACTS MANAGEMENT ==========

    @abstractmethod
    def add_fact(self, thread_id: str, fact: str) -> None:
        """Add fact to workspace."""
        pass

    @abstractmethod
    def remove_fact(self, thread_id: str, fact: str) -> None:
        """Remove fact from workspace."""
        pass

    @abstractmethod
    def get_facts(self, thread_id: str) -> list[str]:
        """Get all facts from workspace."""
        pass

    @abstractmethod
    def clear_facts(self, thread_id: str) -> None:
        """Clear all facts from workspace."""
        pass

    # ========== RESULTS MANAGEMENT ==========

    @abstractmethod
    def add_result(self, thread_id: str, result: AgentResult) -> None:
        """Add result to workspace."""
        pass

    @abstractmethod
    def get_results(self, thread_id: str) -> list[AgentResult]:
        """Get all results from workspace."""
        pass

    @abstractmethod
    def get_results_by_agent(self, thread_id: str, agent_id: str) -> list[AgentResult]:
        """Get results by specific agent."""
        pass

    @abstractmethod
    def clear_results(self, thread_id: str) -> None:
        """Clear all results from workspace."""
        pass

    # ========== VARIABLES MANAGEMENT ==========

    @abstractmethod
    def set_variable(self, thread_id: str, key: str, value: Any) -> None:
        """Set variable in workspace."""
        pass

    @abstractmethod
    def get_variable(self, thread_id: str, key: str, default: Any = None) -> Any:
        """Get variable from workspace."""
        pass

    @abstractmethod
    def remove_variable(self, thread_id: str, key: str) -> None:
        """Remove variable from workspace."""
        pass

    @abstractmethod
    def get_all_variables(self, thread_id: str) -> dict[str, Any]:
        """Get all variables from workspace."""
        pass

    # ========== ARTIFACTS MANAGEMENT ==========

    @abstractmethod
    def add_artifact(
        self,
        thread_id: str,
        name: str,
        artifact_type: str,
        location: str,
        created_by: str,
        metadata: dict[str, Any] = None,
    ) -> None:
        """Add artifact to workspace."""
        pass

    @abstractmethod
    def remove_artifact(self, thread_id: str, name: str) -> None:
        """Remove artifact from workspace."""
        pass

    @abstractmethod
    def get_artifacts(self, thread_id: str) -> dict[str, Any]:
        """Get all artifacts from workspace."""
        pass

    @abstractmethod
    def get_artifacts_by_type(self, thread_id: str, artifact_type: str) -> list[Any]:
        """Get artifacts by type."""
        pass

    # ========== CONVERSATION MANAGEMENT ==========

    @abstractmethod
    def add_message(self, thread_id: str, message: ChatMessage) -> None:
        """Add message to conversation history."""
        pass

    @abstractmethod
    def add_messages(self, thread_id: str, messages: list[ChatMessage]) -> None:
        """Add multiple messages to conversation history."""
        pass

    @abstractmethod
    def get_conversation_history(self, thread_id: str) -> list[ChatMessage]:
        """Get conversation history."""
        pass

    @abstractmethod
    def get_recent_messages(self, thread_id: str, count: int = 10) -> list[ChatMessage]:
        """Get recent messages from conversation."""
        pass

    @abstractmethod
    def clear_conversation(self, thread_id: str) -> None:
        """Clear conversation history."""
        pass

    # ========== TASKS MANAGEMENT ==========

    @abstractmethod
    def add_task(self, thread_id: str, task: Task) -> None:
        """Add processed task to workspace."""
        pass

    @abstractmethod
    def get_tasks(self, thread_id: str) -> list[Task]:
        """Get all tasks from workspace."""
        pass

    @abstractmethod
    def get_original_task(self, thread_id: str) -> Task | None:
        """Get original task that requires response."""
        pass

    # ========== SUMMARY & CONTEXT ==========

    @abstractmethod
    def get_workspace_summary(self, thread_id: str) -> dict[str, Any]:
        """Get workspace content summary."""
        pass

    @abstractmethod
    def get_context_summary(self, thread_id: str) -> dict[str, Any]:
        """Get complete context summary."""
        pass

    @abstractmethod
    def clear_all_content(self, thread_id: str) -> None:
        """Clear all content from workspace."""
        pass

    # ========== WORK PLAN MANAGEMENT ==========

    @abstractmethod
    def create_work_plan(
        self, thread_id: str, owner_uid: str, summary: str = "New Work Plan"
    ) -> WorkPlan:
        """Create a new work plan."""
        pass

    @abstractmethod
    def load_work_plan(self, thread_id: str, owner_uid: str) -> WorkPlan | None:
        """Load work plan from workspace."""
        pass

    @abstractmethod
    def save_work_plan(self, plan: WorkPlan) -> bool:
        """Save work plan to workspace (thread-safe)."""
        pass

    @abstractmethod
    def get_work_plan_status(self, thread_id: str, owner_uid: str) -> WorkPlanStatus:
        """Get work plan status."""
        pass

    @abstractmethod
    def update_work_item_status(
        self,
        thread_id: str,
        owner_uid: str,
        item_id: str,
        status: WorkItemStatus,
        error: str = None,
        correlation_task_id: str = None,
    ) -> bool:
        """Update work item status (thread-safe)."""
        pass

    @abstractmethod
    def store_task_response_for_work_item(
        self,
        thread_id: str,
        owner_uid: str,
        correlation_task_id: str,
        response_content: str,
        from_uid: str,
        result_data: Any = None,
    ) -> bool:
        """Store task response as context without changing status - let LLM interpret."""
        pass

    @abstractmethod
    def atomic_update_work_item(
        self, thread_id: str, owner_uid: str, item_id: str, update_func: callable
    ) -> bool:
        """Atomically update a work item using the provided function."""
        pass

    @abstractmethod
    def get_all_work_plans(self, thread_id: str) -> dict[str, dict[str, Any]]:
        """Get all work plans in workspace."""
        pass

    @abstractmethod
    def remove_work_plan(self, thread_id: str, owner_uid: str) -> None:
        """Remove work plan from workspace."""
        pass

    @abstractmethod
    def work_plan_exists(self, thread_id: str, owner_uid: str) -> bool:
        """Check if work plan exists."""
        pass

    # ========== MESSAGE CONTEXT ==========

    @abstractmethod
    def sync_messages(
        self,
        thread_id: str,
        messages: list[ChatMessage],
        limit: int = 10,
        strategy: str = "conversation",  # "facts" | "conversation" | "both"
    ) -> int:
        """Sync recent messages to workspace."""
        pass


class WorkspaceService(IWorkspaceService):
    """Concrete implementation of workspace service."""

    def __init__(self, storage: WorkloadStorage):
        """Initialize with storage implementation."""
        self._storage = storage
        self._workplan_hooks: list[WorkPlanHook] = []

    def get_workspace(self, thread_id: str) -> Workspace:
        """Get workspace for thread."""
        return self._storage.get_workspace(thread_id)

    def update_workspace(self, workspace: Workspace) -> Workspace:
        """Update workspace in storage."""
        return self._storage.update_workspace(workspace)

    # ========== WORKPLAN HOOKS MANAGEMENT ==========

    def add_workplan_hook(self, hook: WorkPlanHook) -> None:
        """Register a lifecycle hook for workplan operations."""
        self._workplan_hooks.append(hook)

    def remove_workplan_hook(self, hook: WorkPlanHook) -> None:
        """Unregister a workplan hook."""
        if hook in self._workplan_hooks:
            self._workplan_hooks.remove(hook)

    def clear_workplan_hooks(self) -> None:
        """Remove all workplan hooks."""
        self._workplan_hooks.clear()

    def get_workplan_hooks(self) -> list[WorkPlanHook]:
        """Get list of registered workplan hooks."""
        return list(self._workplan_hooks)

    def _execute_workplan_hooks(self, hook_point: WorkPlanHookPoint, *args, **kwargs) -> None:
        """Execute all registered workplan hooks for a lifecycle point."""
        if not self._workplan_hooks:
            return

        method_name = hook_point.value

        for hook in self._workplan_hooks:
            try:
                method = getattr(hook, method_name)
                method(*args, **kwargs)
            except Exception as e:
                hook_name = hook.__class__.__name__
                logger.error(
                    "workload.plan_hook_error",
                    extra={"hook": hook_name, "method": method_name, "error": str(e)},
                )

    # ========== FACTS MANAGEMENT ==========

    def add_fact(self, thread_id: str, fact: str) -> None:
        """Add fact to workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.add_fact(fact)
        self.update_workspace(workspace)

    def remove_fact(self, thread_id: str, fact: str) -> None:
        """Remove fact from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.remove_fact(fact)
        self.update_workspace(workspace)

    def get_facts(self, thread_id: str) -> list[str]:
        """Get all facts from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.facts

    def clear_facts(self, thread_id: str) -> None:
        """Clear all facts from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.clear_facts()
        self.update_workspace(workspace)

    # ========== RESULTS MANAGEMENT ==========

    def add_result(self, thread_id: str, result: AgentResult) -> None:
        """Add result to workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.add_result(result)
        self.update_workspace(workspace)

    def get_results(self, thread_id: str) -> list[AgentResult]:
        """Get all results from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.results

    def get_results_by_agent(self, thread_id: str, agent_id: str) -> list[AgentResult]:
        """Get results by specific agent."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_results_by_agent(agent_id)

    def clear_results(self, thread_id: str) -> None:
        """Clear all results from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.clear_results()
        self.update_workspace(workspace)

    # ========== VARIABLES MANAGEMENT ==========

    def set_variable(self, thread_id: str, key: str, value: Any) -> None:
        """Set variable in workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.set_variable(key, value)
        self.update_workspace(workspace)

    def get_variable(self, thread_id: str, key: str, default: Any = None) -> Any:
        """Get variable from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_variable(key, default)

    def remove_variable(self, thread_id: str, key: str) -> None:
        """Remove variable from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.remove_variable(key)
        self.update_workspace(workspace)

    def get_all_variables(self, thread_id: str) -> dict[str, Any]:
        """Get all variables from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.variables

    # ========== ARTIFACTS MANAGEMENT ==========

    def add_artifact(
        self,
        thread_id: str,
        name: str,
        artifact_type: str,
        location: str,
        created_by: str,
        metadata: dict[str, Any] = None,
    ) -> None:
        """Add artifact to workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.add_artifact(name, artifact_type, location, created_by, metadata)
        self.update_workspace(workspace)

    def remove_artifact(self, thread_id: str, name: str) -> None:
        """Remove artifact from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.remove_artifact(name)
        self.update_workspace(workspace)

    def get_artifacts(self, thread_id: str) -> dict[str, Any]:
        """Get all artifacts from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.artifacts

    def get_artifacts_by_type(self, thread_id: str, artifact_type: str) -> list[Any]:
        """Get artifacts by type."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_artifact_by_type(artifact_type)

    # ========== CONVERSATION MANAGEMENT ==========

    def add_message(self, thread_id: str, message: ChatMessage) -> None:
        """Add message to conversation history."""
        workspace = self.get_workspace(thread_id)
        workspace.add_message(message)
        self.update_workspace(workspace)

    def add_messages(self, thread_id: str, messages: list[ChatMessage]) -> None:
        """Add multiple messages to conversation history."""
        workspace = self.get_workspace(thread_id)
        workspace.add_messages(messages)
        self.update_workspace(workspace)

    def get_conversation_history(self, thread_id: str) -> list[ChatMessage]:
        """Get conversation history."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.conversation_history

    def get_recent_messages(self, thread_id: str, count: int = 10) -> list[ChatMessage]:
        """Get recent messages from conversation."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_recent_messages(count)

    def clear_conversation(self, thread_id: str) -> None:
        """Clear conversation history."""
        workspace = self.get_workspace(thread_id)
        workspace.clear_conversation_history()
        self.update_workspace(workspace)

    # ========== TASKS MANAGEMENT ==========

    def add_task(self, thread_id: str, task: Task) -> None:
        """Add processed task to workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.context.tasks.append(task)
        self.update_workspace(workspace)

    def get_tasks(self, thread_id: str) -> list[Task]:
        """Get all tasks from workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.tasks

    def get_original_task(self, thread_id: str) -> Task | None:
        """Get original task that requires response."""
        workspace = self.get_workspace(thread_id)

        # Find first task that needs response and isn't itself a response
        for task in workspace.context.tasks:
            if task.should_respond and not task.is_response():
                return task

        return None

    # ========== SUMMARY & CONTEXT ==========

    def get_workspace_summary(self, thread_id: str) -> dict[str, Any]:
        """Get workspace content summary."""
        workspace = self.get_workspace(thread_id)
        return workspace.get_context_summary()

    def get_context_summary(self, thread_id: str) -> dict[str, Any]:
        """Get complete context summary."""
        workspace = self.get_workspace(thread_id)
        return {
            "workspace_summary": workspace.get_context_summary(),
            "conversation_summary": workspace.get_conversation_summary(),
            "recent_messages": len(workspace.get_recent_messages(5)),
            "has_tasks": len(workspace.context.tasks) > 0,
        }

    def clear_all_content(self, thread_id: str) -> None:
        """Clear all content from workspace."""
        workspace = self.get_workspace(thread_id)
        workspace.clear_all()
        self.update_workspace(workspace)

    # ========== MESSAGE CONTEXT IMPLEMENTATION ==========

    def sync_messages(
        self,
        thread_id: str,
        messages: list[ChatMessage],
        limit: int = 10,
        strategy: str = "conversation",
    ) -> int:
        """Sync recent messages to workspace."""
        # Filter out cancelled messages, then take the most recent N
        valid_messages = [msg for msg in messages if not msg.is_cancelled] if messages else []
        recent_messages = valid_messages[-limit:]

        if not recent_messages:
            return 0

        workspace = self.get_workspace(thread_id)

        # Apply strategy pattern
        if strategy == "facts":
            # Add as contextual facts for LLM context
            for msg in recent_messages:
                fact = f"Previous conversation - {msg.role.value}: {msg.content[:100]}..."
                workspace.add_fact(fact)
        elif strategy == "conversation":
            # Add to conversation history (proper message format, avoiding duplicates)
            workspace.append_messages_from_graphstate(recent_messages)
        elif strategy == "both":
            # Add as both facts and conversation history (avoiding duplicates)
            for msg in recent_messages:
                fact = f"Previous conversation - {msg.role.value}: {msg.content[:100]}..."
                workspace.add_fact(fact)
            workspace.append_messages_from_graphstate(recent_messages)
        else:
            raise ValueError(
                f"Unknown sync strategy: {strategy}. Use 'facts', 'conversation', or 'both'"
            )

        self.update_workspace(workspace)
        return len(recent_messages)

    # ========== WORK PLAN MANAGEMENT IMPLEMENTATION ==========

    # Class-level lock registry for thread-safe work plan operations
    _work_plan_locks: dict[str, threading.RLock] = defaultdict(threading.RLock)
    _locks_lock = threading.Lock()

    def _get_work_plan_lock(self, thread_id: str, owner_uid: str) -> threading.RLock:
        """Get or create a lock for the specific workplan."""
        lock_key = f"{thread_id}:{owner_uid}"
        with self._locks_lock:
            return self._work_plan_locks[lock_key]

    def _with_work_plan_lock(self, thread_id: str, owner_uid: str):
        """Context manager for thread-safe workplan operations."""
        return self._get_work_plan_lock(thread_id, owner_uid)

    def create_work_plan(
        self, thread_id: str, owner_uid: str, summary: str = "New Work Plan"
    ) -> WorkPlan:
        """Create a new work plan."""
        plan = WorkPlan(summary=summary, owner_uid=owner_uid, thread_id=thread_id)
        return plan

    def load_work_plan(self, thread_id: str, owner_uid: str) -> WorkPlan | None:
        """Load work plan from workspace."""
        try:
            workspace = self.get_workspace(thread_id)
            plan_data = workspace.context.work_plans.get(owner_uid)

            plan = None
            if plan_data:
                plan = WorkPlan(**plan_data)

            # POST-LOAD HOOK
            context = {
                "thread_id": thread_id,
                "owner_uid": owner_uid,
                "operation": "load",
                "found": plan is not None,
            }
            self._execute_workplan_hooks(WorkPlanHookPoint.POST_LOAD, plan, context)

            return plan
        except Exception as e:
            logger.error(
                "workload.plan_load_error",
                extra={"thread_id": thread_id, "owner_uid": owner_uid, "error": str(e)},
            )
            return None

    def save_work_plan(self, plan: WorkPlan) -> bool:
        """Save work plan to workspace (thread-safe)."""
        with self._with_work_plan_lock(plan.thread_id, plan.owner_uid):
            try:
                plan.mark_updated()

                workspace = self.get_workspace(plan.thread_id)
                workspace.context.work_plans[plan.owner_uid] = plan.model_dump()
                self.update_workspace(workspace)

                # POST-SAVE HOOK
                context = {
                    "thread_id": plan.thread_id,
                    "owner_uid": plan.owner_uid,
                    "operation": "save",
                    "success": True,
                }
                self._execute_workplan_hooks(WorkPlanHookPoint.POST_SAVE, plan, context)

                return True
            except Exception as e:
                logger.error(
                    "workload.plan_save_error",
                    extra={
                        "thread_id": plan.thread_id,
                        "owner_uid": plan.owner_uid,
                        "error": str(e),
                    },
                )
                return False

    def get_work_plan_status(self, thread_id: str, owner_uid: str) -> WorkPlanStatus:
        """Get work plan status."""
        plan = self.load_work_plan(thread_id, owner_uid)

        if not plan:
            return WorkPlanStatus(exists=False)

        counts = plan.get_status_counts()
        ready_items = plan.get_ready_items()

        # Check for local ready items (PENDING + LOCAL + dependencies met)
        has_local_ready = any(item.kind == WorkItemKind.LOCAL for item in ready_items)

        # Check for remote ready items (PENDING + REMOTE + dependencies met)
        has_remote_ready = any(item.kind == WorkItemKind.REMOTE for item in ready_items)

        # Calculate remote waiting items (IN_PROGRESS + REMOTE)
        remote_in_progress_items = [
            item
            for item in plan.items.values()
            if item.status == WorkItemStatus.IN_PROGRESS and item.kind == WorkItemKind.REMOTE
        ]

        has_remote_waiting = len(remote_in_progress_items) > 0
        waiting_items_count = len(remote_in_progress_items)

        # Check for responses needing interpretation (IN_PROGRESS + REMOTE + unprocessed responses)
        has_responses = any(item.has_unprocessed_responses() for item in plan.items.values())

        status = WorkPlanStatus(
            exists=True,
            total_items=len(plan.items),
            pending_items=counts.pending,
            in_progress_items=counts.in_progress,
            waiting_items=waiting_items_count,  # Calculated from IN_PROGRESS + REMOTE
            done_items=counts.done,
            failed_items=counts.failed,
            blocked_items=counts.blocked,
            has_local_ready=has_local_ready,
            has_remote_ready=has_remote_ready,
            has_remote_waiting=has_remote_waiting,
            has_responses=has_responses,
            is_complete=plan.is_complete(),
        )

        return status

    def update_work_item_status(
        self,
        thread_id: str,
        owner_uid: str,
        item_id: str,
        status: WorkItemStatus,
        error: str = None,
        correlation_task_id: str = None,
    ) -> bool:
        """Update work item status (thread-safe)."""

        with self._with_work_plan_lock(thread_id, owner_uid):
            plan = self.load_work_plan(thread_id, owner_uid)
            if not plan:
                return False

            item = plan.items.get(item_id)
            if not item:
                return False

            item.status = status

            if error and status == WorkItemStatus.FAILED:
                item.error = error

            if correlation_task_id:
                item.correlation_task_id = correlation_task_id

            # If marking as DONE, finalize the result
            if status == WorkItemStatus.DONE and item.result:
                item.result.success = True
                if item.result.metadata:
                    item.result.metadata.pop("needs_interpretation", None)

            item.mark_updated()
            self.save_work_plan(plan)
            return True

    def store_task_response_for_work_item(
        self,
        thread_id: str,
        owner_uid: str,
        correlation_task_id: str,
        response_content: str,
        from_uid: str,
        result_data: Any = None,
    ) -> bool:
        """Store response by finding and filling pending DelegationExchange."""
        plan = self.load_work_plan(thread_id, owner_uid)
        if not plan:
            return False

        # Find item with delegation exchange matching task_id
        target_item = None
        target_exchange = None

        for item in plan.items.values():
            if item.result and item.result.delegations:
                for exchange in item.result.delegations:
                    if exchange.task_id == correlation_task_id:
                        target_item = item
                        target_exchange = exchange
                        break
                if target_item:
                    break

        if not target_item or not target_exchange:
            return False

        # Extract structured data if provided
        data_to_store = None
        if isinstance(result_data, AgentResult):
            data_to_store = result_data.model_dump()
        elif isinstance(result_data, dict):
            data_to_store = result_data

        # Fill in response fields
        target_exchange.response_content = response_content
        target_exchange.response_data = data_to_store
        target_exchange.responded_by = from_uid
        target_exchange.responded_at = datetime.now(UTC).isoformat()
        # processed stays False - LLM needs to interpret

        target_item.mark_updated()
        return self.save_work_plan(plan)

    def atomic_update_work_item(
        self, thread_id: str, owner_uid: str, item_id: str, update_func: callable
    ) -> bool:
        """Atomically update a work item using the provided function."""
        with self._with_work_plan_lock(thread_id, owner_uid):
            plan = self.load_work_plan(thread_id, owner_uid)
            if not plan or item_id not in plan.items:
                return False

            item = plan.items[item_id]
            update_func(item, plan)
            item.mark_updated()
            return self.save_work_plan(plan)

    def get_all_work_plans(self, thread_id: str) -> dict[str, dict[str, Any]]:
        """Get all work plans in workspace."""
        workspace = self.get_workspace(thread_id)
        return workspace.context.work_plans.copy()

    def remove_work_plan(self, thread_id: str, owner_uid: str) -> None:
        """Remove work plan from workspace."""
        workspace = self.get_workspace(thread_id)
        if owner_uid in workspace.context.work_plans:
            del workspace.context.work_plans[owner_uid]
            self.update_workspace(workspace)

    def work_plan_exists(self, thread_id: str, owner_uid: str) -> bool:
        """Check if work plan exists."""
        workspace = self.get_workspace(thread_id)
        return owner_uid in workspace.context.work_plans
