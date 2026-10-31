"""Async composition root owning server clients and execution reconciliation."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from importlib import import_module

import httpx
from inbound.http_api.authentication import DevelopmentAuthenticator, SessionAuthenticator
from inbound.http_api.dependencies import HttpServices
from inbound.run_engine.interactions import cancel_waits
from mas.application.collaboration.editing import TeamEditService
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.catalog.service import CatalogService
from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.application.elements.construction.secrets import ConfigurationSecrets
from mas.application.sharing.notifications import ShareNotifications
from mas.blueprints.placement import BlueprintPlacementService
from mas.core.async_work import await_owned
from mas.execution.ports import ExecutionLocationUnavailable, ExecutionMissing
from mas.execution.service import ExecutionService
from mas.interactions.service import InteractionService
from mas.programs.blueprints import BlueprintProgramImporter, BlueprintProgramService
from mas.programs.registry import ApplicationRegistry
from mas.programs.service import ProgramService
from mas.scheduling.programs import ProgramScheduleService
from mas.session.execution.blueprint_sessions import BlueprintSessionService
from mas.session.execution.program_sessions import ProgramSessionService
from mas.session.execution.queries import SessionQueryService
from outbound.actions.providers.rag.client import RagActionClient
from outbound.crypto import FieldCipher
from outbound.interactions.redis_store import RedisInteractionStore
from outbound.memory.execution_repository import MemoryExecutionRepository
from outbound.memory.program_repository import MemoryProgramRepository
from outbound.memory.session_store import MemorySessionStore
from outbound.memory.share_notifications import MemoryShareNotifications
from outbound.mongo.action_settings import MongoActionSettings
from outbound.mongo.configuration_secrets import MongoConfigurationSecrets
from outbound.mongo.execution_repository import MongoExecutionRepository
from outbound.mongo.program_repository import MongoProgramRepository
from outbound.mongo.session_store import MongoSessionStore
from outbound.mongo.share_notifications import MongoShareNotifications
from outbound.redis.edit_locks import RedisEditLockStore
from outbound.redis_client import owned_redis
from outbound.run_engine.compiler import ProgramCompiler
from outbound.run_engine.gateway import RunEngineGateway
from outbound.run_engine.location import host_location
from outbound.run_engine.profiles import profile_catalog
from pymongo import AsyncMongoClient
from runengine.adapters.coordination.config import LocalHostConfig, TemporalHostConfig
from runengine.bootstrap.hosts import RunHostBuilder
from runengine.core.refs import FunctionRef

from bootstrap.actions import build_actions
from bootstrap.elements import installed_elements
from bootstrap.receiver import element_runtime
from config.execution_policies import load_execution_profiles
from config.interaction_settings import InteractionBackend
from config.platform_settings import AuthenticationKind, PlatformSettings, StorageKind
from config.receiver_settings import CredentialBackend
from config.tracing_settings import TracingBackend

logger = logging.getLogger(__name__)


async def reconcile(
    executions: ExecutionService,
    sessions: ProgramSessionService,
    stop: asyncio.Event,
    interval: float,
) -> None:
    while not stop.is_set():
        try:
            await executions.reconcile_pending()
            await sessions.reconcile_pending()
        except Exception:
            # Supervisor boundary: retain intents and retry on the next pass.
            logger.exception("Execution reconciliation failed; pending records remain recoverable")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            continue


@asynccontextmanager
async def compose_platform(
    settings: PlatformSettings,
    *,
    elements: ElementRegistry | None = None,
    applications: ApplicationRegistry | None = None,
) -> AsyncIterator[HttpServices]:
    settings = PlatformSettings.model_validate(dict(settings))
    profiles = await load_execution_profiles(settings)
    async with AsyncExitStack() as resources:
        if elements is None:
            elements = installed_elements(settings.element_modules)
        if applications is None:
            applications = ApplicationRegistry()
            for name in settings.application_modules:
                module = import_module(name)
                for registration in module.APPLICATION_PROGRAMS:
                    applications.register(registration)
        database = None
        if (
            settings.storage == StorageKind.MONGO
            or settings.configuration_secrets
            or settings.tracing != TracingBackend.DISABLED
            or settings.library
        ):
            mongo = AsyncMongoClient(
                settings.mongo_uri.get_secret_value(), serverSelectionTimeoutMS=5000
            )
            resources.push_async_callback(mongo.close)
            await mongo.admin.command("ping")
            database = mongo[settings.mongo_database]
        if settings.storage == StorageKind.MONGO:
            programs_repository = MongoProgramRepository(database)
            execution_repository = MongoExecutionRepository(database)
            await execution_repository.initialize()
            session_store = MongoSessionStore(database)
            await session_store.initialize()
            notifications_repository = MongoShareNotifications(database, settings.shares_collection)
            await notifications_repository.initialize()
        else:
            programs_repository = MemoryProgramRepository()
            execution_repository = MemoryExecutionRepository()
            session_store = MemorySessionStore()
            notifications_repository = MemoryShareNotifications()
        secret_store = None
        if settings.configuration_secrets:
            secret_store = MongoConfigurationSecrets(
                database, FieldCipher(settings.credential_encryption_key.get_secret_value())
            )
        configuration = ConfigurationSecrets(elements, secret_store)
        action_auth = None
        if settings.credentials == CredentialBackend.MONGO:
            action_auth = await resources.enter_async_context(
                import_module("bootstrap.credentials").receiver_auth(settings)
            )
        actions = build_actions(
            auth=action_auth,
            settings=MongoActionSettings(
                mongo[settings.admin_config_database][settings.admin_config_collection]
            )
            if database is not None
            else None,
            rag=RagActionClient(str(settings.rag_base_url), timeout=settings.http_timeout),
        )
        programs = ProgramService(
            programs_repository,
            applications,
            ElementBundleResolver(elements),
            configuration,
        )
        blueprint_programs = None
        authoring = None
        resource_authoring = None
        resource_inspection = None
        blueprint_inspection = None
        graph_analysis = None
        blueprint_queries = None
        if settings.library:
            factory = import_module("bootstrap.library").compose_library
            library = await resources.enter_async_context(
                factory(settings, elements, database, configuration)
            )
            blueprint_programs = BlueprintProgramService(
                library.source, BlueprintProgramImporter(elements), programs
            )
            authoring = library.authoring
            resource_authoring = library.resources
            resource_inspection = library.inspection
            blueprint_inspection = library.blueprint_inspection
            graph_analysis = library.graph_analysis
            blueprint_queries = library.blueprint_queries
        interaction_store = None
        if settings.interactions == InteractionBackend.REDIS:
            interaction_client = await resources.enter_async_context(
                owned_redis(
                    settings.redis_uri.get_secret_value(),
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
            )
            await interaction_client.ping()
            interaction_store = RedisInteractionStore(
                interaction_client,
                ttl=settings.interaction_ttl,
                max_events=settings.max_stream_events,
            )
        host = RunHostBuilder.create(settings.host)
        resources.push_async_callback(host.shutdown)
        receiver = None
        if settings.receiver_module:
            receiver = FunctionRef.from_callable(
                import_module(settings.receiver_module).element_runtime
            )
        elif (
            interaction_store is not None
            or settings.credentials != CredentialBackend.DISABLED
            or settings.configuration_secrets
        ):
            receiver = FunctionRef.from_callable(element_runtime)
        compiler = ProgramCompiler(
            programs,
            elements,
            applications,
            profiles,
            settings.default_execution_profile,
            receiver=receiver,
            cancellation=FunctionRef.from_callable(cancel_waits) if interaction_store else None,
        )
        placement = (
            BlueprintPlacementService(
                authoring, library.resolution, BlueprintProgramImporter(elements), compiler
            )
            if settings.library
            else None
        )
        handles = None
        if isinstance(settings.host, TemporalHostConfig):
            handles = partial(import_module("outbound.temporal.run_handles").get_handle, host)
        gateway = RunEngineGateway(
            host, compiler, location=host_location(settings.host), handles=handles
        )
        executions = ExecutionService(
            programs,
            execution_repository,
            gateway,
            interaction_store,
        )
        sessions = ProgramSessionService(session_store, programs, executions, interaction_store)
        schedules = None
        if isinstance(settings.host, TemporalHostConfig):
            schedule_backend = import_module(
                "outbound.temporal.program_schedules"
            ).TemporalProgramSchedules
            admission = import_module("bootstrap.scheduling").admit_scheduled_execution
            schedules = ProgramScheduleService(
                programs,
                gateway,
                schedule_backend(settings.host, FunctionRef.from_callable(admission)),
            )
        if settings.authentication == AuthenticationKind.DEVELOPMENT:
            authenticate = DevelopmentAuthenticator(settings.development_user)
        else:
            redis = await resources.enter_async_context(
                owned_redis(settings.redis_uri.get_secret_value(), decode_responses=True)
            )
            http = await resources.enter_async_context(
                httpx.AsyncClient(timeout=settings.http_timeout)
            )
            authenticate = SessionAuthenticator(
                redis,
                http,
                secret_key=settings.secret_key.get_secret_value(),
                identity_url=settings.identity_url,
                internal_token=settings.internal_auth_token.get_secret_value(),
            )

        team_editing = None
        if settings.edit_locks:
            lock_client = await resources.enter_async_context(
                owned_redis(settings.redis_uri.get_secret_value(), decode_responses=True)
            )
            await lock_client.ping()
            team_editing = TeamEditService(
                RedisEditLockStore(lock_client),
                resource_authoring,
                authoring,
                ttl=settings.edit_lock_ttl,
            )

        async def release_local_waits() -> None:
            if not isinstance(settings.host, LocalHostConfig):
                return
            cursor = None
            while True:
                records = await execution_repository.pending(100, after_execution_id=cursor)
                if not records:
                    return
                for record in records:
                    cursor = record.execution_id
                    try:
                        await executions.cancel(record.execution_id, record.owner)
                    except ExecutionMissing, ExecutionLocationUnavailable:
                        logger.warning(
                            "Local execution %s is unavailable to this host", record.execution_id
                        )

        resources.push_async_callback(release_local_waits)
        stop = asyncio.Event()
        task = asyncio.create_task(
            reconcile(executions, sessions, stop, settings.reconcile_interval)
        )

        async def stop_reconciliation() -> None:
            stop.set()
            await await_owned(task)

        resources.push_async_callback(stop_reconciliation)
        yield HttpServices(
            programs,
            executions,
            authenticate,
            sessions,
            InteractionService(executions, interaction_store)
            if interaction_store is not None
            else None,
            blueprint_programs,
            authoring,
            resource_authoring,
            resource_inspection,
            blueprint_inspection,
            graph_analysis,
            schedules,
            CatalogService(elements),
            blueprint_queries,
            BlueprintSessionService(blueprint_programs, programs, sessions)
            if blueprint_programs is not None
            else None,
            SessionQueryService(sessions, authoring),
            execution_profiles=profile_catalog(profiles, settings.default_execution_profile),
            blueprint_placement=placement,
            team_editing=team_editing,
            actions=actions,
            share_notifications=ShareNotifications(notifications_repository),
        )
