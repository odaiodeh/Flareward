"""Built-in condition schemas/factories agree with actual state access and branch metadata."""

import pytest
from pydantic import ValidationError

from flareward.elements.condition import BaseCondition
from flareward.programs.graph.state.graph_state import GraphState
from plugins.routing.elements.router_boolean.config import RouterBooleanConditionConfig
from plugins.routing.elements.router_boolean.router_condition_factory import (
    RouterBooleanConditionFactory,
)
from plugins.routing.elements.router_direct.config import RouterDirectConditionConfig
from plugins.routing.elements.router_direct.router_condition_factory import (
    RouterDirectConditionFactory,
)
from plugins.routing.elements.threshold.config import ThresholdConditionConfig
from plugins.routing.elements.threshold.spec.spec import ThresholdConditionElementSpec
from plugins.routing.elements.threshold.threshold_factory import ThresholdConditionFactory


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [
        (">", "2", False),
        ("<", "2", False),
        (">=", "2", True),
        ("<=", "2", True),
        ("==", "2.0", True),
        ("!=", "2", False),
    ],
)
def test_numeric_comparison_boundary_and_declared_state_access(operator, value, expected):
    config = ThresholdConditionConfig(input_path=["output"], threshold=2, operator=operator)
    condition = ThresholdConditionFactory().create(config)
    assert isinstance(condition, BaseCondition)
    assert condition(GraphState(output=value)) is expected
    assert (
        ThresholdConditionElementSpec.reads
        == condition.read_channels()
        == {"output", "nodes_output"}
    )


def test_named_node_output_is_selected_without_reading_unrelated_output():
    config = ThresholdConditionConfig(input_path=["nodes_output", "score"], threshold=0.5)
    condition = ThresholdConditionFactory().create(config)
    state = GraphState(output="unrelated-private-output", nodes_output={"score": "0.75"})
    before = state.model_dump_json()
    assert condition(state) is True
    assert state.model_dump_json() == before
    with pytest.raises(ValueError, match="unavailable"):
        condition(GraphState())


@pytest.mark.parametrize("value", ["", "private-nonnumeric", "NaN", "inf", "-inf", "1e9999"])
def test_invalid_runtime_values_fail_instead_of_selecting_a_branch(value):
    config = ThresholdConditionConfig(input_path=["output"], threshold=1)
    with pytest.raises(ValueError, match="finite number") as error:
        ThresholdConditionFactory().create(config)(GraphState(output=value))
    assert "private-nonnumeric" not in str(error.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"input_path": []},
        {"input_path": ["nodes_output"]},
        {"input_path": ["nodes_output", ""]},
        {"input_path": ["messages"]},
        {"input_path": ["output"], "input_key": "output"},
        {"threshold": float("nan")},
        {"threshold": float("inf")},
        {"operator": "eval"},
    ],
)
def test_invalid_selection_and_nonfinite_thresholds_are_rejected_by_the_schema(changes):
    with pytest.raises(ValidationError):
        ThresholdConditionConfig.model_validate(
            {"input_path": ["output"], "threshold": 1, **changes}
        )


def test_legacy_key_is_normalized_without_mutating_authored_configuration():
    data = {"input_key": "output", "threshold": 1, "operator": ">"}
    config = ThresholdConditionConfig.model_validate(data)
    assert config.input_path == ("output",)
    assert "input_key" not in config.model_dump()
    assert data["input_key"] == "output" and "input_path" not in data
    assert ThresholdConditionFactory().create(config)(GraphState(output="2")) is True
    with pytest.raises(ValidationError):
        ThresholdConditionConfig.model_validate({"input_key": "missing", "threshold": 1})


def test_boolean_and_direct_factories_honor_the_shared_contract():
    boolean = RouterBooleanConditionFactory().create(
        RouterBooleanConditionConfig(boolean_value=False)
    )
    direct = RouterDirectConditionFactory().create(RouterDirectConditionConfig())
    assert isinstance(boolean, BaseCondition) and isinstance(direct, BaseCondition)
    assert boolean(GraphState()) == "false"
    assert [item.name for item in boolean.get_output_schema().symbolic_branches] == [True, False]
    with pytest.raises(RuntimeError, match="step context"):
        direct(GraphState())
