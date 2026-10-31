from mas.graph.graph_plan import GraphPlan

from ..models import MessageCode, MessageSeverity, ValidationMessage
from .models import DependencyIssue, DependencyIssueType


class DependencyChecker:
    """Business logic for checking step dependencies."""

    def check_dependencies(
        self, plan: GraphPlan
    ) -> tuple[list[DependencyIssue], list[ValidationMessage]]:
        """Check that all step dependencies and branch targets exist."""
        issues = []
        messages = []
        step_ids = {step.uid for step in plan.steps}

        for step in plan.steps:
            # Check step dependencies
            for dep in step.after:
                if dep not in step_ids:
                    issue = DependencyIssue(
                        step_id=step.uid,
                        missing_dependency=dep,
                        issue_type=DependencyIssueType.MISSING_STEP,
                    )
                    issues.append(issue)
                    messages.append(
                        ValidationMessage(
                            text=f"Step '{step.uid}' depends on missing step '{dep}'",
                            severity=MessageSeverity.ERROR,
                            code=MessageCode.MISSING_DEPENDENCY,
                            context={"step_id": step.uid, "missing_step": dep},
                        )
                    )

            # Check branch targets
            for branch_name, target in step.branches.items():
                if target not in step_ids:
                    issue = DependencyIssue(
                        step_id=step.uid,
                        missing_dependency=target,
                        issue_type=DependencyIssueType.MISSING_BRANCH_TARGET,
                    )
                    issues.append(issue)
                    messages.append(
                        ValidationMessage(
                            text=f"Step '{step.uid}' branches to unknown step '{target}'",
                            severity=MessageSeverity.ERROR,
                            code=MessageCode.MISSING_BRANCH_TARGET,
                            context={"step_id": step.uid, "branch": branch_name, "target": target},
                        )
                    )

        return issues, messages
