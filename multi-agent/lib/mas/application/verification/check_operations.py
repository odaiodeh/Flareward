"""Ordinary operations request trusted checks without acquiring verifier authority."""

from mas.application.elements.operation import BaseOperation, OperationContext
from mas.application.verification.check_ports import CheckRunGateway, CheckRunHandle, StartCheckRun
from mas.domain.check_runs import CheckRun


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
