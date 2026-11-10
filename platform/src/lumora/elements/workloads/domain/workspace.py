"""Workspace model for shared context and collaboration."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from lumora.elements.messaging.domain.messages import ChatMessage
from lumora.elements.workloads.domain.context import WorkspaceContext
from lumora.elements.workloads.domain.models import AgentResult, WorkspaceArtifact


class Workspace(BaseModel):
    """Workspace for shared context and collaboration."""

    # Workspace Identity
    thread_id: str

    # Shared Context Data (structured model)
    context: WorkspaceContext = Field(default_factory=WorkspaceContext)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # ========== CLASS METHODS ==========

    @classmethod
    def create(cls, thread_id: str) -> Workspace:
        """Create a new workspace for a thread."""
        return cls(thread_id=thread_id)

    # ========== INSTANCE METHODS ==========

    def add_fact(self, fact: str) -> Workspace:
        """Add a fact to the workspace."""
        if fact not in self.context.facts:
            self.context.facts.append(fact)
            self._update_timestamp()
        return self

    def remove_fact(self, fact: str) -> Workspace:
        """Remove a fact from the workspace."""
        if fact in self.context.facts:
            self.context.facts.remove(fact)
            self._update_timestamp()
        return self

    def add_result(self, result: AgentResult) -> Workspace:
        """Add an agent result to the workspace."""
        self.context.results.append(result)
        self._update_timestamp()
        return self

    def add_artifact(
        self,
        name: str,
        artifact_type: str,
        location: str,
        created_by: str,
        metadata: dict[str, Any] = None,
    ) -> Workspace:
        """Add an artifact reference to the workspace."""
        artifact_ref = WorkspaceArtifact(
            name=name,
            type=artifact_type,
            location=location,
            created_by=created_by,
            metadata=metadata or {},
        )
        self.context.artifacts[name] = artifact_ref
        self._update_timestamp()
        return self

    def remove_artifact(self, name: str) -> Workspace:
        """Remove an artifact from the workspace."""
        if name in self.context.artifacts:
            del self.context.artifacts[name]
            self._update_timestamp()
        return self

    def set_variable(self, key: str, value: Any) -> Workspace:
        """Set a variable in the workspace."""
        self.context.variables[key] = value
        self._update_timestamp()
        return self

    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a variable from the workspace."""
        return self.context.variables.get(key, default)

    def remove_variable(self, key: str) -> Workspace:
        """Remove a variable from the workspace."""
        if key in self.context.variables:
            del self.context.variables[key]
            self._update_timestamp()
        return self

    def clear_results(self) -> Workspace:
        """Clear all results from the workspace."""
        self.context.results.clear()
        self._update_timestamp()
        return self

    def clear_facts(self) -> Workspace:
        """Clear all facts from the workspace."""
        self.context.facts.clear()
        self._update_timestamp()
        return self

    def clear_all(self) -> Workspace:
        """Clear all data from the workspace."""
        self.context.facts.clear()
        self.context.results.clear()
        self.context.artifacts.clear()
        self.context.variables.clear()
        self.context.conversation_history.clear()
        self._update_timestamp()
        return self

    # ========== CONVERSATION HISTORY MANAGEMENT ==========

    def add_message(self, message: ChatMessage) -> Workspace:
        """Add a message to the conversation history."""
        self.context.conversation_history.append(message)
        self._update_timestamp()
        return self

    def add_messages(self, messages: list[ChatMessage]) -> Workspace:
        """Add multiple messages to the conversation history."""
        self.context.conversation_history.extend(messages)
        self._update_timestamp()
        return self

    def copy_messages_from_graphstate(self, graphstate_messages: list[ChatMessage]) -> Workspace:
        """Copy messages from GraphState to workspace conversation history."""
        copied_messages = deepcopy(graphstate_messages)
        self.add_messages(copied_messages)
        return self

    def append_messages_from_graphstate(self, graphstate_messages: list[ChatMessage]) -> Workspace:
        """Append new messages from GraphState, avoiding duplicates."""
        existing_signatures = {(msg.role, msg.content) for msg in self.context.conversation_history}

        new_messages = [
            msg for msg in graphstate_messages if (msg.role, msg.content) not in existing_signatures
        ]

        if new_messages:
            self.add_messages(new_messages)

        return self

    def clear_conversation_history(self) -> Workspace:
        """Clear all conversation history."""
        self.context.conversation_history.clear()
        self._update_timestamp()
        return self

    def get_conversation_summary(self) -> dict[str, Any]:
        """Get a summary of the conversation history."""
        if not self.context.conversation_history:
            return {"message_count": 0, "participants": [], "latest_message": None}

        # Count messages by role
        role_counts = {}
        participants = set()

        for msg in self.context.conversation_history:
            role_str = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            role_counts[role_str] = role_counts.get(role_str, 0) + 1
            participants.add(role_str)

        latest_message = self.context.conversation_history[-1]

        return {
            "message_count": len(self.context.conversation_history),
            "role_counts": role_counts,
            "participants": list(participants),
            "latest_message": {
                "role": latest_message.role.value
                if hasattr(latest_message.role, "value")
                else str(latest_message.role),
                "content_preview": latest_message.content[:100] + "..."
                if len(latest_message.content) > 100
                else latest_message.content,
            },
        }

    def get_recent_messages(self, count: int = 10) -> list[ChatMessage]:
        """Get the most recent messages from conversation history."""
        return (
            self.context.conversation_history[-count:] if self.context.conversation_history else []
        )

    def get_messages_by_role(self, role) -> list[ChatMessage]:
        """Get all messages from a specific role."""
        target_role = role.value if hasattr(role, "value") else str(role)
        return [
            msg
            for msg in self.context.conversation_history
            if (msg.role.value if hasattr(msg.role, "value") else str(msg.role)) == target_role
        ]

    # ========== HELPER METHODS ==========

    def get_latest_result(self) -> AgentResult | None:
        """Get the most recent agent result."""
        return self.context.results[-1] if self.context.results else None

    def get_results_by_agent(self, agent_id: str) -> list[AgentResult]:
        """Get all results from a specific agent."""
        return [
            result
            for result in self.context.results
            if hasattr(result, "agent_id") and result.agent_id == agent_id
        ]

    def get_artifact_by_type(self, artifact_type: str) -> list[WorkspaceArtifact]:
        """Get all artifacts of a specific type."""
        return [
            artifact
            for artifact in self.context.artifacts.values()
            if artifact.type == artifact_type
        ]

    def has_fact(self, fact: str) -> bool:
        """Check if a fact exists in the workspace."""
        return fact in self.context.facts

    def has_artifact(self, name: str) -> bool:
        """Check if an artifact exists in the workspace."""
        return name in self.context.artifacts

    def has_variable(self, key: str) -> bool:
        """Check if a variable exists in the workspace."""
        return key in self.context.variables

    def get_context_summary(self) -> dict[str, Any]:
        """Get a summary of the workspace context."""
        return {
            "thread_id": self.thread_id,
            "facts_count": len(self.context.facts),
            "results_count": len(self.context.results),
            "artifacts_count": len(self.context.artifacts),
            "variables_count": len(self.context.variables),
            "conversation_history_count": len(self.context.conversation_history),
            "created_at": self.created_at,
            "last_updated": self.last_updated,
        }

    def _update_timestamp(self) -> None:
        """Update the last updated timestamp."""
        self.last_updated = datetime.now(UTC)
