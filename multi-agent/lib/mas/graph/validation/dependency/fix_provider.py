from mas.graph.graph_plan import GraphPlan

from ..fix_models import FixSuggestion, FixType
from ..interfaces import FixSuggestionProvider
from ..models import MessageCode, ValidationReport
from .checker import DependencyChecker
from .models import DependencyFixType, DependencyIssueType, DependencyType


class DependencyFixProvider(FixSuggestionProvider):
    """Provides fix suggestions for dependency issues in the graph."""

    name = "dependency"

    def __init__(self, *args, **kwargs):
        self._checker = DependencyChecker()

    def suggest_fixes(
        self, plan: GraphPlan, validation_report: ValidationReport | None = None
    ) -> list[FixSuggestion]:
        """Suggest fixes for dependency issues."""
        suggestions = []

        if not validation_report or not validation_report.details:
            return suggestions

        dependency_issues = validation_report.details.get("dependency_issues", [])
        if not dependency_issues:
            return suggestions

        # Extract message codes from validation report
        message_codes = self._extract_message_codes(validation_report)

        # Group issues by type for better analysis
        missing_step_issues = []
        missing_branch_issues = []

        for issue_data in dependency_issues:
            issue_type = issue_data.get("issue_type")
            if issue_type == DependencyIssueType.MISSING_STEP:
                missing_step_issues.append(issue_data)
            elif issue_type == DependencyIssueType.MISSING_BRANCH_TARGET:
                missing_branch_issues.append(issue_data)

        # Generate suggestions for missing step dependencies
        suggestions.extend(
            self._suggest_missing_step_fixes(missing_step_issues, plan, message_codes)
        )

        # Generate suggestions for missing branch targets
        suggestions.extend(
            self._suggest_missing_branch_fixes(missing_branch_issues, plan, message_codes)
        )

        return suggestions

    def _extract_message_codes(self, validation_report: ValidationReport) -> dict[str, MessageCode]:
        """Extract message codes from validation report."""
        codes = {}
        for message in validation_report.messages:
            if message.code:
                step_id = message.context.get("step_id", "general")
                codes[step_id] = message.code
        return codes

    def _suggest_missing_step_fixes(
        self,
        missing_step_issues: list[dict],
        plan: GraphPlan,
        message_codes: dict[str, MessageCode],
    ) -> list[FixSuggestion]:
        """Suggest fixes for missing step dependencies."""
        suggestions = []

        for issue_data in missing_step_issues:
            step_id = issue_data.get("step_id")
            missing_dependency = issue_data.get("missing_dependency")

            if not step_id or not missing_dependency:
                continue

            step = plan.get_step(step_id)
            if not step:
                continue

            step_name = step.meta.display_name if step.meta.display_name else step_id
            code = message_codes.get(step_id, MessageCode.MISSING_DEPENDENCY)

            # Strategy 1: Create the missing step
            suggestions.append(
                FixSuggestion(
                    text=(
                        f"Create the missing step '{missing_dependency}' that '{step_name}' "
                        f"depends on"
                    ),
                    fix_type=FixType.ADD_NODE,
                    code=code,
                    context={
                        "step_id": step_id,
                        "step_name": step_name,
                        "missing_step_id": missing_dependency,
                        "fix_type": DependencyFixType.CREATE_MISSING_STEP,
                        "dependency_type": DependencyType.AFTER,
                    },
                    priority=3,  # High priority - broken dependencies prevent execution
                )
            )

            # Strategy 2: Remove the dependency
            suggestions.append(
                FixSuggestion(
                    text=(
                        f"Remove the dependency on '{missing_dependency}' from "
                        f"'{step_name}' step if it's not actually needed"
                    ),
                    fix_type=FixType.MODIFY_CONNECTION,
                    code=code,
                    context={
                        "step_id": step_id,
                        "step_name": step_name,
                        "missing_step_id": missing_dependency,
                        "fix_type": DependencyFixType.REMOVE_DEPENDENCY,
                        "dependency_type": DependencyType.AFTER,
                    },
                    priority=2,
                )
            )

            # Strategy 3: Replace with existing step
            existing_steps = self._get_existing_step_suggestions(step_id, plan)
            if existing_steps:
                step_list = ", ".join([f"'{s}'" for s in existing_steps[:3]])
                more_text = (
                    f" and {len(existing_steps) - 3} others" if len(existing_steps) > 3 else ""
                )

                suggestions.append(
                    FixSuggestion(
                        text=(
                            f"Replace the missing dependency '{missing_dependency}' in "
                            f"'{step_name}' with an existing step like "
                            f"{step_list}{more_text}"
                        ),
                        fix_type=FixType.MODIFY_CONNECTION,
                        code=code,
                        context={
                            "step_id": step_id,
                            "step_name": step_name,
                            "missing_step_id": missing_dependency,
                            "fix_type": DependencyFixType.REPLACE_WITH_EXISTING,
                            "dependency_type": DependencyType.AFTER,
                            "suggested_replacements": existing_steps,
                        },
                        priority=1,
                    )
                )

        return suggestions

    def _suggest_missing_branch_fixes(
        self,
        missing_branch_issues: list[dict],
        plan: GraphPlan,
        message_codes: dict[str, MessageCode],
    ) -> list[FixSuggestion]:
        """Suggest fixes for missing branch targets."""
        suggestions = []

        for issue_data in missing_branch_issues:
            step_id = issue_data.get("step_id")
            missing_target = issue_data.get("missing_dependency")

            if not step_id or not missing_target:
                continue

            step = plan.get_step(step_id)
            if not step:
                continue

            step_name = step.meta.display_name if step.meta.display_name else step_id
            code = message_codes.get(step_id, MessageCode.MISSING_BRANCH_TARGET)

            # Find which branch points to the missing target
            branch_name = None
            for branch, target in step.branches.items():
                if target == missing_target:
                    branch_name = branch
                    break

            branch_description = f"'{branch_name}' branch" if branch_name else "branch"

            # Strategy 1: Create the missing target step
            suggestions.append(
                FixSuggestion(
                    text=(
                        f"Create the missing step '{missing_target}' that the "
                        f"{branch_description} from '{step_name}' points to"
                    ),
                    fix_type=FixType.ADD_NODE,
                    code=code,
                    context={
                        "step_id": step_id,
                        "step_name": step_name,
                        "missing_target_id": missing_target,
                        "branch_name": branch_name,
                        "fix_type": DependencyFixType.CREATE_MISSING_TARGET,
                        "dependency_type": DependencyType.BRANCH,
                    },
                    priority=3,  # High priority - broken branches prevent proper flow
                )
            )

            # Strategy 2: Remove the branch
            suggestions.append(
                FixSuggestion(
                    text=(
                        f"Remove the {branch_description} from '{step_name}' step if this "
                        f"outcome is not needed"
                    ),
                    fix_type=FixType.MODIFY_CONNECTION,
                    code=code,
                    context={
                        "step_id": step_id,
                        "step_name": step_name,
                        "missing_target_id": missing_target,
                        "branch_name": branch_name,
                        "fix_type": DependencyFixType.REMOVE_BRANCH,
                        "dependency_type": DependencyType.BRANCH,
                    },
                    priority=2,
                )
            )

            # Strategy 3: Redirect to existing step
            existing_steps = self._get_existing_step_suggestions(step_id, plan)
            if existing_steps:
                step_list = ", ".join([f"'{s}'" for s in existing_steps[:3]])
                more_text = (
                    f" and {len(existing_steps) - 3} others" if len(existing_steps) > 3 else ""
                )

                suggestions.append(
                    FixSuggestion(
                        text=(
                            f"Redirect the {branch_description} from '{step_name}' to an "
                            f"existing step like {step_list}{more_text}"
                        ),
                        fix_type=FixType.MODIFY_CONNECTION,
                        code=code,
                        context={
                            "step_id": step_id,
                            "step_name": step_name,
                            "missing_target_id": missing_target,
                            "branch_name": branch_name,
                            "fix_type": DependencyFixType.REDIRECT_TO_EXISTING,
                            "dependency_type": DependencyType.BRANCH,
                            "suggested_targets": existing_steps,
                        },
                        priority=1,
                    )
                )

        return suggestions

    def _get_existing_step_suggestions(self, current_step_id: str, plan: GraphPlan) -> list[str]:
        """Get suggestions for existing steps that could be used as replacements."""
        # Return other step IDs (excluding the current step)
        existing_steps = []
        for step in plan.steps:
            if step.uid != current_step_id:
                # Use display name if available, otherwise use ID
                name = step.meta.display_name if step.meta.display_name else step.uid
                existing_steps.append(name)

        # Return up to 5 suggestions, sorted
        return sorted(existing_steps)[:5]
