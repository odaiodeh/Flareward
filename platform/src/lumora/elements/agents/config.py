"""Agent system configuration classes and utilities."""

from dataclasses import dataclass

from lumora.elements.agents.constants import EarlyStoppingPolicy, ExecutionDefaults
from lumora.elements.agents.execution.handlers import ExecutionMode
from lumora.elements.agents.hitl_config import HITLHandlerConfig
from lumora.elements.tools.config import ExecutorConfig


@dataclass
class AgentConfig:
    """Configuration for agent execution."""

    execution_mode: ExecutionMode = ExecutionMode.AUTO

    max_execution_time: float | None = ExecutionDefaults.MAX_EXECUTION_TIME
    max_actions_per_minute: int | None = ExecutionDefaults.MAX_ACTIONS_PER_MINUTE

    early_stopping: str = EarlyStoppingPolicy.FIRST_FINISH.value
    return_intermediate: bool = ExecutionDefaults.RETURN_INTERMEDIATE

    executor_config: ExecutorConfig | None = None

    hitl_config: HITLHandlerConfig | None = None
