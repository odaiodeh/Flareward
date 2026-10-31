"""Translate workflow state to coding work; never create execution environments here."""

import hashlib

from mas.application.coding.contracts import CodingAgent, CodingRequest
from mas.application.elements.node import BaseNode
from mas.core.execution_context import ExecutionContextHolder
from mas.graph.state.graph_state import Channel
from mas.graph.state.state_view import StateView


class CodingAgentNode(BaseNode):
    READS = {Channel.USER_PROMPT, Channel.OUTPUT, Channel.NODES_OUTPUT, Channel.MESSAGES}
    WRITES = {Channel.OUTPUT, Channel.NODES_OUTPUT, Channel.MESSAGES}

    def __init__(
        self,
        agent: CodingAgent,
        holder: ExecutionContextHolder,
        workspace: str,
        instructions: str,
    ) -> None:
        super().__init__()
        self._agent, self._holder = agent, holder
        self._workspace, self._instructions = workspace, instructions

    async def run(self, state: StateView) -> StateView:
        context = self._holder.context
        if not context.root_execution_id:
            raise ValueError("Coding workspace requires a root execution identity")
        namespace = hashlib.sha256(context.root_execution_id.encode()).hexdigest()
        prompt = "\n\n".join(
            value
            for value in (
                self._instructions,
                "Workflow request: " + state[Channel.USER_PROMPT],
                "Previous step result: " + state[Channel.OUTPUT],
            )
            if value
        )
        result = await self._agent.execute(
            CodingRequest(prompt=prompt, workspace=f"{namespace}/{self._workspace}")
        )
        state[Channel.NODES_OUTPUT][self.uid] = result.model_dump_json()
        state[Channel.OUTPUT] = result.content
        self.promote_to_messages(result.content)
        return state
