"""Application-owned graph channels, portable updates and safe state-contract failures."""

from collections.abc import Callable, Mapping
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ModelWrapValidatorHandler,
    ValidationError,
    model_validator,
)

from flareward.json_values import portable_json
from flareward.programs.domain.models import GraphDefinition


class StateContractError(Exception):
    """State validation diagnostics never contain supplied channel values."""


def merge_values(old: dict[str, JsonValue], new: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {**old, **new}


def replace_value(old: JsonValue, new: JsonValue) -> JsonValue:
    return new


class ProgramState(BaseModel):
    """Portable data channels; conversation and agent channels are opt-in adapters."""

    model_config = ConfigDict(extra="forbid")
    input: JsonValue = Field(default=None, frozen=True)
    results: Annotated[dict[str, JsonValue], merge_values] = Field(default_factory=dict)
    values: Annotated[dict[str, JsonValue], merge_values] = Field(default_factory=dict)
    output: Annotated[JsonValue, replace_value] = None

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> Self:
        return cls.model_validate(data)

    @classmethod
    def get_merge_strategies(cls) -> dict[str, Callable[..., Any]]:
        return {
            name: reducer
            for name, field in cls.model_fields.items()
            for reducer in field.metadata
            if callable(reducer)
        }

    @model_validator(mode="wrap")
    @classmethod
    def valid_channels(cls, value: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        try:
            return handler(value)
        except ValidationError:
            raise StateContractError("Graph state violates its channel contracts") from None

    @classmethod
    def writable_schema(cls) -> dict[str, JsonValue]:
        schema = cls.model_json_schema(mode="serialization", by_alias=False)
        for channel in GraphDefinition.READ_ONLY_CHANNELS:
            schema["properties"][channel] = False
        return schema

    def serialize(self) -> dict[str, JsonValue]:
        try:
            result = portable_json(self.model_dump(mode="json", warnings="error"))
        except ValueError, TypeError:
            raise StateContractError("Graph state must contain portable channel values") from None
        assert isinstance(result, dict)
        return result

    @classmethod
    def _writable(cls, updates: Mapping[str, object]) -> None:
        if updates.keys() & GraphDefinition.READ_ONLY_CHANNELS:
            raise StateContractError("Graph input and result scopes are read-only")
        if updates.keys() - cls.model_fields.keys():
            raise StateContractError("Graph output targets unknown state channels")

    def with_updates(self, updates: dict[str, Any]) -> Self:
        self._writable(updates)
        return type(self).model_validate({**self.serialize(), **updates})

    def record_result(self, key: str, result: JsonValue, updates: dict[str, JsonValue]) -> Self:
        self._writable(updates)
        return type(self).model_validate(
            {
                **self.serialize(),
                **updates,
                "results": {**self.results, key: result},
            }
        )
