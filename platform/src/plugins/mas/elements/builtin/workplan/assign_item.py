"""
Tool for assigning work items to execution targets.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from flareward.elements.agents.constants import ToolNames
from flareward.elements.ports.tool import BaseTool
from flareward.elements.workloads.domain import WorkItemKind
from flareward.services.interactions.tools.models import ToolAccessMode


class AssignItemArgs(BaseModel):
    """Arguments for assigning a work item."""

    item_id: str = Field(..., description="ID of the work item to assign")
    kind: WorkItemKind = Field(
        ...,
        description=(
            "Assignment type: 'local' (execute on this node) or 'remote' (delegate to another node)"
        ),
    )
    assigned_uid: str | None = Field(
        None, description="UID of target node (required for remote assignments only)"
    )


class AssignWorkItemTool(BaseTool):
    """Assign a work item to local or remote execution."""

    access_mode = ToolAccessMode.WRITE

    name = ToolNames.WORKPLAN_ASSIGN
    description = """Assign a work item for local or remote execution.
    
    ASSIGNMENT TYPES:
    - 'local': Execute the work item on this node (you will handle it)
    - 'remote': Delegate the work item to another node (specify assigned_uid)
    
    NOTE: This tool only assigns work items. For remote items, you must also 
    use DelegateTaskTool to actually send the task to the assigned node."""
    args_schema = AssignItemArgs

    def __init__(
        self,
        get_thread_id: Callable[[], str],
        get_owner_uid: Callable[[], str],
        get_workload_service: Callable[[], Any],
    ):
        self._get_thread_id = get_thread_id
        self._get_owner_uid = get_owner_uid
        self._get_workload_service = get_workload_service

    async def run(self, **kwargs) -> dict[str, Any]:
        """Assign work item (thread-safe)."""
        args = AssignItemArgs(**kwargs)

        thread_id = self._get_thread_id()
        owner_uid = self._get_owner_uid()
        workload_service = self._get_workload_service()
        workspace_service = workload_service.get_workspace_service()

        def assign_item(item, plan):
            """Update function for atomic assignment."""
            item.kind = args.kind
            item.assigned_uid = args.assigned_uid
            item.updated_at = plan.updated_at

        success = workspace_service.atomic_update_work_item(
            thread_id, owner_uid, args.item_id, assign_item
        )

        if not success:
            return {
                "success": False,
                "error": f"Failed to assign work item {args.item_id} (not found or plan missing)",
            }

        return {
            "success": True,
            "item_id": args.item_id,
            "assignment": {"kind": args.kind, "assigned_uid": args.assigned_uid},
        }
