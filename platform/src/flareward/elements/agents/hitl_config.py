"""Typed configuration for the HITL execution handler."""

from dataclasses import dataclass

from flareward.elements.ports.tool import BaseTool
from flareward.services.interactions.tools.models import ToolApprovalPolicy
from flareward.services.interactions.tools.ports import ApprovalGate


@dataclass(frozen=True)
class HITLHandlerConfig:
    """All dependencies required by ``HITLExecutionHandler``."""

    gate: ApprovalGate
    policy: ToolApprovalPolicy
    tool_registry: dict[str, BaseTool]
    node_uid: str
    node_display_name: str
    session_id: str
