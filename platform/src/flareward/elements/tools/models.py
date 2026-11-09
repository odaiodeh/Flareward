"""Models for tool execution requests and responses."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ExecutionMode(Enum):
    """Execution modes for tool execution."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONCURRENT_LIMITED = "concurrent_limited"
    BATCHED = "batched"
    PRIORITY = "priority"


@dataclass
class ToolExecutionRequest:
    """A request to execute a tool with all necessary data."""

    tool_name: str
    tool_call_id: str
    args: dict[str, Any]
    context: dict[str, Any] | None = None
    timeout: float | None = None

    def __str__(self) -> str:
        return f"ToolExecutionRequest({self.tool_name}, id={self.tool_call_id})"


@dataclass
class ToolExecutionResponse:
    """Response from tool execution with the original request ID for mapping."""

    tool_call_id: str  # Maps back to the original request
    tool_name: str
    success: bool
    result: Any | None = None
    error: Exception | None = None
    execution_time: float = 0.0
    timestamp: datetime = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(UTC)
        if self.metadata is None:
            self.metadata = {}

    @property
    def has_error(self) -> bool:
        """Check if execution had an error."""
        return self.error is not None or not self.success

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"ToolExecutionResponse({self.tool_name}, id={self.tool_call_id}, {status})"


@dataclass
class BatchToolExecutionResponse:
    """Response from batch tool execution."""

    responses: dict[str, ToolExecutionResponse]  # Keyed by tool_call_id
    total_time: float
    execution_mode: str
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def get_response(self, tool_call_id: str) -> ToolExecutionResponse | None:
        """Get response for a specific tool call ID."""
        return self.responses.get(tool_call_id)

    def get_ordered_responses(self, tool_call_ids: list[str]) -> list[ToolExecutionResponse]:
        """Get responses in the order of the provided tool call IDs."""
        return [
            self.responses.get(call_id) for call_id in tool_call_ids if call_id in self.responses
        ]

    @property
    def all_successful(self) -> bool:
        """Check if all executions were successful."""
        return all(response.success for response in self.responses.values())

    @property
    def success_count(self) -> int:
        """Count of successful executions."""
        return sum(1 for response in self.responses.values() if response.success)

    @property
    def failed_count(self) -> int:
        """Count of failed executions."""
        return sum(1 for response in self.responses.values() if not response.success)

    def __str__(self) -> str:
        return (
            f"BatchToolExecutionResponse({len(self.responses)} tools, "
            f"{self.success_count} success, {self.failed_count} failed, "
            f"{self.total_time:.3f}s, {self.execution_mode})"
        )


# Monitoring and Status Models


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


@dataclass
class CircuitBreakerStatus:
    """Circuit breaker status for a specific tool."""

    tool_name: str
    state: CircuitBreakerState
    failure_count: int
    can_execute: bool
    last_failure_time: float | None = None
    last_success_time: float | None = None
    half_open_calls: int = 0

    @property
    def is_healthy(self) -> bool:
        """Check if the circuit breaker is in a healthy state."""
        return self.state == CircuitBreakerState.CLOSED

    def __str__(self) -> str:
        return (
            f"CircuitBreakerStatus({self.tool_name}, {self.state.value}, "
            f"failures={self.failure_count})"
        )


@dataclass
class ExecutorMetrics:
    """Comprehensive metrics for the executor."""

    total_executions: int
    total_errors: int
    success_rate: float
    error_rate: float
    tools_registered: int
    tool_names: list[str]
    features: dict[str, Any]
    strategies: dict[str, str]

    @property
    def is_healthy(self) -> bool:
        """Check if the executor is in a healthy state."""
        return self.error_rate < 50.0  # Configurable threshold

    def __str__(self) -> str:
        return (
            f"ExecutorMetrics({self.total_executions} executions, "
            f"{self.success_rate:.1f}% success, {self.tools_registered} tools)"
        )


@dataclass
class ExecutorHealth:
    """Health status of the executor."""

    status: str
    strategies_loaded: int
    tools_registered: int
    max_concurrent: int
    metrics_enabled: bool
    features_enabled: dict[str, bool]
    uptime: float | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if the executor is healthy."""
        return self.status == "healthy"

    def __str__(self) -> str:
        return (
            f"ExecutorHealth({self.status}, {self.tools_registered} tools, "
            f"{self.strategies_loaded} strategies)"
        )


@dataclass
class CircuitBreakerReport:
    """Circuit breaker status report for all tools."""

    enabled: bool
    tool_statuses: dict[str, CircuitBreakerStatus]

    @property
    def healthy_tools(self) -> list[str]:
        """Get list of tools with healthy circuit breakers."""
        return [name for name, status in self.tool_statuses.items() if status.is_healthy]

    @property
    def unhealthy_tools(self) -> list[str]:
        """Get list of tools with unhealthy circuit breakers."""
        return [name for name, status in self.tool_statuses.items() if not status.is_healthy]

    @property
    def overall_health(self) -> str:
        """Get overall health assessment."""
        if not self.enabled:
            return "disabled"

        total_tools = len(self.tool_statuses)
        healthy_count = len(self.healthy_tools)

        if healthy_count == total_tools:
            return "healthy"
        elif healthy_count >= total_tools * 0.7:  # 70% threshold
            return "degraded"
        else:
            return "unhealthy"

    def __str__(self) -> str:
        if not self.enabled:
            return "CircuitBreakerReport(disabled)"

        return (
            f"CircuitBreakerReport({len(self.healthy_tools)}/{len(self.tool_statuses)} healthy, "
            f"overall: {self.overall_health})"
        )
