"""Application routing validates portable outcomes before infrastructure sees them."""

import pytest

from lumora.programs.domain.routing import RouteSelectionError, normalize_route_selection


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, "true"),
        (False, "false"),
        ("left", "left"),
        (("left", "right"), ["left", "right"]),
        ([], []),
        ("END", "END"),
    ],
)
def test_portable_conditions_support_symbolic_direct_and_explicit_terminal_outcomes(
    value, expected
):
    assert (
        normalize_route_selection(
            value, {"true": "yes", "false": "no", "left": "a", "right": "b", "END": "finish"}
        )
        == expected
    )


@pytest.mark.parametrize(
    "value", [None, 1, {"route": "left"}, [True], ["left", 3], "private-value", "END"]
)
def test_invalid_or_unknown_condition_outcomes_fail_without_echoing_data(value):
    with pytest.raises(RouteSelectionError) as error:
        normalize_route_selection(value, {"left": "node"})
    assert "private-value" not in str(error.value)
