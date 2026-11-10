"""
Specialized analyzers for orchestrator context building.

Provides focused analysis services:
- IntentClassifier: Understands user intent
- HealthAnalyzer: Detects work plan issues
- ProgressTracker: Monitors progress metrics
"""

from lumora.elements.workloads.domain import WorkItemStatus, WorkPlan
from plugins.mas.elements.orchestrator.context.models import (
    FutilityIndicator,
    ProgressMetrics,
    WorkPlanHealth,
)


class HealthAnalyzer:
    """Analyzes work plan health and detects issues."""

    def analyze(self, plan: WorkPlan | None) -> WorkPlanHealth:
        """
        Analyze work plan for health indicators.

        Detects:
        - Repeated failures (approaching max retries)
        - Stuck delegation loops (many attempts, unprocessed responses)
        - Blocked items (dependency issues)

        Args:
            plan: Work plan to analyze

        Returns:
            WorkPlanHealth with indicators and recommendations
        """
        if not plan:
            return WorkPlanHealth(progress_metrics=ProgressMetrics())

        futility_indicators = []
        blocked_analysis = []

        # Check each item for issues
        for item in plan.items.values():
            # Repeated failures
            if item.retry_count >= item.max_retries - 1:
                futility_indicators.append(
                    FutilityIndicator(
                        item_id=item.id,
                        issue_type="repeated_failure",
                        occurrences=item.retry_count,
                        description=(
                            f"Failed {item.retry_count} times, "
                            f"approaching max retries ({item.max_retries})"
                        ),
                        suggested_action="Consider marking as FAILED or trying different approach",
                    )
                )

            # Stuck in delegation loop
            if item.result and len(item.result.delegations) > 3:
                unprocessed = sum(1 for d in item.result.delegations if not d.processed)
                if unprocessed > 1:
                    futility_indicators.append(
                        FutilityIndicator(
                            item_id=item.id,
                            issue_type="stuck_delegation",
                            occurrences=len(item.result.delegations),
                            description=(
                                f"{len(item.result.delegations)} delegation attempts, "
                                f"{unprocessed} unprocessed responses"
                            ),
                            suggested_action=(
                                "Review agent responses - may need different agent or approach"
                            ),
                        )
                    )

            # Blocked by dependencies
            if item.status == WorkItemStatus.PENDING and item.dependencies:
                completed_deps = plan.get_completed_item_ids()
                blocked_by = [dep for dep in item.dependencies if dep not in completed_deps]
                if blocked_by:
                    # Get titles of blocking items for clarity
                    blocker_titles = []
                    truly_blocking = []
                    for dep in blocked_by:
                        dep_item = plan.items.get(dep)
                        if dep_item:
                            # If dependency has unprocessed responses, it's not truly blocking
                            # (the response is here, LLM will process it this cycle)
                            if dep_item.result and dep_item.result.has_unprocessed_responses:
                                # Not truly blocking - response available for processing
                                continue
                            blocker_titles.append(f"{dep} ({dep_item.status.value})")
                            truly_blocking.append(dep)
                        else:
                            blocker_titles.append(dep)
                            truly_blocking.append(dep)

                    # Only report as blocked if there are truly blocking dependencies
                    if truly_blocking:
                        blocked_analysis.append(
                            f"{item.id} blocked by: {', '.join(blocker_titles)}"
                        )

        # Basic progress metrics (will be enriched by ProgressTracker)
        total = len(plan.items)
        done = len(plan.get_items_by_status(WorkItemStatus.DONE))
        failed = len(plan.get_items_by_status(WorkItemStatus.FAILED))

        progress = ProgressMetrics(
            total_cycles=0,  # Will be set by ProgressTracker
            cycles_without_completion=0,
            items_completed_this_cycle=0,
            items_blocked=len(blocked_analysis),
            is_stalled=False,
            is_regressing=failed > done and total > 2,
        )

        return WorkPlanHealth(
            futility_indicators=futility_indicators,
            progress_metrics=progress,
            blocked_items_analysis=blocked_analysis,
            has_critical_issues=len(futility_indicators) > 0,
            needs_pivot=progress.is_regressing,
            needs_user_input=len(blocked_analysis) > 3,
        )


class ProgressTracker:
    """Tracks progress metrics across orchestration cycles."""

    def __init__(self):
        """Initialize progress tracker with zero state."""
        self._total_cycles = 0
        self._cycles_without_completion = 0
        self._last_done_count = 0

    def update(self, plan: WorkPlan | None) -> ProgressMetrics:
        """
        Update and return progress metrics.

        Tracks:
        - Total cycles run
        - Cycles without any completion
        - Items completed this cycle
        - Stalled detection (no progress for 5+ cycles)

        Args:
            plan: Current work plan

        Returns:
            ProgressMetrics with current state
        """
        self._total_cycles += 1

        if not plan:
            return ProgressMetrics(
                total_cycles=self._total_cycles,
                cycles_without_completion=self._cycles_without_completion,
            )

        # Count current done items
        done_items = plan.get_items_by_status(WorkItemStatus.DONE)
        current_done = len(done_items)

        # Check if we completed anything this cycle
        completed_this_cycle = max(0, current_done - self._last_done_count)

        if completed_this_cycle == 0:
            self._cycles_without_completion += 1
        else:
            self._cycles_without_completion = 0  # Reset on progress

        self._last_done_count = current_done

        # Detect stall (no progress for 5+ cycles)
        is_stalled = self._cycles_without_completion >= 5

        # Count blocked items
        blocked = 0
        if plan.items:
            for item in plan.items.values():
                if item.status == WorkItemStatus.PENDING and item.dependencies:
                    completed_deps = plan.get_completed_item_ids()
                    if not all(dep in completed_deps for dep in item.dependencies):
                        blocked += 1

        return ProgressMetrics(
            total_cycles=self._total_cycles,
            cycles_without_completion=self._cycles_without_completion,
            items_completed_this_cycle=completed_this_cycle,
            items_blocked=blocked,
            is_stalled=is_stalled,
            is_regressing=False,  # Will be set by HealthAnalyzer
        )
