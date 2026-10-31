from mas.graph.graph_plan import GraphPlan

from ..interfaces import ValidationProvider
from ..models import ValidationReport
from .detector import CycleDetector


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
