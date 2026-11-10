from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.validation.cycle.detector import CycleDetector
from lumora.programs.graph.validation.interfaces import ValidationProvider
from lumora.programs.graph.validation.models import ValidationReport


class CycleValidator(ValidationProvider):
    """Validates graph for execution cycles."""

    name = "cycle"

    def __init__(self, *args, **kwargs):
        self._detector = CycleDetector()

    def validate(self, plan: GraphPlan) -> ValidationReport:
        cycles, messages = self._detector.detect_cycles(plan)

        return ValidationReport(
            validator_name=self.name,
            is_valid=len(cycles) == 0,
            messages=messages,
            details={"cycles": [cycle.model_dump() for cycle in cycles]},
        )
