"""Execution handlers for different agent execution modes."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from enum import Enum

from mas.application.agents.execution.executor import AgentActionExecutor
from mas.domain.agents import AgentAction, AgentObservation, AgentStep, StepType


class ExecutionMode(Enum):
    """Different modes of agent execution."""

    AUTO = "auto"  # Automatically execute all actions
    GUIDED = "guided"  # Ask for confirmation before execution
    HITL = "hitl"  # Gate WRITE tools through human approval


class ExecutionHandler(ABC):
    """Abstract base class for execution handlers."""

    def __init__(self, action_executor: AgentActionExecutor):
        """Initialize execution handler."""
        self.action_executor = action_executor
        self.observations: list[AgentObservation] = []

    @abstractmethod
    def handle_actions(self, actions: list[AgentAction]) -> AsyncIterator[AgentStep]:
        """Handle a batch of actions according to execution policy."""
        pass

    @abstractmethod
    def is_ready_for_next_iteration(self) -> bool:
        """Check if handler is ready for the next iteration."""
        pass

    def get_observations(self) -> list[AgentObservation]:
        """Get all observations collected by this handler."""
        return list(self.observations)


class AutoExecutionHandler(ExecutionHandler):
    """Automatic execution handler."""

    async def handle_actions(self, actions: list[AgentAction]) -> AsyncIterator[AgentStep]:
        """Execute all actions immediately and yield observations individually."""
        if not actions:
            return

        # Execute all actions together (efficient batch execution)
        batch_observations = await self.action_executor.execute_batch(actions)

        # Store observations
        self.observations.extend(batch_observations)

        # Yield each observation as individual step (matches LLM conversation format)
        for obs in batch_observations:
            obs_step = AgentStep(
                StepType.OBSERVATION,
                obs,
                metadata={
                    "action_id": obs.action_id,
                    "execution_time": obs.execution_time,
                    "success": obs.success,
                    "handler": "auto",
                },
            )
            yield obs_step

    def is_ready_for_next_iteration(self) -> bool:
        """Auto handler is always ready for next iteration."""
        return True


class GuidedExecutionHandler(ExecutionHandler):
    """Guided execution handler."""

    def __init__(self, action_executor: AgentActionExecutor):
        super().__init__(action_executor)
        self.pending_actions: list[AgentAction] = []
        self.confirmed_actions: dict[str, bool] = {}

    async def handle_actions(self, actions: list[AgentAction]) -> AsyncIterator[AgentStep]:
        """Queue actions for confirmation."""

        for action in actions:
            self.pending_actions.append(action)

            # Yield action step for confirmation
            action_step = AgentStep(
                StepType.ACTION,
                action,
                metadata={
                    "action_id": action.id,
                    "requires_confirmation": True,
                    "handler": "guided",
                },
            )
            yield action_step

    async def confirm_action(self, action_id: str, execute: bool = True) -> AgentStep | None:
        """Confirm and optionally execute a pending action."""
        # Find the action
        action = None
        for pending_action in self.pending_actions:
            if pending_action.id == action_id:
                action = pending_action
                break

        if not action:
            return None

        # Mark as confirmed
        self.confirmed_actions[action_id] = execute

        if execute:
            # Execute single action
            obs = await self.action_executor.execute(action)
            self.observations.append(obs)

            # Remove from pending
            self.pending_actions.remove(action)

            # Return observation step
            return AgentStep(
                StepType.OBSERVATION,
                obs,
                metadata={
                    "action_id": obs.action_id,
                    "execution_time": obs.execution_time,
                    "success": obs.success,
                    "handler": "guided",
                    "confirmed": True,
                },
            )
        else:
            # Remove from pending without executing
            self.pending_actions.remove(action)
            return None

    def get_pending_actions(self) -> list[AgentAction]:
        """Get list of actions pending confirmation."""
        return list(self.pending_actions)

    def is_ready_for_next_iteration(self) -> bool:
        """Guided handler is ready when no actions are pending."""
        return len(self.pending_actions) == 0
