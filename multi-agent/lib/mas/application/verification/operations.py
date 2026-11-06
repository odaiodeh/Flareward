"""Typed workflow calls depend on a verification capability, not HTTP or Mongo."""

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field

from mas.application.elements.operation import BaseOperation, OperationContext
from mas.application.verification.models import StartVerification, VerificationView
from mas.application.verification.ports import VerificationGateway
from mas.domain.verification import VerificationId, VerificationSubject


class RequestVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    subject: VerificationSubject
    policy: str = Field(min_length=1, max_length=128)


class VerificationHandle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    plan_id: VerificationId


class RequestVerificationOperation(BaseOperation[RequestVerification, VerificationView]):
    def __init__(self, gateway: VerificationGateway) -> None:
        self._gateway = gateway

    async def execute(
        self, request: RequestVerification, context: OperationContext
    ) -> VerificationView:
        if not context.execution.execution_id or not context.execution.root_execution_id:
            raise ValueError("Verification requires execution identity")
        key = hashlib.sha256(
            json.dumps(
                [context.execution.execution_id, context.key], separators=(",", ":")
            ).encode()
        ).hexdigest()
        return await self._gateway.start(
            StartVerification(key=key, subject=request.subject, policy=request.policy)
        )


class InspectVerificationOperation(BaseOperation[VerificationHandle, VerificationView]):
    def __init__(self, gateway: VerificationGateway) -> None:
        self._gateway = gateway

    async def execute(
        self, request: VerificationHandle, context: OperationContext
    ) -> VerificationView:
        return await self._gateway.inspect(request.plan_id)


class CancelVerificationOperation(BaseOperation[VerificationHandle, VerificationView]):
    def __init__(self, gateway: VerificationGateway) -> None:
        self._gateway = gateway

    async def execute(
        self, request: VerificationHandle, context: OperationContext
    ) -> VerificationView:
        return await self._gateway.cancel(request.plan_id)
