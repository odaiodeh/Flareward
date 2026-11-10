"""Explicit finite numeric selection; normalize the retained top-level key format."""

from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from lumora.elements.condition_config import BaseConditionConfig
from lumora.elements.hints import CardContext, CardHint
from plugins.routing.elements.threshold.identifiers import Identifier


class ComparisonOperator(StrEnum):
    GREATER = ">"
    LESS = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="


class ThresholdConditionConfig(BaseConditionConfig):
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    input_path: tuple[str, ...] = Field(
        min_length=1,
        max_length=2,
        description="Select ['output'] or ['nodes_output', '<node uid>']",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    threshold: float = Field(
        allow_inf_nan=False,
        description="Finite numeric cutoff",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    operator: ComparisonOperator = Field(
        default=ComparisonOperator.GREATER,
        description="Numeric comparison operator",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_input_key(cls, value: object) -> object:
        if not isinstance(value, dict) or "input_key" not in value:
            return value
        if "input_path" in value:
            raise ValueError("Select input_path or legacy input_key, not both")
        key = value["input_key"]
        if not isinstance(key, str):
            raise ValueError("Legacy input_key must be a state channel name")
        return {
            **{name: item for name, item in value.items() if name != "input_key"},
            "input_path": [key],
        }

    @field_validator("input_path")
    @classmethod
    def numeric_selection(cls, path: tuple[str, ...]) -> tuple[str, ...]:
        if path == ("output",) or (len(path) == 2 and path[0] == "nodes_output" and path[1]):
            return path
        raise ValueError("Threshold input_path must select output or a named nodes_output entry")
