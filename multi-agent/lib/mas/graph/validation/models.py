from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class MessageCode(StrEnum):
    # Dependency codes
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    MISSING_BRANCH_TARGET = "MISSING_BRANCH_TARGET"

    # Cycle codes
    CYCLE_DETECTED = "CYCLE_DETECTED"

    # Orphan codes
    ORPHANED_STEP = "ORPHANED_STEP"

    # Channel codes
    IMPOSSIBLE_CHANNELS = "IMPOSSIBLE_CHANNELS"
    MISSING_CHANNELS = "MISSING_CHANNELS"

    # Required nodes codes
    MISSING_START_NODE = "MISSING_START_NODE"
    MISSING_END_NODE = "MISSING_END_NODE"
    MISSING_REQUIRED_NODE = "MISSING_REQUIRED_NODE"

    # Maximum nodes codes
    TOO_MANY_START_NODES = "TOO_MANY_START_NODES"
    TOO_MANY_END_NODES = "TOO_MANY_END_NODES"
    TOO_MANY_NODES = "TOO_MANY_NODES"

    # Orchestrator validation codes
    ORCHESTRATOR_INVALID_DELEGATION_EDGE = "ORCHESTRATOR_INVALID_DELEGATION_EDGE"
    ORCHESTRATOR_MISSING_RETURN_PATH = "ORCHESTRATOR_MISSING_RETURN_PATH"
    ORCHESTRATOR_MISSING_FINALIZE = "ORCHESTRATOR_MISSING_FINALIZE"
    ORCHESTRATOR_INVALID_CONDITION_TYPE = "ORCHESTRATOR_INVALID_CONDITION_TYPE"


class ValidationMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    severity: MessageSeverity
    code: MessageCode | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ValidationDetails(BaseModel):
    """Base class for validation details."""

    model_config = ConfigDict(frozen=True)


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    validator_name: str
    is_valid: bool
    messages: list[ValidationMessage] = Field(default_factory=list)
    details: Any = None

    @property
    def errors(self) -> list[ValidationMessage]:
        return [msg for msg in self.messages if msg.severity == MessageSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationMessage]:
        return [msg for msg in self.messages if msg.severity == MessageSeverity.WARNING]


class ValidationResult(BaseModel):
    """Aggregate result from multiple validators."""

    model_config = ConfigDict(frozen=True)

    is_valid: bool
    reports: list[ValidationReport]

    @property
    def all_messages(self) -> list[ValidationMessage]:
        messages = []
        for report in self.reports:
            messages.extend(report.messages)
        return messages

    @property
    def errors(self) -> list[ValidationMessage]:
        return [msg for msg in self.all_messages if msg.severity == MessageSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationMessage]:
        return [msg for msg in self.all_messages if msg.severity == MessageSeverity.WARNING]
