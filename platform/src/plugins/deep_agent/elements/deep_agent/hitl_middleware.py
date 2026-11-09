"""HITL middleware for Deep Agents — bridges LangChain's ``wrap_tool_call``
hook to our domain ``ApprovalGate`` / ``ToolApprovalPolicy``.

Delegates the resolve → check → request flow to ``HITLToolGatekeeper``
(shared with ``HITLExecutionHandler`` and ``HITLHook``).  This adapter
is responsible only for translating gatekeeper results into the
``ToolMessage`` objects that LangGraph expects.

Deep Agents come with built-in tools (``write_file``, ``edit_file``,
``execute``, ``task``, etc.) that are NOT in our domain tool registry.
``DEEP_AGENT_BUILTIN_ACCESS_MODES`` maps these to the correct
``ToolAccessMode`` so they are properly gated.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest

from flareward.elements.agents.approvals import HITLToolGatekeeper
from flareward.elements.ports.tool import BaseTool
from flareward.services.interactions.tools.models import (
    ApprovalDecision,
    RequestOrigin,
    ToolAccessMode,
    ToolApprovalPolicy,
)
from flareward.services.interactions.tools.ports import ApprovalGate

logger = logging.getLogger(__name__)


DEEP_AGENT_BUILTIN_ACCESS_MODES: dict[str, ToolAccessMode] = {
    "ls": ToolAccessMode.READ,
    "read_file": ToolAccessMode.READ,
    "glob": ToolAccessMode.READ,
    "grep": ToolAccessMode.READ,
    "write_file": ToolAccessMode.WRITE,
    "edit_file": ToolAccessMode.WRITE,
    "execute": ToolAccessMode.DESTRUCTIVE,
    "write_todos": ToolAccessMode.READ,
    "task": ToolAccessMode.WRITE,
    "start_async_task": ToolAccessMode.WRITE,
    "check_async_task": ToolAccessMode.READ,
    "update_async_task": ToolAccessMode.WRITE,
    "cancel_async_task": ToolAccessMode.WRITE,
    "list_async_tasks": ToolAccessMode.READ,
}


class HITLMiddleware(AgentMiddleware):
    """LangChain ``AgentMiddleware`` that gates tool calls through our
    HITL approval system.

    Decision mapping (our domain → LangChain response):
      APPROVE  → call handler(request)
      MODIFY   → override request args, then call handler
      REJECT   → return ToolMessage with rejection feedback
      REDIRECT → return ToolMessage with human instruction
    """

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        policy: ToolApprovalPolicy,
        tool_registry: dict[str, BaseTool],
        origin: RequestOrigin,
        default_access_mode: ToolAccessMode = ToolAccessMode.WRITE,
    ) -> None:
        super().__init__()
        self._gatekeeper = HITLToolGatekeeper(
            gate=gate,
            policy=policy,
            tool_registry=tool_registry,
            origin=origin,
            builtin_access_modes=DEEP_AGENT_BUILTIN_ACCESS_MODES,
            default_access_mode=default_access_mode,
        )

    # ------------------------------------------------------------------
    # wrap_tool_call — the single integration point
    # ------------------------------------------------------------------

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        tool_name = request.tool_call["name"]
        tool_args = request.tool_call.get("args", {})
        tool_call_id = request.tool_call.get("id", "")

        response = await self._gatekeeper.check(tool_name, tool_args)

        if response is None:
            return await handler(request)

        match response.decision:
            case ApprovalDecision.APPROVE:
                return await handler(request)

            case ApprovalDecision.MODIFY:
                return await self._handle_modify(request, response, handler)

            case ApprovalDecision.REJECT:
                return self._rejection_message(
                    tool_call_id,
                    f"Action rejected by human operator. "
                    f"Reason: {response.feedback}. "
                    f"Please choose a safer approach.",
                )

            case ApprovalDecision.REDIRECT:
                return self._rejection_message(
                    tool_call_id,
                    f"Human operator instruction: {response.feedback}",
                )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    async def _handle_modify(
        request: ToolCallRequest,
        response: Any,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        modified_args = response.modified_args
        if not modified_args:
            return await handler(request)

        modified_tool_call = {
            **request.tool_call,
            "args": modified_args,
        }
        modified_request = request.override(tool_call=modified_tool_call)
        return await handler(modified_request)

    @staticmethod
    def _rejection_message(tool_call_id: str, content: str) -> ToolMessage:
        return ToolMessage(
            content=content,
            tool_call_id=tool_call_id,
        )
