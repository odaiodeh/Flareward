"""Application approval policy awaits a gate without knowing its transport."""

import asyncio

from lumora.elements.agents.approvals import HITLToolGatekeeper
from lumora.services.interactions.tools.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResponse,
    HITLConfig,
    RequestOrigin,
    ToolAccessMode,
    ToolApprovalPolicy,
)
from lumora.services.interactions.tools.ports import ApprovalGate


class RecordingGate(ApprovalGate):
    def __init__(self) -> None:
        super().__init__(HITLConfig())
        self.loop = asyncio.get_running_loop()
        self.requests: list[ApprovalRequest] = []

    async def _send_and_wait(self, request, timeout) -> ApprovalResponse:
        assert asyncio.get_running_loop() is self.loop
        self.requests.append(request)
        return ApprovalResponse(request.request_id, ApprovalDecision.APPROVE)


async def test_gatekeeper_awaits_write_approval_and_normalizes_optional_reasoning():
    gate = RecordingGate()
    origin = RequestOrigin("agent", "Agent", "session")
    gatekeeper = HITLToolGatekeeper(
        gate=gate,
        policy=ToolApprovalPolicy(),
        tool_registry={},
        origin=origin,
    )
    result = await gatekeeper.check("write", {"value": 1})
    assert result.approved
    assert len(gate.requests) == 1
    assert gate.requests[0].origin == origin
    assert gate.requests[0].reasoning == ""
    assert gate.requests[0].tool_args == {"value": 1}


async def test_read_policy_does_not_open_an_approval_wait():
    gate = RecordingGate()
    gatekeeper = HITLToolGatekeeper(
        gate=gate,
        policy=ToolApprovalPolicy(),
        tool_registry={},
        origin=RequestOrigin("agent", "Agent", "session"),
        builtin_access_modes={"read": ToolAccessMode.READ},
    )
    assert await gatekeeper.check("read", {}) is None
    assert gate.requests == []
