"""Values exchanged by agent strategies and execution handlers."""

import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any
from uuid import uuid4


class StepType(Enum):
    PLANNING = "planning"
    ACTION = "action"
    OBSERVATION = "observation"
    ERROR = "error"
    FINISH = "finish"


class ActionStatus(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    INVALID = "invalid"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class AgentAction:
    tool: str
    tool_input: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid4()))
    reasoning: str = ""
    raw_output: str | None = None
    status: ActionStatus = ActionStatus.PENDING
    error: str | None = None

    def with_status(self, status: ActionStatus, error: str | None = None) -> AgentAction:
        return replace(self, status=status, error=error)

    def is_terminal(self) -> bool:
        return self.status in (ActionStatus.SUCCESS, ActionStatus.FAILED, ActionStatus.SKIPPED)

    def is_successful(self) -> bool:
        return self.status == ActionStatus.SUCCESS


@dataclass(frozen=True)
class AgentObservation:
    action_id: str
    tool: str
    output: Any
    success: bool = True
    error: Exception | None = None
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def content(self) -> str:
        return str(self.output) if self.success else f"Error: {self.error}"

    def is_error(self) -> bool:
        return not self.success or self.error is not None


@dataclass(frozen=True)
class AgentFinish:
    output: Any
    reasoning: str = ""
    return_values: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        result = {**self.return_values, "output": self.output}
        if self.reasoning:
            result["reasoning"] = self.reasoning
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class AgentStep:
    type: StepType
    data: Any
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.type in (StepType.FINISH, StepType.ERROR)

    def is_action(self) -> bool:
        return self.type == StepType.ACTION

    def is_observation(self) -> bool:
        return self.type == StepType.OBSERVATION

    def is_finish(self) -> bool:
        return self.type == StepType.FINISH

    def is_error(self) -> bool:
        return self.type == StepType.ERROR


type ActionObservationPair = tuple[AgentAction, AgentObservation]
type ExecutionHistory = list[AgentStep]
