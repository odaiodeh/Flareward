"""Typed agent parsing failures and recovery choices."""

from enum import Enum
from typing import Any


class ParseErrorType(Enum):
    """Types of parsing errors that can occur."""

    INVALID_FORMAT = "invalid_format"
    MISSING_CONTENT = "missing_content"
    INVALID_ROLE = "invalid_role"
    MALFORMED_STRUCTURE = "malformed_structure"
    TOOL_CALL_ERROR = "tool_call_error"
    JSON_ERROR = "json_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_FORMAT = "unknown_format"


class RecoveryStrategy(Enum):
    """Strategies for recovering from parse errors."""

    REFLECTION = "reflection"  # Create reflection action
    ERROR_ACTION = "error_action"  # Create error-handling action
    IGNORE = "ignore"  # Skip the error
    FAIL_FAST = "fail_fast"


class ParseError(Exception):
    """Structured parsing error with recovery information."""

    def __init__(
        self,
        message: str,
        error_type: ParseErrorType,
        raw_output: str,
        recoverable: bool = True,
        recovery_strategy: RecoveryStrategy = RecoveryStrategy.REFLECTION,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.raw_output = raw_output
        self.recoverable = recoverable
        self.recovery_strategy = recovery_strategy
        self.context = context or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "message": str(self),
            "error_type": self.error_type.value,
            "raw_output": self.raw_output,
            "recoverable": self.recoverable,
            "recovery_strategy": self.recovery_strategy.value,
            "context": self.context,
        }
