"""Resolve optional tracing locally and drain its resources through cancellation."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractContextManager, ExitStack, asynccontextmanager
from importlib import import_module

from runengine.invocation.errors import InvocationInfrastructureError

from lumora.async_work import await_owned
from lumora.bootstrap.settings.receiver_settings import ReceiverSettings
from lumora.bootstrap.settings.tracing_settings import TracingBackend
from lumora.services.tracing import NoOpTracingService, TracingService


@asynccontextmanager
async def receiver_tracing(settings: ReceiverSettings) -> AsyncIterator[TracingService]:
    if settings.tracing == TracingBackend.DISABLED:
        yield NoOpTracingService()
        return
    owner = ExitStack()

    def create() -> TracingService:
        try:
            factory = import_module("lumora.services.tracing.adapters.langfuse.otel").owned_tracing
        except ImportError:
            raise InvocationInfrastructureError(
                "Tracing adapter is unavailable", retryable=False
            ) from None
        manager: AbstractContextManager[TracingService] = factory(
            public_key=settings.langfuse_public_key.get_secret_value(),
            secret_key=settings.langfuse_secret_key.get_secret_value(),
            base_url=str(settings.langfuse_base_url),
            timeout_seconds=settings.tracing_timeout,
        )
        return owner.enter_context(manager)

    try:
        yield await await_owned(asyncio.to_thread(create))
    finally:
        await await_owned(asyncio.to_thread(owner.close))
