from mas.application.elements.node import BaseNode
from mas.graph.state.graph_state import Channel
from mas.graph.state.state_view import StateView


class MockAgentNode(BaseNode):
    """
    Test stub: echoes the user prompt or returns a fixed message.
    """

    READS = {Channel.USER_PROMPT}
    WRITES = {Channel.NODES_OUTPUT}

    def __init__(self, *, name: str = "mock_agent", echo_message: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.echo_message = echo_message

    async def run(self, state: StateView) -> StateView:
        response = (
            self.echo_message
            if self.echo_message is not None
            else f"Mock echo: {state.get(Channel.USER_PROMPT, '')}"
        )
        state[Channel.NODES_OUTPUT] = {self.uid: response}
        return state
