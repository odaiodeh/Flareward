from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any

from mas.core.tracing.models import ObservationHandle


class TracingService(ABC):
    """Domain-level tracing port.

    All observability instrumentation depends on this abstract class,
    never on a concrete SDK.  When tracing is disabled the
    composition root injects NoOpTracingService.
    """

    @property
    @abstractmethod
    def enabled(self) -> bool: ...

    @abstractmethod
    def trace_session(
        self,
        session_id: str,
        user_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[ObservationHandle]: ...

    @abstractmethod
    def trace_node(
        self,
        node_uid: str,
        node_type: str,
        display_name: str = "",
    ) -> AbstractContextManager[ObservationHandle]: ...

    @abstractmethod
    def trace_llm(
        self,
        model: str,
        provider: str,
        input_messages: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[ObservationHandle]: ...

    @abstractmethod
    def trace_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any] | None = None,
    ) -> AbstractContextManager[ObservationHandle]: ...

    @abstractmethod
    def trace_agent_iteration(
        self,
        iteration: int,
        strategy: str = "",
    ) -> AbstractContextManager[ObservationHandle]: ...

    @abstractmethod
    def flush(self) -> None: ...

    def get_session_cost(self, session_id: str) -> float | None:
        """Fetch the total USD cost for a session from the tracing backend.

        Returns a float (>= 0) when the session exists in the tracing
        backend, or None when it does not.  Non-abstract so existing
        subclasses aren't forced to implement it.
        """
        return None
