"""Simplified agent action executor for direct tool execution."""

import time

from mas.application.agents.constants import ToolExecutionDefaults
from mas.application.tools.executor import ToolExecutorManager
from mas.application.tools.models import ToolExecutionRequest, ToolExecutionResponse
from mas.domain.agents import AgentAction, AgentObservation


class AgentActionExecutor:
    """Simplified executor for agent actions using ToolExecutorManager."""

    def __init__(
        self,
        *,
        tool_executor_manager: ToolExecutorManager,
        validate_args: bool = ToolExecutionDefaults.VALIDATE_ARGS,
    ):
        """Initialize agent action executor."""
        self.tool_executor_manager = tool_executor_manager
        self.validate_args = validate_args

    async def execute(self, action: AgentAction) -> AgentObservation:
        """Execute a single agent action and return observation."""
        result = (await self.execute_batch([action]))[0]
        return result

    async def execute_batch(self, actions: list[AgentAction]) -> list[AgentObservation]:
        """Await tool execution directly and return observations in request order."""
        if not actions:
            return []
        start_time = time.perf_counter()

        try:
            # Create ToolExecutionRequests and track missing tools
            requests = []
            missing_tools = []

            for action in actions:
                # Check if tool exists
                if not self.tool_executor_manager.has_tool(action.tool):
                    missing_tools.append(action)
                    continue

                request = ToolExecutionRequest(
                    tool_name=action.tool,
                    tool_call_id=action.id,
                    args=action.tool_input,
                    context={
                        "agent_action": True,
                        "action_id": action.id,
                        "validate_args": self.validate_args,
                    },
                )
                requests.append(request)

            # Create observations for missing tools
            observations = []
            for action in missing_tools:
                observations.append(
                    AgentObservation(
                        action_id=action.id,
                        tool=action.tool,
                        output=None,
                        success=False,
                        error=Exception(f"Tool '{action.tool}' not found"),
                        execution_time=time.perf_counter() - start_time,
                    )
                )

            if requests:
                # Execute via ToolExecutorManager (uses configured execution mode)
                batch_response = await self.tool_executor_manager.execute_requests_async(
                    requests=requests
                    # No mode specified - uses manager's configured execution_mode
                )

                # Convert responses to observations for successful tools
                for action in actions:
                    if action in missing_tools:
                        continue  # Already handled above

                    response = batch_response.get_response(action.id)

                    if response:
                        observation = self._response_to_observation(action, response, start_time)
                    else:
                        # Missing response - shouldn't happen but handle gracefully
                        observation = AgentObservation(
                            action_id=action.id,
                            tool=action.tool,
                            output=None,
                            success=False,
                            error=Exception(f"No response received for tool '{action.tool}'"),
                            execution_time=time.perf_counter() - start_time,
                        )

                    observations.append(observation)

            by_id = {observation.action_id: observation for observation in observations}
            return [by_id[action.id] for action in actions]

        except Exception as e:
            return [
                AgentObservation(
                    action_id=action.id,
                    tool=action.tool,
                    output=None,
                    success=False,
                    error=e,
                    execution_time=time.perf_counter() - start_time,
                    metadata={"error_type": "execution_error"},
                )
                for action in actions
            ]

    def _response_to_observation(
        self, action: AgentAction, response: ToolExecutionResponse, start_time: float
    ) -> AgentObservation:
        """Convert ToolExecutionResponse to AgentObservation."""
        return AgentObservation(
            action_id=action.id,
            tool=action.tool,
            output=response.result if response.success else None,
            success=response.success,
            error=Exception(str(response.error)) if response.error else None,
            execution_time=time.perf_counter() - start_time,
            metadata={
                "tool_execution_time": getattr(response, "execution_time", None),
                "tool_call_id": response.tool_call_id,
            },
        )
