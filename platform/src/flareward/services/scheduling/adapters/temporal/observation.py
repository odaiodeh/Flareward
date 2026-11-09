"""Borrow the SDK RPC facade for root liveness without starting runs or owning executors."""

from runengine.adapters.coordination.config import TemporalHostConfig
from runengine.adapters.coordination.temporal.host import TemporalRunHost
from temporalio.client import Client

from flareward.executions.adapters.run_engine.outbound.errors import engine_errors
from flareward.executions.adapters.run_engine.outbound.location import host_location
from flareward.executions.adapters.run_engine.outbound.status import execution_phase
from flareward.executions.domain.models import ExecutionPhase
from flareward.services.scheduling.adapters.temporal.handles import get_handle


class TemporalExecutionObservation:
    def __init__(self, config: TemporalHostConfig, client: Client) -> None:
        # The SDK facade only borrows this connection. No builder/worker/environment
        # lifecycle or native start method is used by this adapter.
        self._rpc = TemporalRunHost(config, client=client)
        self._location = host_location(config)

    @property
    def location(self) -> str:
        return self._location

    async def status(self, execution_id: str) -> ExecutionPhase:
        async with engine_errors():
            return execution_phase(
                (await (await get_handle(self._rpc, execution_id)).status()).phase
            )
