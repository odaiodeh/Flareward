"""Whole-value projections and named mappings share portable, detached JSON semantics."""

import pytest
from pydantic import ValidationError

from flareward.programs.domain.bindings import BindingError, project
from flareward.programs.domain.models import (
    LiteralBinding,
    PathBinding,
    ProgramCallStep,
    ProgramRef,
)


@pytest.mark.parametrize("value", [[1, 2], {"amount": 3}, "text", 4, True, None])
def test_whole_values_and_empty_paths_preserve_json_shape(value):
    assert project(PathBinding(path=()), value) == value
    assert project(LiteralBinding(value=value), {"unused": "source"}) == value
    assert project({"value": PathBinding(path=())}, value) == {"value": value}


def test_selected_values_and_literals_are_detached_from_their_source():
    source = {"nested": {"items": [1]}}
    selected = project(PathBinding(path=("nested",)), source)
    selected["items"].append(2)
    assert source == {"nested": {"items": [1]}}
    literal = LiteralBinding(value={"items": [1]})
    projected = project(literal, None)
    projected["items"].append(2)
    assert literal.value == {"items": [1]}


def test_invalid_dynamic_paths_and_values_have_safe_diagnostics():
    for source in ({"token": "private-input"}, None, ["private-input"]):
        with pytest.raises(BindingError) as failed:
            project(PathBinding(path=("missing",)), source)
        assert "private-input" not in str(failed.value)
    with pytest.raises(BindingError):
        project(PathBinding(path=()), {"number": float("nan")})
    with pytest.raises(ValidationError):
        LiteralBinding(value=float("inf"))


def test_projection_union_does_not_confuse_a_field_named_kind_with_a_whole_value():
    step = ProgramCallStep(
        uid="call",
        program=ProgramRef(program_id="child", revision=1),
        inputs={"kind": LiteralBinding(value="named")},
    )
    restored = ProgramCallStep.model_validate_json(step.model_dump_json())
    assert project(restored.inputs, None) == {"kind": "named"}
    whole = step.model_copy(update={"inputs": PathBinding(path=())})
    restored_whole = ProgramCallStep.model_validate_json(whole.model_dump_json())
    assert project(restored_whole.inputs, [1]) == [1]
