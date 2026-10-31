"""Protocol interfaces for the tool execution framework."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from mas.application.ports.tool import BaseTool
from mas.application.tools.models import ExecutionMode, ToolExecutionRequest, ToolExecutionResponse


@runtime_checkable
class ToolExecutor(Protocol):
    """Protocol for tool executors."""

    async def execute_requests_async(
        self, requests: list[ToolExecutionRequest], mode: ExecutionMode = ExecutionMode.PARALLEL
    ) -> Any:
        """Execute tool requests."""
        ...

    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to the executor."""
        ...

    def remove_tool(self, tool_name: str) -> bool:
        """Remove a tool from the executor."""
        ...


@runtime_checkable
class ErrorHandler(Protocol):
    """Protocol for error handling policies."""

    async def handle_error(
        self,
        error: Exception,
        tool: BaseTool,
        args: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Any:
        """Handle execution error."""
        ...


@runtime_checkable
class ExecutionValidator(Protocol):
    """Protocol for pre-execution validation."""

    async def validate(
        self, tool: BaseTool, args: dict[str, Any], context: dict[str, Any] | None = None
    ) -> tuple[bool, str | None]:
        """Validate before execution."""
        ...


@runtime_checkable
class ExecutionHook(Protocol):
    """Protocol for execution hooks."""

    async def __call__(self, *args, **kwargs) -> None:
        """Execute the hook."""
        ...


class ExecutionStrategy(ABC):
    """Base class for execution strategies."""

    @abstractmethod
    async def execute_requests(
        self,
        requests: list[ToolExecutionRequest],
        executor_func: Callable[[ToolExecutionRequest], Awaitable[ToolExecutionResponse]],
    ) -> list[ToolExecutionResponse]:
        """Execute tool requests using the strategy."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name for logging."""
        pass


@runtime_checkable
class StreamingHandler(Protocol):
    """Protocol for streaming execution events."""

    async def on_tool_start(self, tool_name: str, args: dict[str, Any], tool_call_id: str) -> None:
        """Called when tool execution starts."""
        ...

    async def on_tool_complete(
        self, tool_name: str, result: Any, tool_call_id: str, execution_time: float
    ) -> None:
        """Called when tool execution completes successfully."""
        ...

    async def on_tool_error(
        self, tool_name: str, error: Exception, tool_call_id: str, execution_time: float
    ) -> None:
        """Called when tool execution fails."""
        ...


@runtime_checkable
class CircuitBreaker(Protocol):
    """Protocol for circuit breaker implementations."""

    def can_execute(self, tool_name: str) -> bool:
        """Check if tool can be executed."""
        ...

    def record_success(self, tool_name: str) -> None:
        """Record successful execution."""
        ...

    def record_failure(self, tool_name: str) -> None:
        """Record failed execution."""
        ...

    def get_tool_status(self, tool_name: str) -> dict[str, Any]:
        """Get status for a specific tool."""
        ...


@runtime_checkable
class MetricsCollector(Protocol):
    """Protocol for metrics collection."""

    def record_execution(
        self, tool_name: str, execution_time: float, success: bool, error: Exception | None = None
    ) -> None:
        """Record tool execution metrics."""
        ...

    def get_metrics(self) -> dict[str, Any]:
        """Get collected metrics."""
        ...

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        ...


# Type aliases for commonly used types
ExecutorFunction = Any  # Callable that executes a single request
HookFunction = Any  # Callable for pre/post execution hooks
