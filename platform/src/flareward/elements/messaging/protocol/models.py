"""
Core IEM Protocol Models

Clean, minimal models for packet types and addressing.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class PacketType(str, Enum):
    """Packet types - each type knows its own structure."""

    TASK = "task"
    SYSTEM = "system"
    DEBUG = "debug"


class ErrorCode(str, Enum):
    """Standard IEM error codes."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ADJACENCY_ERROR = "ADJACENCY_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"


# Remove StandardActions and StandardEvents as they're not needed in the clean design
# Nodes use natural language and LLM intelligence instead


class ElementAddress(BaseModel):
    """Address for an element in the graph."""

    uid: str

    def __str__(self) -> str:
        return self.uid

    def __eq__(self, other) -> bool:
        if isinstance(other, ElementAddress):
            return self.uid == other.uid
        elif isinstance(other, str):
            return self.uid == other
        return False


class IEMError(BaseModel):
    """Structured error for IEM communications."""

    code: ErrorCode
    message: str
    details: Optional[dict[str, Any]] = None

    @classmethod
    def from_exception(
        cls, exc: Exception, code: ErrorCode = ErrorCode.INTERNAL_ERROR
    ) -> "IEMError":
        """Create IEMError from Python exception."""
        return cls(code=code, message=str(exc), details={"exception_type": type(exc).__name__})

    @classmethod
    def validation_error(cls, message: str, details: dict = None) -> "IEMError":
        """Create validation error."""
        return cls(code=ErrorCode.VALIDATION_ERROR, message=message, details=details)

    @classmethod
    def protocol_error(cls, message: str, details: dict = None) -> "IEMError":
        """Create protocol error."""
        return cls(code=ErrorCode.PROTOCOL_ERROR, message=message, details=details)
