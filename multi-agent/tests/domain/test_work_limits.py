"""Work policy is finite, strict portable domain data rather than backend capacity."""

import pytest
from mas.domain.execution.budgets import WorkLimits
from pydantic import ValidationError


@pytest.mark.parametrize("field", ["max_dispatches", "max_children", "max_depth"])
@pytest.mark.parametrize("value", [-1, True, 1.5, "2", 100_001])
def test_work_limits_reject_invalid_or_unbounded_allowances(field, value):
    with pytest.raises(ValidationError):
        WorkLimits.model_validate({field: value})
