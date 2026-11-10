"""Receiver-side settings I/O and safe infrastructure failure translation."""

import asyncio

from pydantic import ValidationError
from pydantic_settings import SettingsError
from runengine.invocation.errors import InvocationInfrastructureError

from lumora.async_work import await_owned
from lumora.bootstrap.settings.interaction_settings import InteractionSettings


async def load_receiver_settings[Settings: InteractionSettings](kind: type[Settings]) -> Settings:
    try:
        return await await_owned(asyncio.to_thread(kind))
    except OSError, SettingsError, ValidationError:
        raise InvocationInfrastructureError(
            "Receiving service configuration is unavailable", retryable=False
        ) from None
