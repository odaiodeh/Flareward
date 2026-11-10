from collections.abc import Callable, Iterator
from enum import StrEnum
from typing import Annotated, Any, Self, get_type_hints

from pydantic import BaseModel, ConfigDict, Field

from lumora.elements.messaging.domain.messages import ChatMessage
from lumora.elements.messaging.protocol.packets import IEMPacket
from lumora.programs.graph.state.merge_strategies import (
    append_chat_messages,
    append_iem_packets,
    merge_string_dicts,
    merge_task_threads,
    merge_threads,
    merge_workspaces,
)


class GraphState(BaseModel):
    """
    Application state for graph-based node adapters.

    • Declares your main channels with merge-strategies via Annotated
    • Behaves like a dict: __getitem__, __setitem__, keys(), items(), etc.
    • Execution adapters specialize the state for their runtime
    • Raises KeyError for non-existent keys (like standard dict)
    """

    model_config = ConfigDict(
        extra="ignore",
        arbitrary_types_allowed=True,
    )

    # —————– Channels (with merge strategies) —————–

    user_prompt: Annotated[str, lambda old, new: new] = Field(
        default="", json_schema_extra={"external": True, "streamable": True}
    )

    nodes_output: Annotated[dict[str, str], merge_string_dicts] = Field(
        default_factory=dict, json_schema_extra={"streamable": False}
    )

    messages: Annotated[list[ChatMessage], append_chat_messages] = Field(
        default_factory=list, json_schema_extra={"streamable": True}
    )

    output: Annotated[str, lambda old, new: new] = Field(
        default="", json_schema_extra={"streamable": True}
    )

    target_branch: Annotated[str, lambda old, new: new] = Field(
        default="", json_schema_extra={"streamable": False}
    )

    # —————– STRUCTURED COMMUNICATION (Inter-Node Coordination) —————–

    inter_packets: Annotated[list[IEMPacket], append_iem_packets] = Field(
        default_factory=list, json_schema_extra={"streamable": False}
    )

    # —————– PRIVATE WORKSPACE (Node Internal State) —————–

    task_threads: Annotated[dict[str, list[ChatMessage]], merge_task_threads] = Field(
        default_factory=dict, json_schema_extra={"streamable": False}
    )

    # —————– AGENTIC WORKLOAD MANAGEMENT —————–

    threads: Annotated[dict[str, Any], merge_threads] = Field(
        default_factory=dict, json_schema_extra={"streamable": False}
    )

    workspaces: Annotated[dict[str, Any], merge_workspaces] = Field(
        default_factory=dict, json_schema_extra={"streamable": False}
    )

    # —————– Dict-like API —————–

    def __getitem__(self, key: str) -> Any:
        if key in self.__class__.model_fields:
            return getattr(self, key)
        raise KeyError(f"{key!r} not found in state.")

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.__class__.model_fields:
            setattr(self, key, value)

    def __delitem__(self, key: str) -> None:
        if key in self.__class__.model_fields:
            delattr(self, key)
        else:
            raise KeyError(f"{key!r} not found in state.")

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.__class__.model_fields:
            return getattr(self, key)
        return default

    def update(self, data: dict[str, Any]) -> None:
        for k, v in data.items():
            self[k] = v

    def keys(self) -> Iterator[str]:
        return iter(self.__class__.model_fields.keys())

    @classmethod
    def get_external_channels(cls) -> set[str]:
        return set(
            [
                field_name
                for field_name, field_info in cls.model_fields.items()
                if isinstance(field_info.json_schema_extra, dict)
                and field_info.json_schema_extra.get("external", False)
            ]
        )

    def items(self) -> Iterator[tuple[str, Any]]:
        for k in self.__class__.model_fields:
            yield k, getattr(self, k)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.model_dump()})"

    @classmethod
    def get_streamable_channels(cls) -> set[str]:
        """
        Returns names of all fields marked as streamable.
        Only these fields will be included in stream payloads.

        Returns:
            Set of field names that have streamable=True in json_schema_extra
        """
        streamable = set()
        for field_name, field_info in cls.model_fields.items():
            if isinstance(field_info.json_schema_extra, dict):
                is_streamable = field_info.json_schema_extra.get("streamable", False)
                if is_streamable:
                    streamable.add(field_name)
        return streamable

    def get_streamable_state(self) -> dict[str, Any]:
        """
        Returns a filtered dict containing only streamable fields.
        This is what gets sent over the wire during streaming to reduce payload size.

        Returns:
            Dictionary with only streamable fields and their values
        """
        streamable = self.get_streamable_channels()
        result = {}

        # Include streamable declared fields
        for field_name in streamable:
            if field_name in self.__class__.model_fields:
                result[field_name] = getattr(self, field_name)

        return result

    # —————– Merge Strategy Introspection —————–

    @classmethod
    def get_merge_strategies(cls) -> dict[str, Callable[[Any, Any], Any]]:
        """
        Extract the merge function from each Annotated channel field.

        Returns:
            { field_name: merge_callable } for every channel
            that declares a merge strategy via Annotated[Type, fn].
        """
        strategies: dict[str, Callable[[Any, Any], Any]] = {}
        hints = get_type_hints(cls, include_extras=True)
        for field_name in cls.model_fields:
            hint = hints.get(field_name)
            if hint and hasattr(hint, "__metadata__"):
                for meta in hint.__metadata__:
                    if callable(meta):
                        strategies[field_name] = meta
                        break
        return strategies

    # —————– Serialization Boundary —————–

    def serialize(self) -> dict[str, Any]:
        """Convert to a JSON-safe dict for cross-process transport."""
        return self.model_dump(mode="json")

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> Self:
        """
        Reconstruct a GraphState from a serialized dict.

        All fields are properly typed — Pydantic handles reconstruction
        automatically via model_validate, including polymorphic IEM packets
        (discriminated union on the 'type' field).
        """
        return cls.model_validate(data)


class Channel(StrEnum):
    """Closed names of the base graph channels; Program-defined channels use strings."""

    USER_PROMPT = "user_prompt"
    NODES_OUTPUT = "nodes_output"
    MESSAGES = "messages"
    OUTPUT = "output"
    TARGET_BRANCH = "target_branch"
    INTER_PACKETS = "inter_packets"
    TASK_THREADS = "task_threads"
    THREADS = "threads"
    WORKSPACES = "workspaces"
