"""Adapter-specific functions used to verify the actual engine state contract."""

from mas.domain.messages import ChatMessage, Role
from run_engine.state import ProgramGraphState


def state_identity(state: ProgramGraphState) -> ProgramGraphState:
    return state


def contribute_state(state: ProgramGraphState, *, uid: str) -> ProgramGraphState:
    state.messages.append(ChatMessage(role=Role.ASSISTANT, content=uid))
    state.inter_packets[0].acknowledge(uid)
    state.task_threads.setdefault(uid, []).append(ChatMessage(role=Role.ASSISTANT, content=uid))
    state.workspaces[uid] = {"result": uid}
    return state
