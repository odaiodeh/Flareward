from mas.graph.graph_plan import GraphPlan

from ..interfaces import ValidationProvider
from ..models import ValidationReport
from .checker import DependencyChecker


class DependencyValidator(ValidationProvider):
    """Validates step dependencies and branch targets."""

    name = "dependency"

    def __init__(self, *args, **kwargs):
        self._checker = DependencyChecker()

    def validate(self, plan: GraphPlan) -> ValidationReport:
        issues, messages = self._checker.check_dependencies(plan)

        return ValidationReport(
            validator_name=self.name,
            is_valid=len(issues) == 0,
            messages=messages,
            details={"dependency_issues": [issue.model_dump() for issue in issues]},
        )
