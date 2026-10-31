"""Typed configuration for the HITL execution handler."""

from dataclasses import dataclass

from mas.application.ports.tool import BaseTool
from mas.core.hitl.models import ToolApprovalPolicy
from mas.core.hitl.ports import ApprovalGate


@dataclass(frozen=True)
class HITLHandlerConfig:
    """All dependencies required by ``HITLExecutionHandler``."""

    gate: ApprovalGate
    policy: ToolApprovalPolicy
    tool_registry: dict[str, BaseTool]
    node_uid: str
    node_display_name: str
    session_id: str
