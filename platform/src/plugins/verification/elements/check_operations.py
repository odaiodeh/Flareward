"""Ordinary operations request trusted checks without acquiring verifier authority."""

from flareward.elements.operation import BaseOperation, OperationContext
from flareward.services.verification.check_ports import (
    CheckRunGateway,
    CheckRunHandle,
    StartCheckRun,
)
from flareward.services.verification.domain.check_runs import CheckRun


class StartCheckOperation(BaseOperation[StartCheckRun, CheckRun]):
    def __init__(self, gateway: CheckRunGateway) -> None:
        self._gateway = gateway

    async def execute(self, request: StartCheckRun, context: OperationContext) -> CheckRun:
        return await self._gateway.start_check(request)


class RefreshCheckOperation(BaseOperation[CheckRunHandle, CheckRun]):
    def __init__(self, gateway: CheckRunGateway) -> None:
        self._gateway = gateway

    async def execute(self, request: CheckRunHandle, context: OperationContext) -> CheckRun:
        return await self._gateway.refresh_check(request.intent_id)
