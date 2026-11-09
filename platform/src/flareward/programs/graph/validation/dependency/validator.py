from flareward.programs.graph.graph_plan import GraphPlan
from flareward.programs.graph.validation.dependency.checker import DependencyChecker
from flareward.programs.graph.validation.interfaces import ValidationProvider
from flareward.programs.graph.validation.models import ValidationReport


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
