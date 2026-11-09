from flareward.programs.graph.models import AdjacentNodes

"""Orchestrator-specific phase validators."""

from flareward.elements.agents.phases.models import PhaseValidationContext
from flareward.elements.workloads.domain import WorkItemKind, WorkItemStatus, WorkPlan


class AllocationValidator:
    """
    Validates allocation phase to ensure proper assignment-delegation coordination.

    SOLID SRP: Responsible only for allocation phase validation logic.
    """

    def validate(self, context: PhaseValidationContext) -> str:
        """
        Validate allocation phase state.

        Checks for common allocation issues:
        - Remote items assigned but not delegated (infinite loop risk)
        - Remote items delegated but not assigned (confusion)
        - Items assigned to non-adjacent nodes

        Args:
            context: Validation context with work plan and adjacent nodes

        Returns:
            Guidance text if issues found, empty string if all good
        """
        plan = context.plan
        if not isinstance(plan, WorkPlan) or not plan.items:
            return ""

        # Get adjacent nodes (AdjacentNodes model)
        adjacent_nodes = context.adjacent_nodes
        if adjacent_nodes is None:
            adjacent_nodes = AdjacentNodes.empty()

        issues: list[str] = []

        # Check assignment-delegation coordination for remote items
        for item in plan.items.values():
            if item.status == WorkItemStatus.PENDING and item.kind == WorkItemKind.REMOTE:
                if not item.assigned_uid:
                    issues.append(
                        f"Remote item {item.id} has no assigned_uid. "
                        f"Use AssignWorkItemTool to assign it to a specific node."
                    )
                elif not item.result or not item.result.delegations:
                    issues.append(
                        f"Remote item {item.id} assigned but not delegated. "
                        f"Use DelegateTaskTool to send it to {item.assigned_uid}. "
                        f"Set work_item_id={item.id}."
                    )
                elif item.assigned_uid not in adjacent_nodes:
                    issues.append(
                        f"Item {item.id} assigned to non-adjacent node {item.assigned_uid}. "
                        f"Use ListAdjacentNodesTool to see available nodes."
                    )

        if issues:
            return "ALLOCATION ISSUES FOUND:\n" + "\n".join(issues)
        return ""


