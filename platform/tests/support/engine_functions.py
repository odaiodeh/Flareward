"""Adapter-specific functions used to verify the actual engine state contract."""

from flareward.elements.messaging.domain.messages import ChatMessage, Role
from flareward.executions.adapters.run_engine.shared.state import AgentProgramGraphState


def state_identity(state: AgentProgramGraphState) -> AgentProgramGraphState:
    return state


def contribute_state(state: AgentProgramGraphState, *, uid: str) -> AgentProgramGraphState:
    state.messages.append(ChatMessage(role=Role.ASSISTANT, content=uid))
    state.inter_packets[0].acknowledge(uid)
    state.task_threads.setdefault(uid, []).append(ChatMessage(role=Role.ASSISTANT, content=uid))
    state.workspaces[uid] = {"result": uid}
    return state
