"""Per-invocation receiver composition owns transport clients and existing node capabilities."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from importlib import import_module
from typing import Any

from pydantic import JsonValue
from pymongo import AsyncMongoClient

from flareward.async_work import await_owned
from flareward.bootstrap.settings.interaction_settings import InteractionBackend
from flareward.bootstrap.settings.receiver_settings import CredentialBackend, ReceiverSettings
from flareward.bootstrap.tracing import receiver_tracing
from flareward.elements.configuration.platform import PlatformConfig
from flareward.elements.construction.context import ElementBuildContext
from flareward.elements.construction.runtime import ElementRuntime
from flareward.executions.adapters.run_engine.inbound.settings import load_receiver_settings
from flareward.executions.context import ExecutionContextHolder
from flareward.programs.graph.runtime_binder import NodeRuntimeBindings
from flareward.resources.adapters.mongo.configuration_secrets import MongoConfigurationSecrets
from flareward.services.auth.adapters.crypto import FieldCipher
from flareward.services.connections.adapters.redis import owned_redis
from flareward.services.interactions.adapters.buffered_channel import BufferedChannel
from flareward.services.interactions.adapters.redis_gate import RedisApprovalGate
from flareward.services.interactions.adapters.redis_store import RedisInteractionStore
from flareward.services.interactions.adapters.wire import canonical, root_key
from flareward.services.interactions.models import initial_rules
from flareward.services.interactions.tools.models import HITLConfig, ToolApprovalPolicy


@asynccontextmanager
async def element_runtime(holder: ExecutionContextHolder) -> AsyncIterator[ElementRuntime]:
    settings = await load_receiver_settings(ReceiverSettings)
    async with AsyncExitStack() as resources:
        build = ElementBuildContext(
            execution_ctx=holder,
            tracing_service=await resources.enter_async_context(receiver_tracing(settings)),
            platform_config=PlatformConfig(shared_storage=settings.shared_storage),
        )
        if settings.workflow_credential_directory is not None:
            build.workflow_credentials = import_module(
                "flareward.services.access.adapters.workflow_credentials"
            ).FileWorkflowCredentials(settings.workflow_credential_directory)
        if settings.configuration_secrets:
            mongo: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
                settings.mongo_uri.get_secret_value(), serverSelectionTimeoutMS=5000
            )
            resources.push_async_callback(mongo.close)
            build.configuration_secrets = MongoConfigurationSecrets(
                mongo[settings.mongo_database],
                FieldCipher(settings.credential_encryption_key.get_secret_value()),
            )
        if settings.credentials == CredentialBackend.MONGO:
            factory = import_module("flareward.bootstrap.credentials").receiver_auth
            build.auth_service = await resources.enter_async_context(factory(settings))
        if settings.interactions == InteractionBackend.DISABLED:
            yield ElementRuntime(build)
            return
        client = await resources.enter_async_context(
            owned_redis(
                settings.redis_uri.get_secret_value(),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        )
        store = RedisInteractionStore(
            client, ttl=settings.interaction_ttl, max_events=settings.max_stream_events
        )
        context = holder.context
        await client.set(
            root_key(context.root_execution_id) + ":rules",
            canonical(initial_rules(context).to_dict()),
            ex=settings.interaction_ttl,
            nx=True,
        )

        async def publish(data: dict[str, JsonValue]) -> None:
            await store.publish(context.root_execution_id, context.execution_id, data)

        channel = BufferedChannel(context, publish, capacity=settings.stream_buffer_capacity)
        drain = asyncio.create_task(channel.drain())

        async def close_channel() -> None:
            channel.close()
            await await_owned(drain)

        resources.push_async_callback(close_channel)
        cancelled = asyncio.Event()
        gate = RedisApprovalGate(
            client,
            context,
            cancelled,
            HITLConfig(enabled=True, timeout_seconds=settings.approval_timeout),
            ttl=settings.interaction_ttl,
            max_events=settings.max_stream_events,
        )
        yield ElementRuntime(
            build,
            NodeRuntimeBindings(
                channel=channel, approval_gate=gate, approval_policy=ToolApprovalPolicy()
            ),
            cancel=cancelled.set,
        )
