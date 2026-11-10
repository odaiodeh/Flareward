"""Workspace context models for shared data management."""

from typing import Any

from pydantic import BaseModel, Field

from lumora.elements.messaging.domain.messages import ChatMessage
from lumora.elements.workloads.domain.models import AgentResult, WorkspaceArtifact
from lumora.elements.workloads.domain.task import Task


class WorkspaceContext(BaseModel):
    """Workspace context data model."""

    # Shared Context Data
    facts: list[str] = Field(default_factory=list)
    results: list[AgentResult] = Field(default_factory=list)
    artifacts: dict[str, WorkspaceArtifact] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    conversation_history: list[ChatMessage] = Field(default_factory=list)

    # Task storage for response tracking
    tasks: list[Task] = Field(default_factory=list, description="Processed tasks for this thread")

    # Work Plans storage - dedicated field for clean separation
    work_plans: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Work plans by owner_uid. Each value is a serialized WorkPlan.",
    )
