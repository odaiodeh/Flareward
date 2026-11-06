from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from typing import Any, Protocol, runtime_checkable

from mas.core.channels import SessionChannel
from mas.core.enums import ResourceCategory
from mas.core.hitl.models import ToolApprovalPolicy
from mas.core.hitl.ports import ApprovalGate

# ── Existing protocols ────────────────────────────────────────


@runtime_checkable
class SupportsStreaming(Protocol):
    def _stream(self, payload: Mapping[str, Any]) -> None: ...

    def is_streaming(self) -> bool: ...


class LLMSupportsStreaming(ABC):
    @abstractmethod
    def stream(self, messages: list[Any], **kwargs) -> Iterator[str]: ...


class ElementInstances(Protocol):
    def register(
        self, category: ResourceCategory, rid: str, instance: Any, spec: Any, resource_spec: Any
    ) -> None: ...

    def get(self, category: ResourceCategory, rid: str) -> Any: ...

    def get_instance(self, category: ResourceCategory, rid: str) -> Any: ...

    def get_config(self, category: ResourceCategory, rid: str) -> Any: ...

    def get_spec(self, category: ResourceCategory, rid: str) -> Any: ...

    def get_runtime_element(self, category: ResourceCategory, rid: str) -> Any: ...


# ── Capability protocols (Node Capability Binding System) ─────
#
# Shared vocabulary used by all binding phases to ask "can this
# node receive X?".  Each protocol is narrow (ISP) and
# runtime-checkable so that isinstance() replaces hasattr().


@runtime_checkable
class SupportsStreamingChannel(Protocol):
    """Runtime capability: node can emit events through a session channel."""

    def set_streaming_channel(self, channel: SessionChannel | None) -> None: ...


@runtime_checkable
class SupportsHITL(Protocol):
    """Runtime capability: node can gate tool execution through human approval."""

    def set_approval_gate(self, gate: ApprovalGate | None) -> None: ...
    def set_approval_policy(self, policy: ToolApprovalPolicy | None) -> None: ...
