"""
Tool for summarizing work plans.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from mas.application.agents.constants import ToolNames
from mas.application.ports.tool import BaseTool
from mas.domain.workloads import WorkItemKind, WorkItemStatus


class SummarizeWorkPlanArgs(BaseModel):
    """Empty args schema (no arguments required)."""

    pass


class SummarizeWorkPlanTool(BaseTool):
    """Generate a final summary of completed work plan with results."""

    name = ToolNames.WORKPLAN_SUMMARIZE
    description = """Generate a comprehensive summary of the completed work plan,
including results and deliverables.
    
    Use this in SYNTHESIS phase to create a final report for the user. This should include
    what was accomplished, key results from each work item, and any deliverables created."""
    args_schema = SummarizeWorkPlanArgs

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
        """Generate summary with full structured data."""
        thread_id = self._get_thread_id()
        owner_uid = self._get_owner_uid()
        workload_service = self._get_workload_service()
        workspace_service = workload_service.get_workspace_service()

        plan = workspace_service.load_work_plan(thread_id, owner_uid)
        if not plan:
            return {"summary": "No work plan found", "items": []}

        # Build comprehensive summary with results
        lines = [
            f"Work Plan Summary: {plan.summary}",
            f"Total Items: {len(plan.items)}",
            f"Status: {plan.get_status_counts().model_dump()}",
        ]

        # ✅ NEW: Collect structured item data for LLM
        items_data = []

        # Add completed items with results
        completed_items = plan.get_items_by_status(WorkItemStatus.DONE)
        if completed_items:
            lines.append(f"\nCompleted Work ({len(completed_items)}):")
            for item in completed_items:
                lines.append(f"  ✅ {item.title}")
                if item.result and item.result.final_summary:
                    lines.append(f"     Result: {item.result.final_summary}")
                if item.assigned_uid:
                    lines.append(f"     Completed by: {item.assigned_uid}")

                # ✅ Add structured data
                items_data.append(
                    {
                        "id": item.id,
                        "title": item.title,
                        "status": item.status.value,
                        "assigned_to": item.assigned_uid,
                        "result": {
                            "summary": item.result.final_summary if item.result else None,
                            "data": item.result.data if item.result else None,
                            "success": item.result.success if item.result else None,
                            "metadata": item.result.metadata if item.result else None,
                        }
                        if item.result
                        else None,
                    }
                )

        # Add IN_PROGRESS (REMOTE) items with responses (pending interpretation)
        in_progress_items = plan.get_items_by_status(WorkItemStatus.IN_PROGRESS)
        if in_progress_items:
            # Check for REMOTE items with delegation history
            remote_with_responses = [
                item
                for item in in_progress_items
                if item.kind == WorkItemKind.REMOTE
                and item.result
                and item.result.has_unprocessed_responses
            ]
            if remote_with_responses:
                lines.append(f"\nWaiting for Interpretation ({len(remote_with_responses)}):")
                for item in remote_with_responses:
                    delegation_count = len(item.result.delegations)
                    latest = item.result.latest_exchange

                    # Show item with delegation count
                    lines.append(
                        f"  ⏳ {item.title} "
                        f"({delegation_count} delegation{'s' if delegation_count > 1 else ''})"
                    )

                    if delegation_count > 1:
                        # Multi-turn conversation - show all exchanges
                        lines.append(f"     Conversation with {item.assigned_uid}:")
                        for ex in item.result.delegations:
                            if ex.response_content:
                                lines.append(
                                    f"       [{ex.sequence}] {ex.responded_by}: "
                                    f"{ex.response_content}"
                                )
                    else:
                        # Single exchange - show full content
                        if latest and latest.response_content:
                            lines.append(f"     Response from {latest.responded_by}:")
                            lines.append(f"       {latest.response_content}")

                    # ✅ Add structured data for LLM (includes full conversation history)
                    items_data.append(
                        {
                            "id": item.id,
                            "title": item.title,
                            "status": item.status.value,
                            "kind": item.kind.value,
                            "assigned_to": item.assigned_uid,
                            "conversation": [
                                {
                                    "query": ex.query,
                                    "response": ex.response_content,
                                    "from": ex.responded_by,
                                    "data": ex.response_data,
                                    "sequence": ex.sequence,
                                    "task_id": ex.task_id,
                                    "delegated_at": ex.delegated_at,
                                    "responded_at": ex.responded_at,
                                }
                                for ex in item.result.delegations
                                if ex.response_content
                            ],
                            "delegation_count": delegation_count,
                            "latest_exchange": {
                                "query": latest.query,
                                "response": latest.response_content,
                                "from": latest.responded_by,
                                "data": latest.response_data,
                            }
                            if latest and latest.response_content
                            else None,
                        }
                    )

        # Add failed items with errors
        failed_items = plan.get_items_by_status(WorkItemStatus.FAILED)
        if failed_items:
            lines.append(f"\nFailed Work ({len(failed_items)}):")
            for item in failed_items:
                lines.append(f"  ❌ {item.title}")
                if item.error:
                    lines.append(f"     Error: {item.error}")

                # ✅ Add structured data
                items_data.append(
                    {
                        "id": item.id,
                        "title": item.title,
                        "status": item.status.value,
                        "assigned_to": item.assigned_uid,  # 🎯 Agent/node UID shown here
                        "error": item.error,
                    }
                )

        # Add any incomplete items
        incomplete_statuses = [WorkItemStatus.PENDING, WorkItemStatus.IN_PROGRESS]
        incomplete_items = []
        for status in incomplete_statuses:
            incomplete_items.extend(plan.get_items_by_status(status))

        if incomplete_items:
            lines.append(f"\nIncomplete Work ({len(incomplete_items)}):")
            for item in incomplete_items:
                lines.append(f"  ⏳ {item.title} ({item.status.value})")

                # ✅ Add structured data
                items_data.append(
                    {
                        "id": item.id,
                        "title": item.title,
                        "status": item.status.value,
                        "assigned_to": item.assigned_uid,  # 🎯 Agent/node UID shown here
                    }
                )

        # ✅ Return BOTH text summary AND structured data
        return {
            "summary": "\n".join(lines),
            "items": items_data,  # LLM can now access all AgentResult fields!
        }