class PlanningValidator:
    """
    Validates planning phase to ensure work plan quality.

    Supports multi-request workflows on same thread.

    SOLID SRP: Responsible only for planning phase validation logic.
    """

    def validate(self, context: PhaseValidationContext) -> str:
        """
        Validate planning phase state with multi-request awareness.

        Checks for common planning issues:
        - Missing work plan
        - Empty work plan
        - Circular dependencies
        - Provides guidance when existing plan is present

        Args:
            context: Validation context with work plan

        Returns:
            Guidance text if issues found, empty string if all good
        """
        plan = context.plan

        if not isinstance(plan, WorkPlan):
            return "No work plan found. Use CreateOrUpdateWorkPlanTool to create one."

        if not plan.items:
            return "Empty work plan. Break down the request into specific work items."

        # Check for circular dependencies
        circular = self._find_circular_dependencies(plan)
        if circular:
            return f"Circular dependencies detected: {circular}. Fix dependency chain."

        # ✅ NEW: Provide guidance for existing work plans (multi-request scenario)
        has_done_items = any(item.status == WorkItemStatus.DONE for item in plan.items.values())
        has_in_progress = any(
            item.status == WorkItemStatus.IN_PROGRESS for item in plan.items.values()
        )
        has_failed = any(item.status == WorkItemStatus.FAILED for item in plan.items.values())

        if has_done_items or has_in_progress or has_failed:
            # Existing work plan with activity - provide contextual guidance
            guidance_lines = []
            guidance_lines.append("📋 EXISTING WORK PLAN DETECTED:")

            done_count = sum(
                1 for item in plan.items.values() if item.status == WorkItemStatus.DONE
            )
            in_progress_count = sum(
                1 for item in plan.items.values() if item.status == WorkItemStatus.IN_PROGRESS
            )
            pending_count = sum(
                1 for item in plan.items.values() if item.status == WorkItemStatus.PENDING
            )
            failed_count = sum(
                1 for item in plan.items.values() if item.status == WorkItemStatus.FAILED
            )

            guidance_lines.append(
                f"   Status: {done_count} done, {in_progress_count} in progress, "
                f"{pending_count} pending, {failed_count} failed"
            )
            guidance_lines.append("")
            guidance_lines.append("   FOR NEW REQUEST:")
            guidance_lines.append(
                "   - If independent work → Add new items with CreateOrUpdateWorkPlanTool"
            )
            guidance_lines.append(
                "   - If follow-up on completed work → Add items depending on DONE items"
            )
            guidance_lines.append(
                "   - If clarification only → May not need new items, proceed to next phase"
            )
            guidance_lines.append(
                "   - If re-do failed work → Update failed items with new approach"
            )
            guidance_lines.append("")
            guidance_lines.append(
                "   REMEMBER: CreateOrUpdateWorkPlanTool preserves existing item status!"
            )

            return "\n".join(guidance_lines)

        return ""

    def _find_circular_dependencies(self, plan: WorkPlan) -> list[str]:
        """
        Find circular dependencies using DFS.

        Args:
            plan: Work plan to check

        Returns:
            List of item IDs involved in circular dependencies
        """
        visited = set()
        rec_stack = set()
        circular_items = []

        def dfs(item_id: str) -> bool:
            if item_id in rec_stack:
                circular_items.append(item_id)
                return True
            if item_id in visited:
                return False

            visited.add(item_id)
            rec_stack.add(item_id)

            item = plan.items.get(item_id)
            if item and item.dependencies:
                for dep_id in item.dependencies:
                    if dfs(dep_id):
                        circular_items.append(item_id)
                        return True

            rec_stack.remove(item_id)
            return False

        for item_id in plan.items:
            if item_id not in visited:
                dfs(item_id)

        return list(set(circular_items))


class ExecutionValidator:
    """
    Validates execution phase to ensure local work items are properly handled.

    SOLID SRP: Responsible only for execution phase validation logic.
    """

    def validate(self, context: PhaseValidationContext) -> str:
        """
        Validate execution phase state with actionable guidance.

        Checks for execution issues:
        - Local items ready for execution (dependencies satisfied)
        - Local items blocked by dependencies
        - ⚠️  Local items marked DONE/FAILED without execution record (DATA INTEGRITY)
        - ⚠️  Local items with execution record but not marked (INCOMPLETE WORKFLOW)

        Args:
            context: Validation context with work plan

        Returns:
            Guidance text if issues found, empty string if all good
        """
        plan = context.plan
        if not isinstance(plan, WorkPlan) or not plan.items:
            return ""

        guidance_lines: list[str] = []

        # Get completed item IDs for dependency checking
        completed_ids = plan.get_completed_item_ids()

        # Check for ready local items (PENDING + LOCAL + no blocking dependencies)
        ready_local_items = [
            item
            for item in plan.items.values()
            if item.status == WorkItemStatus.PENDING
            and item.kind == WorkItemKind.LOCAL
            and not item.is_blocked(completed_ids)
        ]

        # Check for blocked local items (PENDING + LOCAL + has blocking dependencies)
        blocked_local_items = [
            item
            for item in plan.items.values()
            if item.status == WorkItemStatus.PENDING
            and item.kind == WorkItemKind.LOCAL
            and item.is_blocked(completed_ids)
        ]

        if ready_local_items:
            guidance_lines.append(
                f"⚡ READY FOR EXECUTION: {len(ready_local_items)} LOCAL item(s) ready to execute."
            )
            guidance_lines.append("   ACTION: For each ready item:")
            guidance_lines.append("   1. Review item description for requirements")
            guidance_lines.append("   2. Execute the work (use domain tools OR direct reasoning)")
            guidance_lines.append(
                "   3. RecordLocalExecutionTool(item_id='...', outcome='what you did and achieved')"
            )
            guidance_lines.append("      → This automatically marks the item as DONE")
            guidance_lines.append("")

            # Show ALL items (no truncation)
            for item in ready_local_items:
                guidance_lines.append(f"   - {item.id}: {item.title}")
            guidance_lines.append("")

        if blocked_local_items:
            guidance_lines.append(
                f"⏸️  BLOCKED: {len(blocked_local_items)} LOCAL item(s) waiting for dependencies."
            )
            guidance_lines.append(
                "   These items will become ready once their dependencies complete."
            )
            guidance_lines.append("")

        return "\n".join(guidance_lines) if guidance_lines else ""


