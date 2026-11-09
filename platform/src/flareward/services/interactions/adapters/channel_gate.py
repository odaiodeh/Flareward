"""
Channel-based ApprovalGate adapter.

Emits an ``approval_required`` event through the channel's outbound
path, then blocks on the channel's inbound path (``wait_for``) until
the human responds or the timeout expires.

Works identically for ``LocalInputCapableChannel`` (foreground,
same-process) and ``RedisInputCapableChannel`` (background,
cross-process) — the channel adapter hides the difference.
"""

import asyncio
import logging
from dataclasses import asdict

from flareward.async_work import await_owned
from flareward.elements.messaging.channels import InputCapableChannel
from flareward.services.interactions.tools.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResponse,
    HITLConfig,
)
from flareward.services.interactions.tools.ports import ApprovalGate

logger = logging.getLogger(__name__)


class ChannelApprovalGate(ApprovalGate):
    """ApprovalGate that uses an InputCapableChannel for transport."""

    def __init__(
        self,
        channel: InputCapableChannel,
        config: HITLConfig,
    ) -> None:
        super().__init__(config)
        self._channel = channel

    async def _send_and_wait(
        self,
        request: ApprovalRequest,
        timeout: float,
    ) -> ApprovalResponse | None:
        return await await_owned(asyncio.to_thread(self._wait_for_response, request, timeout))

    def _wait_for_response(
        self,
        request: ApprovalRequest,
        timeout: float,
    ) -> ApprovalResponse | None:
        args_str = str(request.tool_args)
        channel_sid = self._channel.session_id
        logger.info(
            "HITL approval required: tool=%s, access_mode=%s, "
            "origin=%s (%s), session=%s, timeout=%ss",
            request.tool_name,
            request.tool_access_mode.value,
            request.origin.node_display_name,
            request.origin.node_uid,
            channel_sid,
            timeout,
        )
        logger.debug(
            "HITL request_id=%s, args=%s",
            request.request_id,
            args_str,
        )

        self._channel.emit(
            {
                "type": "approval_required",
                "node": request.origin.node_uid,
                "display_name": request.origin.node_display_name,
                "request_id": request.request_id,
                "approval_type": request.type.value,
                "origin": asdict(request.origin),
                "tool_name": request.tool_name,
                "tool_args": request.tool_args,
                "tool_description": request.tool_description,
                "tool_access_mode": request.tool_access_mode.value,
                "reasoning": request.reasoning,
            }
        )

        raw = self._channel.wait_for(request.request_id, timeout=timeout)
        if raw is None:
            logger.info(
                "HITL timeout: request_id=%s, applying default=%s",
                request.request_id,
                self._config.timeout_decision.value,
            )
            return None

        decision = raw.get("decision", "reject")
        logger.info(
            "HITL response: request_id=%s, decision=%s, feedback=%s",
            request.request_id,
            decision,
            raw.get("feedback", ""),
        )

        return ApprovalResponse(
            request_id=request.request_id,
            decision=ApprovalDecision(decision),
            feedback=raw.get("feedback", ""),
            modified_args=raw.get("modified_args", {}),
        )
