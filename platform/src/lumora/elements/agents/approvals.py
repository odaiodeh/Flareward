"""Shared tool-call gating logic for HITL approval."""

import logging

from lumora.elements.ports.tool import BaseTool
from lumora.services.interactions.tools.models import (
    ApprovalRequest,
    ApprovalResponse,
    ApprovalType,
    RequestOrigin,
    ToolAccessMode,
    ToolApprovalPolicy,
)
from lumora.services.interactions.tools.ports import ApprovalGate

logger = logging.getLogger(__name__)


class HITLToolGatekeeper:
    """Resolves tool access modes, checks the approval policy, and requests human approval via
    the ``ApprovalGate``.
    """

    def __init__(
        self,
        *,
        gate: ApprovalGate,
        policy: ToolApprovalPolicy,
        tool_registry: dict[str, BaseTool],
        origin: RequestOrigin,
        builtin_access_modes: dict[str, ToolAccessMode] | None = None,
        default_access_mode: ToolAccessMode = ToolAccessMode.WRITE,
    ) -> None:
        self._gate = gate
        self._policy = policy
        self._tool_registry = tool_registry
        self._origin = origin
        self._builtin_modes = builtin_access_modes or {}
        self._default_mode = default_access_mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_access_mode(self, tool_name: str) -> ToolAccessMode:
        """Determine the access mode for *tool_name*."""
        domain_tool = self._tool_registry.get(tool_name)
        if domain_tool is not None:
            return domain_tool.access_mode
        return self._builtin_modes.get(tool_name, self._default_mode)

    async def check(
        self,
        tool_name: str,
        tool_args: dict,
        *,
        reasoning: str | None = None,
    ) -> ApprovalResponse | None:
        """Gate a single tool call through the HITL approval system."""
        access_mode = self.resolve_access_mode(tool_name)

        if not self._policy.requires_approval(tool_name, access_mode):
            logger.debug(
                "HITL gatekeeper auto-approved '%s' (mode=%s)",
                tool_name,
                access_mode.value,
            )
            return None

        logger.info(
            "HITL gatekeeper requesting approval: tool=%s, mode=%s, node=%s",
            tool_name,
            access_mode.value,
            self._origin.node_uid,
        )

        domain_tool = self._tool_registry.get(tool_name)
        request = ApprovalRequest(
            request_id=ApprovalRequest.generate_id(),
            type=ApprovalType.TOOL_EXECUTION,
            origin=self._origin,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_description=domain_tool.description if domain_tool else "",
            tool_access_mode=access_mode,
            reasoning=reasoning or "",
        )
        response = await self._gate.request_approval(request)

        logger.info(
            "HITL gatekeeper decision: tool=%s, decision=%s",
            tool_name,
            response.decision.value,
        )
        return response
