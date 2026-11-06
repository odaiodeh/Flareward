"""Application-owned graph channels, portable updates and safe state-contract failures."""

from collections.abc import Mapping, Set
from typing import Annotated, Any, Self

from pydantic import (
    ConfigDict,
    Field,
    JsonValue,
    ModelWrapValidatorHandler,
    ValidationError,
    model_validator,
)

from mas.domain.json_values import portable_json
from mas.domain.programs.models import GraphDefinition
from mas.graph.state.graph_state import GraphState


class StateContractError(Exception):
    """State validation diagnostics never contain supplied channel values."""


def merge_values(old: dict[str, JsonValue], new: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {**old, **new}


class ProgramState(GraphState):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    input: JsonValue = Field(default=None, frozen=True)
    results: Annotated[dict[str, JsonValue], merge_values] = Field(default_factory=dict)
    values: Annotated[dict[str, JsonValue], merge_values] = Field(default_factory=dict)

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

    def accept_node(self, result: GraphState, *, writes: Set[str]) -> Self:
        original = self.serialize()
        try:
            returned = result.serialize()
        except ValueError, TypeError:
            raise StateContractError("Node state must contain portable channel values") from None
        changed = {
            name
            for name, value in returned.items()
            if name not in original or value != original[name]
        }
        self._writable({name: returned[name] for name in changed})
        if changed - writes:
            raise StateContractError("Node returned changes outside its declared write contract")
        return type(self).model_validate({**original, **returned})
