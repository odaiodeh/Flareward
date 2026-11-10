"""HITL capability mixin for agent nodes."""

import logging
from typing import Any

from lumora.executions.context import ExecutionContextHolder
from lumora.services.interactions.tools.models import HITLMode, ToolApprovalPolicy
from lumora.services.interactions.tools.ports import ApprovalGate

logger = logging.getLogger(__name__)


class HITLCapableMixin:
    """Mixin for nodes that support HITL tool-call gating."""

    def __init__(
        self,
        *,
        hitl_mode: HITLMode = HITLMode.SKIP,
        execution_holder: ExecutionContextHolder | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._hitl_mode = HITLMode(hitl_mode) if isinstance(hitl_mode, str) else hitl_mode
        self._execution_holder = execution_holder
        self._approval_gate: ApprovalGate | None = None
        self._approval_policy: ToolApprovalPolicy | None = None

    # ── SupportsHITL protocol ─────────────────────────────────

    def set_approval_gate(self, gate: ApprovalGate | None) -> None:
        self._approval_gate = gate

    def set_approval_policy(self, policy: ToolApprovalPolicy | None) -> None:
        self._approval_policy = policy

    # ── Shared decision logic ─────────────────────────────────

    def _should_activate_hitl(self) -> bool:
        """Decide whether HITL gating is active for this execution run."""
        if self._hitl_mode == HITLMode.SKIP:
            return False
        requested = self._hitl_mode == HITLMode.ASK or (
            self._execution_holder is not None and self._execution_holder.context.hitl_enabled
        )
        if not requested:
            return False
        if self._approval_gate is None or self._approval_policy is None:
            raise RuntimeError(
                "Human approval is required but no approval gate/policy was configured"
            )
        return True

    @property
    def hitl_session_id(self) -> str:
        """Session ID from the execution context (filled at runtime)."""
        if self._execution_holder is None:
            return ""
        try:
            return self._execution_holder.context.session_id
        except RuntimeError, AttributeError:
            return ""
