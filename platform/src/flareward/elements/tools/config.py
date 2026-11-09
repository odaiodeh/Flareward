"""Runtime tool-executor configuration with explicitly borrowed collaborators."""

from dataclasses import dataclass, fields
from typing import Any

from flareward.elements.tools.interfaces import ErrorHandler, ExecutionValidator
from flareward.elements.tools.models import ExecutionMode
from flareward.elements.tools.policies import RetryPolicy
from flareward.elements.tools.validators import ArgumentValidator


@dataclass
class ExecutorConfig:
    """Configuration model for ToolExecutorManager."""

    # Core execution settings
    max_concurrent: int = 30
    execution_mode: ExecutionMode = ExecutionMode.PARALLEL
    default_timeout: float | None = None
    enable_metrics: bool = True

    # Error handling
    error_handler: ErrorHandler | None = None

    # Validation
    validators: list[ExecutionValidator] | None = None

    # Circuit breaker
    enable_circuit_breaker: bool = False

    @classmethod
    def create_default(cls) -> ExecutorConfig:
        """Create a default configuration with production-ready settings."""

        return cls(
            max_concurrent=30,
            execution_mode=ExecutionMode.PARALLEL,
            enable_metrics=True,
            error_handler=RetryPolicy(max_retries=2, initial_delay=0.5),
            validators=[ArgumentValidator(strict=True)],
            enable_circuit_breaker=False,
        )

    @classmethod
    def create_balanced(cls) -> ExecutorConfig:
        """Create a balanced configuration with high performance and reliability."""

        return cls(
            max_concurrent=30,
            execution_mode=ExecutionMode.PARALLEL,
            enable_metrics=True,
            error_handler=RetryPolicy(max_retries=2, initial_delay=0.5),
            validators=[ArgumentValidator(strict=True)],
            enable_circuit_breaker=True,
        )

    @classmethod
    def create_robust(cls) -> ExecutorConfig:
        """Create a robust configuration with circuit breaker and enhanced error handling."""

        return cls(
            max_concurrent=5,  # More conservative for robust mode
            execution_mode=ExecutionMode.CONCURRENT_LIMITED,
            enable_metrics=True,
            error_handler=RetryPolicy(max_retries=3, initial_delay=0.5, exponential_base=2.0),
            validators=[ArgumentValidator(strict=True)],
            enable_circuit_breaker=True,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for ToolExecutorManager constructor."""
        arguments = {
            field.name: value
            for field in fields(self)
            if (value := getattr(self, field.name)) is not None
        }
        if self.validators is not None:
            arguments["validators"] = self.validators.copy()
        return arguments
