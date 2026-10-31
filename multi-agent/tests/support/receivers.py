"""Receiver-local collaborators prove service binding without serializing live objects."""

import asyncio
import json
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from mas.application.capabilities.hitl_capable import HITLCapableMixin
from mas.application.elements.construction.runtime import ElementRuntime
from mas.application.elements.factory import BaseFactory
from mas.application.elements.node import BaseNode
from mas.application.elements.specification import BaseElementSpec
from mas.core.channels import SessionChannel
from mas.core.element_deps import ElementBuildContext
from mas.core.enums import ResourceCategory
from mas.core.execution_context import ExecutionContextHolder
from mas.core.hitl.models import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalType,
    HITLConfig,
    HITLMode,
    RequestOrigin,
    ToolAccessMode,
    ToolApprovalPolicy,
)
from mas.core.hitl.ports import ApprovalGate
from mas.core.platform_config import PlatformConfig
from mas.core.runtime_binder import NodeRuntimeBindings
from mas.core.tracing import NoOpTracingService
from mas.graph.state.state_view import StateView
from pydantic import BaseModel, ConfigDict


def audit(event: str, holder: ExecutionContextHolder) -> None:
    target = os.environ.get("UNIFAI_TEST_RECEIVER_AUDIT")
    if target:
        with Path(target).open("a", encoding="utf-8") as output:
            output.write(
                json.dumps({"event": event, "execution_id": holder.context.execution_id}) + "\n"
            )


class AuditChannel(SessionChannel):
    def __init__(self, holder: ExecutionContextHolder) -> None:
        self._holder = holder
        self._closed = False

    @property
    def session_id(self) -> str:
        return self._holder.context.session_id

    def emit(self, data) -> None:
        if not self._closed:
            audit("stream." + data["type"], self._holder)

    def is_active(self) -> bool:
        return not self._closed

    def close(self, *, cancelled: bool = False) -> None:
        self._closed = True
        audit("channel.closed", self._holder)


class AuditTracing(NoOpTracingService):
    def __init__(self, holder: ExecutionContextHolder) -> None:
        self._holder = holder

    @contextmanager
    def trace_session(self, session_id, user_id="", metadata=None):
        audit("trace.session", self._holder)
        with super().trace_session(session_id, user_id, metadata) as handle:
            yield handle

    def flush(self) -> None:
        audit("trace.flushed", self._holder)


class AuditCredential:
    def __init__(self, resolve_user: Callable[[], str]) -> None:
        self.resolve_user = resolve_user


class AuditAuth:
    def bind_lazy(self, resolve_user, server_id, scheme_type):
        return AuditCredential(resolve_user)


class AuditGate(ApprovalGate):
    async def _send_and_wait(self, request, timeout):
        return ApprovalResponse(request.request_id, ApprovalDecision.APPROVE)


@asynccontextmanager
async def element_runtime(holder: ExecutionContextHolder) -> AsyncIterator[ElementRuntime]:
    channel = AuditChannel(holder)
    audit("opened", holder)
    try:
        yield ElementRuntime(
            build=ElementBuildContext(
                execution_ctx=holder,
                auth_service=AuditAuth(),
                tracing_service=AuditTracing(holder),
                platform_config=PlatformConfig(shared_storage="/receiver-owned"),
            ),
            bindings=NodeRuntimeBindings(
                channel=channel,
                approval_gate=AuditGate(HITLConfig(enabled=True)),
                approval_policy=ToolApprovalPolicy(),
            ),
        )
    finally:
        await asyncio.to_thread(channel.close)
        audit("closed", holder)


class ContextConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_identifier: str = "test-auth-server"
    scheme_type: str = "oauth2"


class ContextNode(HITLCapableMixin, BaseNode):
    READS = set()
    WRITES = {"output"}

    def __init__(self, deps: ElementBuildContext, credential: AuditCredential) -> None:
        super().__init__(hitl_mode=HITLMode.ASK, execution_holder=deps.execution_ctx)
        self._deps = deps
        self._credential = credential

    async def run(self, state: StateView) -> StateView:
        context = self._deps.execution_ctx.context
        assert self._should_activate_hitl()
        response = await self._approval_gate.request_approval(
            ApprovalRequest(
                request_id="fixture-approval",
                type=ApprovalType.TOOL_EXECUTION,
                origin=RequestOrigin(self.uid, self.display_name, context.session_id),
                tool_name="fixture-write",
                tool_args={},
                tool_description="Deterministic verification",
                tool_access_mode=ToolAccessMode.WRITE,
            )
        )
        state["output"] = json.dumps(
            {
                "context": context.model_dump(mode="json"),
                "credential_user": self._credential.resolve_user(),
                "storage": self._deps.platform_config.shared_storage,
                "approved": response.approved,
            }
        )
        return state


class ContextFactory(BaseFactory):
    def accepts(self, cfg: ContextConfig, element_type: str) -> bool:
        return element_type == "receiver_context"

    def create(self, cfg: ContextConfig, **dependencies) -> ContextNode:
        return ContextNode(dependencies["deps"], dependencies["auth_credential"])


class ContextSpec(BaseElementSpec):
    category = ResourceCategory.NODE
    type_key = "receiver_context"
    name = "Receiver context"
    description = "Deterministic receiver service and execution identity verification"
    config_schema = ContextConfig
    factory_cls = ContextFactory
    reads = ContextNode.total_reads()
    writes = ContextNode.total_writes()
