"""
Essential Payloads for IEM Protocol

Defines core Pydantic models for common communication patterns.
Keep only the payloads that are actually used in the system.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TaskPayload(BaseModel):
    """
    Universal task payload for agent communication.

    This is the primary payload used throughout the system for
    passing results, artifacts, and metadata between nodes.
    """

    result: str
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)


class ProcessingPayload(BaseModel):
    """
    Simple payload for processing events.

    Used for basic communication when starting processing
    or passing simple data between nodes.
    """

    data: Dict[str, Any] = Field(default_factory=dict)
    thread_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ErrorPayload(BaseModel):
    """
    Standardized error payload.

    Used for communicating errors in a structured way
    across the IEM protocol.
    """

    error_code: str
    error_message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    retry_possible: bool = False
