from flareward.programs.graph.graph_plan import GraphPlan
from flareward.programs.graph.validation.interfaces import ValidationProvider
from flareward.programs.graph.validation.models import ValidationReport
from flareward.programs.graph.validation.orphan.detector import OrphanDetector


class OrphanValidator(ValidationProvider):
    """Validates graph for orphaned steps."""

    name = "orphan"

    def __init__(self, *args, **kwargs):
        self._detector = OrphanDetector()

    def validate(self, plan: GraphPlan) -> ValidationReport:
        orphaned_steps, messages = self._detector.detect_orphans(plan)

        return ValidationReport(
            validator_name=self.name,
            is_valid=len(orphaned_steps) == 0,
            messages=messages,
            details={"orphaned_steps": list(orphaned_steps)},
        )
