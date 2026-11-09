"""Factory for creating execution handlers."""

from flareward.elements.agents.execution.executor import AgentActionExecutor
from flareward.elements.agents.execution.handlers import (
    AutoExecutionHandler,
    ExecutionHandler,
    ExecutionMode,
    GuidedExecutionHandler,
)
from flareward.elements.agents.execution.hitl_handler import HITLExecutionHandler
from flareward.elements.agents.hitl_config import HITLHandlerConfig


class ExecutionHandlerFactory:
    """Factory for creating execution handlers."""

    @staticmethod
    def create(
        mode: ExecutionMode,
        action_executor: AgentActionExecutor,
        hitl_config: HITLHandlerConfig | None = None,
    ) -> ExecutionHandler:
        """Create an execution handler for the specified mode."""
        if mode == ExecutionMode.AUTO:
            return AutoExecutionHandler(action_executor)
        elif mode == ExecutionMode.GUIDED:
            return GuidedExecutionHandler(action_executor)
        elif mode == ExecutionMode.HITL:
            if hitl_config is None:
                raise ValueError("HITLHandlerConfig is required for HITL execution mode")
            return HITLExecutionHandler(
                action_executor,
                gate=hitl_config.gate,
                policy=hitl_config.policy,
                tool_registry=hitl_config.tool_registry,
                node_uid=hitl_config.node_uid,
                node_display_name=hitl_config.node_display_name,
                session_id=hitl_config.session_id,
            )
        else:
            raise ValueError(f"Unsupported execution mode: {mode}")

    @staticmethod
    def get_supported_modes():
        return [ExecutionMode.AUTO, ExecutionMode.GUIDED, ExecutionMode.HITL]
