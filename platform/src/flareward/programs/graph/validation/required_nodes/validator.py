from flareward.programs.graph.graph_plan import GraphPlan
from flareward.programs.graph.validation.interfaces import ValidationProvider
from flareward.programs.graph.validation.models import ValidationReport
from flareward.programs.graph.validation.required_nodes.checker import RequiredNodesChecker
from flareward.programs.graph.validation.settings import ValidationSettings


class RequiredNodesValidator(ValidationProvider):
    """Validates that required node types are present and counts are within limits."""

    name = "required_nodes"

    def __init__(self, settings: ValidationSettings = None, *args, **kwargs):
        settings = settings or ValidationSettings()
        self._checker = RequiredNodesChecker(
            required_start_nodes=settings.required_start_nodes,
            required_end_nodes=settings.required_end_nodes,
            required_any_nodes=settings.required_any_nodes,
            max_start_nodes=settings.max_start_nodes,
            max_end_nodes=settings.max_end_nodes,
            max_any_nodes=settings.max_any_nodes,
        )

    def validate(self, plan: GraphPlan) -> ValidationReport:
        issues, messages = self._checker.check_required_nodes(plan)

        return ValidationReport(
            validator_name=self.name,
            is_valid=len(issues) == 0,
            messages=messages,
            details={"required_node_issues": [issue.model_dump() for issue in issues]},
        )
