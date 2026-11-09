"""
Tool for recording local execution results.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from flareward.elements.agents.constants import ToolNames
from flareward.elements.ports.tool import BaseTool
from flareward.elements.workloads.domain import (
    LocalExecution,
    WorkItemKind,
    WorkItemResult,
    WorkItemStatus,
)
from flareward.services.interactions.tools.models import ToolAccessMode


class RecordLocalExecutionArgs(BaseModel):
    """Arguments for recording local execution outcome."""

    item_id: str = Field(..., description="ID of the LOCAL work item you just executed")
    outcome: str = Field(
        ...,
        description="""Complete execution result in natural narrative format.
        
        Include:
        - What you did (approach, steps, tools if used)
        - How you did it (methods, reasoning)
        - What you achieved (results, findings, outputs, conclusions)
        
        Write naturally - this is for the SYNTHESIS phase to understand your work.""",
    )


class RecordLocalExecutionTool(BaseTool):
    """Record execution results for LOCAL work items and mark as DONE.

    Use this tool after executing a LOCAL work item to capture what you did and what you achieved.
    Write naturally - describe your execution as a complete narrative.

    Workflow (ONE STEP):
    1. Execute LOCAL work item (use domain tools, reasoning, analysis)
    2. Call RecordLocalExecutionTool to capture outcome → automatically marks as DONE

    This creates a rich execution record for the SYNTHESIS phase to use."""

    access_mode = ToolAccessMode.WRITE

    name = ToolNames.WORKPLAN_RECORD_EXECUTION
    description = """Record the outcome of executing a LOCAL work item and mark it as DONE.
    
    After you execute work locally (with or without tools), use this to capture:
    - What you did
    - How you approached it
    - What you achieved
    
    Write as a natural narrative - include all relevant details for synthesis.
    This will automatically mark the item as DONE."""

    args_schema = RecordLocalExecutionArgs

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
        """Record local execution outcome (thread-safe)."""
        args = RecordLocalExecutionArgs(**kwargs)

        thread_id = self._get_thread_id()
        owner_uid = self._get_owner_uid()
        workload_service = self._get_workload_service()
        workspace_service = workload_service.get_workspace_service()

        def update_execution(item, plan):
            """Update function to record execution outcome and mark as DONE."""
            # Validate it's a LOCAL item
            if item.kind == WorkItemKind.LOCAL:
                # Initialize result if needed
                if not item.result:
                    item.result = WorkItemResult()

                # Create LocalExecution record
                item.result.local_execution = LocalExecution(outcome=args.outcome)

                # Automatically mark as DONE (atomic operation)
                item.status = WorkItemStatus.DONE
            elif item.kind == WorkItemKind.REMOTE:
                # Prevent recording for REMOTE items
                raise ValueError(
                    f"Cannot record local execution for REMOTE item '{args.item_id}'. "
                    "REMOTE items track results through delegation exchanges, "
                    "not local execution records. "
                    f"Use DelegateTaskTool to work with REMOTE items."
                )
            else:
                raise ValueError(f"Unknown work item kind '{item.kind}' for item '{args.item_id}'")

        try:
            success = workspace_service.atomic_update_work_item(
                thread_id, owner_uid, args.item_id, update_execution
            )

            if not success:
                return {
                    "success": False,
                    "error": f"Work item '{args.item_id}' not found in work plan",
                }

            return {
                "success": True,
                "item_id": args.item_id,
                "status": "done",
                "message": f"Execution outcome recorded for '{args.item_id}' and marked as DONE.",
            }

        except ValueError as e:
            # Validation error (e.g., trying to record for REMOTE item)
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"Failed to record execution: {str(e)}"}
