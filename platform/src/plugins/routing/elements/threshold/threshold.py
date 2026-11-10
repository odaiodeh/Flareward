"""Compare a selected numeric output without widening the declared state access."""

import math
import operator

from lumora.elements.condition import BaseCondition
from lumora.elements.domain.conditions import ConditionOutputSchema, boolean_condition_schema
from lumora.programs.graph.state.state_view import StateView
from plugins.routing.elements.threshold.config import ComparisonOperator

COMPARISONS = {
    ComparisonOperator.GREATER: operator.gt,
    ComparisonOperator.LESS: operator.lt,
    ComparisonOperator.GREATER_EQUAL: operator.ge,
    ComparisonOperator.LESS_EQUAL: operator.le,
    ComparisonOperator.EQUAL: operator.eq,
    ComparisonOperator.NOT_EQUAL: operator.ne,
}


class ThresholdCondition(BaseCondition):
    READS = {"output", "nodes_output"}

    def __init__(
        self, input_path: tuple[str, ...], threshold: float, comparison: ComparisonOperator
    ) -> None:
        super().__init__()
        self._path, self._threshold, self._compare = input_path, threshold, COMPARISONS[comparison]

    def run(self, state: StateView) -> bool:
        try:
            value = state[self._path[0]]
            for key in self._path[1:]:
                value = value[key]
        except KeyError, TypeError:
            raise ValueError("Threshold input is unavailable") from None
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError("Threshold input must be a finite number")
        try:
            number = float(value)
        except ValueError, OverflowError:
            raise ValueError("Threshold input must be a finite number") from None
        if not math.isfinite(number):
            raise ValueError("Threshold input must be a finite number")
        return self._compare(number, self._threshold)

    @classmethod
    def get_output_schema(cls) -> ConditionOutputSchema:
        return boolean_condition_schema("Compare a selected output with a finite numeric threshold")