class MonitoringValidator:
    """
    Validates monitoring phase to ensure proper response handling.

    SOLID SRP: Responsible only for monitoring phase validation logic.
    """

    def validate(self, context: PhaseValidationContext) -> str:
        """
        Validate monitoring phase state and provide actionable guidance.

        Checks for:
        - Items with responses needing interpretation
        - Delegated items waiting for responses
        - Items that may need follow-up

        Args:
            context: Validation context with work plan

        Returns:
            Guidance text with specific actions to take
        """
        plan = context.plan
        if not isinstance(plan, WorkPlan) or not plan.items:
            return ""

        guidance_lines: list[str] = []

        # Check for items with responses needing interpretation (PRIORITY)
        items_with_responses = [
            item
            for item in plan.items.values()
            if item.status == WorkItemStatus.IN_PROGRESS
            and item.kind == WorkItemKind.REMOTE
            and item.result
            and item.result.has_unprocessed_responses
        ]

        if items_with_responses:
            guidance_lines.append(
                f"⚠️ RESPONSES READY: {len(items_with_responses)} work item(s) "
                "have responses waiting for your interpretation."
            )
            guidance_lines.append(
                "   ACTION: Review the responses in 'Current Work Plan' above, then decide:"
            )
            guidance_lines.append("   - If satisfactory → MarkWorkItemStatusTool(status='done')")
            guidance_lines.append(
                "   - If needs clarification → DelegateTaskTool (re-delegate with "
                "follow-up question)"
            )
            guidance_lines.append(
                "   - If impossible to complete → "
                "MarkWorkItemStatusTool(status='failed', notes='reason')"
            )
            guidance_lines.append("")

        # Check for delegated items still waiting (no responses yet)
        delegated_no_response = [
            item
            for item in plan.items.values()
            if item.status == WorkItemStatus.IN_PROGRESS
            and item.kind == WorkItemKind.REMOTE
            and item.result
            and item.result.pending_exchange is not None
        ]

        if delegated_no_response:
            guidance_lines.append(
                f"⏳ WAITING: {len(delegated_no_response)} delegated item(s) "
                "still waiting for responses."
            )
            guidance_lines.append(
                "   ACTION: Wait for responses to arrive. If timeout concerns, "
                "consider retry/reallocation."
            )
            guidance_lines.append("")

        # Check for items blocked by failed dependencies (NEW)
        blocked_by_failure = plan.get_items_blocked_by_failure()

        if blocked_by_failure:
            guidance_lines.append(
                f"🚫 BLOCKED BY FAILURE: {len(blocked_by_failure)} item(s) "
                "blocked by failed dependencies."
            )
            guidance_lines.append(
                "   ACTION: These items cannot proceed until dependencies are resolved:"
            )
            guidance_lines.append(
                "   - Option 1: Retry failed dependency (re-delegate or re-execute)"
            )
            guidance_lines.append(
                "   - Option 2: Mark blocked items as 'failed' if dependency is unrecoverable"
            )
            guidance_lines.append(
                "   - Option 3: Modify work plan to remove dependency if not truly needed"
            )
            guidance_lines.append("")

            # List blocked items with their failed dependencies
            for item in blocked_by_failure[:3]:  # Show first 3
                failed_deps = [
                    dep_id
                    for dep_id in item.dependencies
                    if plan.items.get(dep_id, None)
                    and plan.items[dep_id].status == WorkItemStatus.FAILED
                ]
                guidance_lines.append(f"   - {item.id}: blocked by {', '.join(failed_deps)}")
            if len(blocked_by_failure) > 3:
                guidance_lines.append(f"   ... and {len(blocked_by_failure) - 3} more")

        if guidance_lines:
            return "MONITORING GUIDANCE:\n" + "\n".join(guidance_lines)
        return ""


