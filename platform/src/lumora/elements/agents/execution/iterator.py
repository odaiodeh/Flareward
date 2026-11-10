"""AgentIterator focused purely on iteration (SOLID compliant)."""

import logging
from collections import deque
from collections.abc import Callable

from lumora.elements.agents.domain.models import (
    AgentAction,
    AgentObservation,
    AgentStep,
    StepType,
)
from lumora.elements.agents.execution.handlers import ExecutionHandler, GuidedExecutionHandler
from lumora.elements.agents.strategies.base import AgentStrategy
from lumora.elements.messaging.domain.messages import ChatMessage, Role
from lumora.services.tracing import NoOpTracingService, TracingService

logger = logging.getLogger(__name__)


class AgentIterator:
    """Iterator for step-by-step agent execution."""

    def __init__(
        self,
        *,
        strategy: AgentStrategy,
        execution_handler: ExecutionHandler,
        on_action: Callable[[AgentAction], bool] | None = None,
        tracing: TracingService = None,
    ):
        """Initialize clean agent iterator."""
        self.strategy = strategy
        self.execution_handler = execution_handler
        self.on_action = on_action

        # Execution state (iterator's core responsibility)
        self.messages: list[ChatMessage] = []
        self.history: list[AgentStep] = []
        self._finished = False
        self._iteration_count = 0

        # Queue for steps waiting to be yielded
        self._step_queue: deque[AgentStep] = deque()

        self._tracing = tracing or NoOpTracingService()

    def __aiter__(self) -> AgentIterator:
        return self

    async def __anext__(self) -> AgentStep:
        while not self._step_queue:
            if self._finished or not self.execution_handler.is_ready_for_next_iteration():
                raise StopAsyncIteration
            if not self.strategy.should_continue(self.history):
                self._finished = True
                raise StopAsyncIteration
            self._iteration_count += 1
            with self._tracing.trace_agent_iteration(
                iteration=self._iteration_count,
                strategy=self.strategy.strategy_name,
            ) as handle:
                try:
                    await self._advance()
                except Exception as error:
                    handle.update(
                        level="ERROR",
                        status_message=f"Agent iteration failed ({type(error).__name__})",
                    )
                    step = AgentStep(
                        StepType.ERROR,
                        error,
                        metadata={
                            "error_type": type(error).__name__,
                            "iteration": self._iteration_count,
                        },
                    )
                    self.history.append(step)
                    self._step_queue.append(step)
        return self._step_queue.popleft()

    async def _advance(self) -> None:
        steps = await self.strategy.think(self.messages)
        self._update_conversation_messages(steps)
        actions = []
        for step in steps:
            self.history.append(step)
            if step.type == StepType.ACTION:
                action = step.data
                if self.on_action and not self.on_action(action):
                    self._record_result(self._create_rejection_step(action, "Rejected by policy"))
                else:
                    actions.append(action)
            elif step.type in (StepType.FINISH, StepType.ERROR, StepType.PLANNING):
                if step.type == StepType.FINISH:
                    self._finished = True
                self._step_queue.append(step)
        if actions:
            async for result in self.execution_handler.handle_actions(actions):
                self._record_result(result)

    def _record_result(self, step: AgentStep) -> None:
        self.history.append(step)
        self._step_queue.append(step)
        if step.type == StepType.OBSERVATION:
            observation = step.data
            if observation.success or observation.output:
                content = str(observation.output)
            elif observation.error:
                content = f"Error: {observation.error}"
            else:
                content = "Tool call was blocked."
            self.messages.append(
                ChatMessage(
                    role=Role.TOOL,
                    content=content,
                    tool_call_id=observation.action_id,
                )
            )

    def _update_conversation_messages(self, steps: list[AgentStep]) -> None:
        """Update conversation messages with assistant responses."""
        for step in steps:
            if step.type == StepType.PLANNING and isinstance(step.data, ChatMessage):
                if step.data.role == Role.ASSISTANT:
                    self.messages.append(step.data)

    def _create_rejection_step(self, action: AgentAction, reason: str) -> AgentStep:
        """Create a step representing action rejection."""
        rejection_obs = AgentObservation(
            action_id=action.id,
            tool=action.tool,
            output=None,
            success=False,
            error=Exception(reason),
            execution_time=0.0,
        )

        # Add to execution handler's observations for proper tracking
        self.execution_handler.observations.append(rejection_obs)

        return AgentStep(
            StepType.OBSERVATION, rejection_obs, metadata={"rejected": True, "reason": reason}
        )

    # Properties for backward compatibility and access to state
    @property
    def observations(self) -> list[AgentObservation]:
        """Get all observations from execution handler."""
        return self.execution_handler.get_observations()

    @property
    def finished(self) -> bool:
        """Check if iteration is finished."""
        return self._finished

    # Compatibility methods for guided mode testing
    def get_pending_actions(self) -> list[AgentAction]:
        """Get list of actions pending confirmation (GUIDED mode only)."""

        if isinstance(self.execution_handler, GuidedExecutionHandler):
            return self.execution_handler.get_pending_actions()
        else:
            return []

    async def confirm_action(self, action_id: str, execute: bool = True) -> AgentStep | None:
        """Confirm and optionally execute a pending action (GUIDED mode only)."""
        if isinstance(self.execution_handler, GuidedExecutionHandler):
            return await self.execution_handler.confirm_action(action_id, execute)
        else:
            return None

    @property
    def pending_actions(self) -> list[AgentAction]:
        """Get pending actions (compatibility property)."""
        return self.get_pending_actions()
