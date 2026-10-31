"""Common models for workload operations."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """Result from agent processing."""

    content: str = Field(..., description="Main result content")
    agent_id: str = Field(..., description="ID of the agent that produced this result")
    agent_name: str = Field(..., description="Name of the agent")
    artifacts: list[str] = Field(
        default_factory=list, description="List of artifact paths/names produced"
    )
    metrics: dict[str, Any] = Field(default_factory=dict, description="Performance metrics")
    success: bool = Field(default=True, description="Whether the agent task succeeded")
    error: str | None = Field(default=None, description="Error message if failed")
    reasoning: str = Field(default="", description="Agent's reasoning process")
    execution_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Execution metadata"
    )


class ArtifactRef(BaseModel):
    """Reference to an artifact with metadata."""

    name: str
    type: str
    location: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