class SynthesisValidator:
    """
    Validates synthesis phase to ensure proper completion and quality.

    SOLID SRP: Responsible only for synthesis phase validation logic.
    """

    def validate(self, context: PhaseValidationContext) -> str:
        """
        Validate synthesis phase state and readiness.

        Checks for synthesis readiness:
        - Work completion status
        - Synthesis quality reminders
        - Result availability

        Args:
            context: Validation context with work plan

        Returns:
            Guidance text with synthesis checklist and reminders
        """
        plan = context.plan
        if not isinstance(plan, WorkPlan) or not plan.items:
            return ""

        guidance_lines: list[str] = []

        # Count items by status
        done_items = [item for item in plan.items.values() if item.status == WorkItemStatus.DONE]
        failed_items = [
            item for item in plan.items.values() if item.status == WorkItemStatus.FAILED
        ]
        incomplete_items = [
            item
            for item in plan.items.values()
            if item.status not in [WorkItemStatus.DONE, WorkItemStatus.FAILED]
        ]

        if incomplete_items:
            # Work not complete - shouldn't be in synthesis yet
            guidance_lines.append(
                f"⚠️  WORK INCOMPLETE: {len(incomplete_items)} item(s) still in progress."
            )
            guidance_lines.append(
                f"   Status: {len(done_items)} done, {len(failed_items)} failed, "
                f"{len(incomplete_items)} incomplete"
            )
            guidance_lines.append("")
            guidance_lines.append(
                "   Synthesis typically waits for all work to finish (DONE or FAILED)."
            )
            guidance_lines.append("   If proceeding anyway, note incomplete items in synthesis.")
        else:
            # All work complete - ready for synthesis
            guidance_lines.append(f"✅ WORK COMPLETE: All {len(plan.items)} items finished.")
            guidance_lines.append(f"   Status: {len(done_items)} done, {len(failed_items)} failed")
            guidance_lines.append("")
            guidance_lines.append("   SYNTHESIS CHECKLIST:")
            guidance_lines.append("   ✓ Review all results in 'Current Work Plan' section above")
            guidance_lines.append("   ✓ Include findings from all DONE items")
            guidance_lines.append(
                "   ✓ Structure synthesis logically (overview → findings → insights → deliverables)"
            )
            guidance_lines.append("   ✓ Address original request/objective")

            if failed_items:
                guidance_lines.append("   ✓ Mention failed items briefly with context")

            guidance_lines.append("   ✓ Focus on VALUE delivered, not internal process")
            guidance_lines.append("   ✓ Be concise yet comprehensive")
            guidance_lines.append("")

            # Check for items with results
            items_with_results = [
                item
                for item in done_items
                if item.result
                and (
                    item.result.final_summary
                    or item.result.delegations
                    or item.result.local_execution
                )
            ]

            if items_with_results:
                guidance_lines.append(
                    f"   📊 {len(items_with_results)} DONE item(s) have results to synthesize"
                )

            if len(items_with_results) < len(done_items):
                items_no_results = len(done_items) - len(items_with_results)
                guidance_lines.append(
                    f"   ⚠️  {items_no_results} DONE item(s) have no explicit results "
                    "(may still be valuable)"
                )

        if guidance_lines:
            return "SYNTHESIS GUIDANCE:\n" + "\n".join(guidance_lines)
        return ""
