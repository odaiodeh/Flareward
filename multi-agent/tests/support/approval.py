"""A deterministic existing-style node exercises real approval and streaming capabilities."""

import json

from mas.application.capabilities.hitl_capable import HITLCapableMixin
from mas.application.elements.factory import BaseFactory
from mas.application.elements.node import BaseNode
from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.element_deps import ElementBuildContext
from mas.core.enums import ResourceCategory
from mas.core.hitl.models import (
    ApprovalRequest,
    ApprovalType,
    HITLMode,
    RequestOrigin,
    ToolAccessMode,
)
from mas.graph.state.state_view import StateView
from pydantic import BaseModel, ConfigDict, Field


class ApprovalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requests: int = Field(default=1, ge=1, le=3)
    request_prefix: str = "probe"


class ApprovalProbe(HITLCapableMixin, BaseNode):
    READS = set()
    WRITES = {"output"}

    def __init__(self, deps: ElementBuildContext, count: int, prefix: str) -> None:
        super().__init__(
            hitl_mode=HITLMode.ASK,
            execution_holder=deps.execution_ctx,
            tracing_service=deps.tracing_service,
        )
        self._holder, self._count = deps.execution_ctx, count
        self._prefix = prefix

    async def run(self, state: StateView) -> StateView:
        assert self._should_activate_hitl()
        decisions = []
        context = self._holder.context
        for index in range(self._count):
            response = await self._approval_gate.request_approval(
                ApprovalRequest(
                    f"{self._prefix}-{index}",
                    ApprovalType.TOOL_EXECUTION,
                    RequestOrigin(self.uid, self.display_name, context.session_id),
                    "fixture-write",
                    {"index": index},
                    "Deterministic write approval",
                    ToolAccessMode.WRITE,
                )
            )
            decisions.append(response.decision.value)
            self._stream({"type": "fixture_step", "approved": response.approved, "index": index})
            if not response.approved:
                break
        state["output"] = json.dumps(
            {
                "decisions": decisions,
                "execution_id": context.execution_id,
                "credential_user": context.credential_user_id(),
            }
        )
        return state


class ApprovalFactory(BaseFactory):
    def accepts(self, cfg, element_type):
        return element_type == "platform_approval"

    def create(self, cfg, **dependencies):
        return ApprovalProbe(dependencies["deps"], cfg.requests, cfg.request_prefix)


class ApprovalSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_approval"
    name = "Approval probe"
    description = "Deterministic native streaming and existing HITL contract verification"
    config_schema = ApprovalConfig
    factory_cls = ApprovalFactory
    reads = ApprovalProbe.total_reads()
    writes = ApprovalProbe.total_writes()
