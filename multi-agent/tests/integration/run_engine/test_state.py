"""Domain merge semantics survive real parallel invocation boundaries."""

from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import TaskPacket
from mas.domain.messages import ChatMessage, Role
from run_engine.state import AgentProgramGraphState
from runengine import GraphBuilder
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.bootstrap.hosts import RunHostBuilder
from support.engine_functions import contribute_state, state_identity


async def test_parallel_state_keeps_messages_acknowledgments_threads_and_workspaces():
    original = AgentProgramGraphState(
        messages=[ChatMessage(role=Role.USER, content="request")],
        inter_packets=[
            TaskPacket(src=ElementAddress(uid="source"), dst=ElementAddress(uid="team"), payload={})
        ],
    )
    graph = (
        GraphBuilder(AgentProgramGraphState)
        .add_node("start", state_identity)
        .add_node("a", contribute_state, kwargs={"uid": "a"})
        .add_node("b", contribute_state, kwargs={"uid": "b"})
        .add_node("finish", state_identity)
        .add_edge("start", "a")
        .add_edge("start", "b")
        .add_edge("a", "finish")
        .add_edge("b", "finish")
        .set_entry("start")
        .set_exit("finish")
        .compile()
    )
    async with RunHostBuilder.create(LocalHostConfig()) as host:
        state = (await graph.run(original, host=host)).final_state
    assert [message.content for message in state.messages] == ["request", "a", "b"]
    assert state.inter_packets[0].ack_by == {"a", "b"}
    assert set(state.task_threads) == {"a", "b"}
    assert state.workspaces == {"a": {"result": "a"}, "b": {"result": "b"}}
    assert original.inter_packets[0].ack_by == set()
    assert len(original.messages) == 1
