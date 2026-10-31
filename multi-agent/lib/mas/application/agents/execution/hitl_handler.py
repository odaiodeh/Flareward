"""HITL execution handler — gates WRITE/DESTRUCTIVE tool calls through an ApprovalGate while
executing READ tools automatically.
"""

import logging
from collections.abc import AsyncIterator
from dataclasses import replace

from mas.application.agents.approvals import HITLToolGatekeeper
from mas.application.agents.execution.executor import AgentActionExecutor
from mas.application.agents.execution.handlers import ExecutionHandler
from mas.application.ports.tool import BaseTool
from mas.core.hitl.models import ApprovalDecision, RequestOrigin, ToolApprovalPolicy
from mas.core.hitl.ports import ApprovalGate
from mas.domain.agents import AgentAction, AgentObservation, AgentStep, StepType

logger = logging.getLogger(__name__)


class HITLExecutionHandler(ExecutionHandler):
    """Execution handler that gates tool calls through human approval."""

    def __init__(
        self,
        action_executor: AgentActionExecutor,
        *,
        gate: ApprovalGate,
        policy: ToolApprovalPolicy,
        tool_registry: dict[str, BaseTool],
        node_uid: str,
        node_display_name: str,
        session_id: str,
    ) -> None:
        super().__init__(action_executor)
        self._gatekeeper = HITLToolGatekeeper(
            gate=gate,
            policy=policy,
            tool_registry=tool_registry,
            origin=RequestOrigin(
                node_uid=node_uid,
                node_display_name=node_display_name,
                session_id=session_id,
            ),
        )

    # ------------------------------------------------------------------
    # ExecutionHandler contract
    # ------------------------------------------------------------------

    async def handle_actions(self, actions: list[AgentAction]) -> AsyncIterator[AgentStep]:
        if not actions:
            return

        for action in actions:
            response = await self._gatekeeper.check(
                action.tool, action.tool_input, reasoning=action.reasoning
            )

            if response is None:
                yield await self._execute_action(action)
                continue

            match response.decision:
                case ApprovalDecision.APPROVE:
                    yield await self._execute_action(action)

                case ApprovalDecision.MODIFY:
                    modified = self._apply_modification(action, response.modified_args)
                    yield await self._execute_action(modified, modified=True)

                case ApprovalDecision.REJECT:
                    yield self._rejection_step(
                        action,
                        f"Action rejected by human operator. "
                        f"Reason: {response.feedback}. "
                        f"Please choose a safer approach.",
                    )

                case ApprovalDecision.REDIRECT:
                    yield self._rejection_step(
                        action,
                        f"Human operator instruction: {response.feedback}",
                    )

    def is_ready_for_next_iteration(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _execute_action(
        self,
        action: AgentAction,
        *,
        modified: bool = False,
    ) -> AgentStep:
        obs = await self.action_executor.execute(action)
        self.observations.append(obs)
        return AgentStep(
            StepType.OBSERVATION,
            obs,
            metadata={
                "action_id": obs.action_id,
                "execution_time": obs.execution_time,
                "success": obs.success,
                "handler": "hitl",
                "modified": modified,
            },
        )

    @staticmethod
    def _apply_modification(
        action: AgentAction,
        modified_args: dict,
    ) -> AgentAction:
        if not modified_args:
            return action
        return replace(action, tool_input=modified_args)

    def _rejection_step(self, action: AgentAction, message: str) -> AgentStep:
        obs = AgentObservation(
            action_id=action.id,
            tool=action.tool,
            output=message,
            success=False,
            error=None,
            execution_time=0.0,
        )
        self.observations.append(obs)
        return AgentStep(
            StepType.OBSERVATION,
            obs,
            metadata={
                "action_id": action.id,
                "handler": "hitl",
                "rejected": True,
            },
        )
