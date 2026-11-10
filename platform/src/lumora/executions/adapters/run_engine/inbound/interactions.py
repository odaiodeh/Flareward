"""Installed invocation effect for releasing receiver waits during program-side cancellation."""

from lumora.bootstrap.settings.interaction_settings import (
    InteractionBackend,
    InteractionSettings,
)
from lumora.executions.adapters.run_engine.inbound.settings import load_receiver_settings
from lumora.executions.adapters.run_engine.outbound.errors import application_errors
from lumora.services.connections.adapters.redis import owned_redis
from lumora.services.interactions.adapters.redis_store import RedisInteractionStore

__runengine_contract__ = "lumora-interactions-v1"


@application_errors
async def cancel_waits(*, execution_id: str, root_execution_id: str) -> None:
    settings = await load_receiver_settings(InteractionSettings)
    if settings.interactions == InteractionBackend.DISABLED:
        return
    async with owned_redis(
        settings.redis_uri.get_secret_value(),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    ) as client:
        await RedisInteractionStore(client, ttl=settings.interaction_ttl).cancel(
            execution_id, root_execution_id=root_execution_id
        )
