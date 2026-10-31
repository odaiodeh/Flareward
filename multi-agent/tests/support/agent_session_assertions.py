"""Shared behavioral assertions for deterministic, live, and remotely placed agent sessions."""

import hashlib

from mas.domain.messages import Role
from mas.domain.workloads.models import AgentResult
from mas.domain.workloads.workspace import Workspace
from mas.session.domain.session_record import SessionRecord

from support.agent_session import AgentRole


def assert_agent_results(session: SessionRecord, turn: int) -> tuple[AgentResult, AgentResult]:
    state = session.graph_state
    assert len(state.threads) == len(state.workspaces) == 1
    workspace = Workspace.model_validate(next(iter(state.workspaces.values())))
    results = workspace.context.results
    assert len(results) == 2 * turn and all(item.success for item in results), results
    research, review = results[-2:]
    assert research.agent_id == "research" and review.agent_id == "review"
    assert [message.role for message in state.messages] == [Role.USER, Role.ASSISTANT] * turn
    assert all(packet.dst.uid in packet.ack_by for packet in state.inter_packets)
    return research, review


def assert_agent_turn(
    session: SessionRecord,
    seed: str,
    execution_id: str,
    turn: int,
    previous_review: str | None,
) -> str:
    state = session.graph_state
    research, review = assert_agent_results(session, turn)
    expected = {
        role: hashlib.sha256(f"{seed}:{execution_id}:{role.value}".encode()).hexdigest()
        for role in AgentRole
    }
    assert expected[AgentRole.RESEARCH] in research.content
    assert expected[AgentRole.RESEARCH] in review.content
    assert expected[AgentRole.REVIEW] in review.content
    assert expected[AgentRole.REVIEW] in state.output
    assert execution_id in research.content and session.run_id in research.content
    if previous_review is not None:
        assert previous_review in research.content
    return expected[AgentRole.REVIEW]
