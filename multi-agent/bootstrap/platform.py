"""Async composition root owning server clients and execution reconciliation."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from importlib import import_module
from typing import Any

import httpx
from inbound.http_api.authentication import DevelopmentAuthenticator, SessionAuthenticator
from inbound.http_api.dependencies import Authenticator, HttpServices
from inbound.http_api.verification_auth import VerifierAuthenticator
from inbound.run_engine.interactions import cancel_waits
from mas.application.access.administrators import AdministratorPolicy
from mas.application.access.maintenance import CredentialMaintenance
from mas.application.artifacts.access import ArtifactAccessService
from mas.application.artifacts.service import ArtifactService
from mas.application.collaboration.editing import TeamEditService
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.catalog.service import CatalogService
from mas.application.elements.construction.secrets import ConfigurationSecrets
from mas.application.elements.construction.snapshots import SavedResourceResolver
from mas.application.events import ProgramEventService
from mas.application.execution.access import ExecutionGrantAccess
from mas.application.execution.ports import (
    ExecutionLocationUnavailable,
    ExecutionMissing,
    ExecutionRepository,
)
from mas.application.execution.profile_access import ExecutionProfileAccess
from mas.application.execution.service import ExecutionService
from mas.application.programs.blueprints import BlueprintProgramImporter, BlueprintProgramService
from mas.application.programs.ports import ProgramRepository
from mas.application.programs.registry import ApplicationRegistry
from mas.application.programs.service import ProgramService
from mas.application.reporting.service import ReportingService
from mas.application.resources.builtins import BuiltinAdministration
from mas.application.reviews.service import ReviewService
from mas.application.sharing.notifications import ShareNotifications, ShareNotificationsRepository
from mas.application.verification.check_service import CheckRunService, RegisteredCheckRunner
from mas.application.verification.maintenance import CheckJobMaintenance
from mas.application.verification.models import VerificationAuthority
from mas.application.verification.program_checks import ProgramCheckRunner
from mas.application.verification.reports import CheckReportCollector
from mas.application.verification.service import VerificationService
from mas.blueprints.placement import BlueprintPlacementService
from mas.core.async_work import await_owned
from mas.interactions.service import InteractionService
from mas.scheduling.programs import ProgramScheduleService
from mas.session.execution.blueprint_sessions import BlueprintSessionService
from mas.session.execution.program_sessions import ProgramSessionService
from mas.session.execution.queries import SessionQueryService
from mas.session.execution.session_store import SessionStore
from mas_plugins.ci.github import GitHubActionsCheckRunner
from mas_plugins.ci.github_reports import GitHubCheckReports
from outbound.actions.providers.rag.client import RagActionClient
from outbound.artifacts.access import SQLiteArtifactAccessRepository
from outbound.artifacts.filesystem import FileArtifactRepository
from outbound.auth.redis_sessions import RedisSessionReader
from outbound.crypto import FieldCipher
from outbound.interactions.redis_store import RedisInteractionStore
from outbound.memory.execution_repository import MemoryExecutionRepository
from outbound.memory.program_repository import MemoryProgramRepository
from outbound.memory.session_store import MemorySessionStore
from outbound.memory.share_notifications import MemoryShareNotifications
from outbound.mongo.action_settings import MongoActionSettings
from outbound.mongo.administrators import MongoAdministratorDirectory
from outbound.mongo.check_runs import MongoCheckRunRepository
from outbound.mongo.configuration_secrets import MongoConfigurationSecrets
from outbound.mongo.event_sources import MongoEventSources
from outbound.mongo.execution_repository import MongoExecutionRepository
from outbound.mongo.program_repository import MongoProgramRepository
from outbound.mongo.reporting import MongoReportingReader
from outbound.mongo.reviews import MongoReviewRepository
from outbound.mongo.session_store import MongoSessionStore
from outbound.mongo.share_notifications import MongoShareNotifications
from outbound.mongo.verification_repository import MongoVerificationRepository
from outbound.redis.edit_locks import RedisEditLockStore
from outbound.redis_client import owned_redis
from outbound.reviews.executions import ExecutionReviews
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
from bootstrap.programs import installed_applications
from bootstrap.receiver import element_runtime
from bootstrap.work_budgets import admit_work
from bootstrap.workflow_access import WorkflowAccessComponents
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
    reviews: ReviewService | None = None,
    credentials: tuple[CredentialMaintenance, ...] = (),
    checks: CheckJobMaintenance | None = None,
) -> None:
    while not stop.is_set():
        try:
            await executions.reconcile_pending()
            await sessions.reconcile_pending()
            if reviews is not None:
                await reviews.reconcile()
            for service in credentials:
                await service.reconcile()
            if checks is not None:
                await checks.reconcile()
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
    profile_access = ExecutionProfileAccess(
        profile_catalog(profiles, settings.default_execution_profile), settings.profile_access
    )
    async with AsyncExitStack() as resources:
        if elements is None:
            elements = installed_elements(settings.element_modules)
        if applications is None:
            applications = installed_applications(settings.application_modules)
        database = None
        if (
            settings.storage == StorageKind.MONGO
            or settings.configuration_secrets
            or settings.tracing != TracingBackend.DISABLED
            or settings.library
        ):
            mongo: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
                settings.mongo_uri.get_secret_value(), serverSelectionTimeoutMS=5000
            )
            resources.push_async_callback(mongo.close)
            await mongo.admin.command("ping")
            database = mongo[settings.mongo_database]
        programs_repository: ProgramRepository
        execution_repository: ExecutionRepository
        session_store: SessionStore
        notifications_repository: ShareNotificationsRepository
        if settings.storage == StorageKind.MONGO:
            assert database is not None
            programs_repository = MongoProgramRepository(database)
            await programs_repository.initialize()
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
            assert database is not None
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
        administrators = (
            AdministratorPolicy(
                MongoAdministratorDirectory(
                    mongo[settings.admin_config_database], settings.admin_config_collection
                ),
                settings.admin_allowed_users,
            )
            if database is not None
            else None
        )
        library = None
        blueprint_programs = None
        authoring = None
        resource_authoring = None
        resource_inspection = None
        blueprint_inspection = None
        graph_analysis = None
        blueprint_queries = None
        if settings.library:
            assert administrators is not None
            factory = import_module("bootstrap.library").compose_library
            library = await resources.enter_async_context(
                factory(settings, elements, database, configuration, administrators)
            )
            authoring = library.authoring
            resource_authoring = library.resources
            resource_inspection = library.inspection
            blueprint_inspection = library.blueprint_inspection
            graph_analysis = library.graph_analysis
            blueprint_queries = library.blueprint_queries
        resource_snapshots = (
            SavedResourceResolver(library.resources, elements, configuration) if library else None
        )
        programs = ProgramService(
            programs_repository,
            applications,
            elements,
            configuration,
            resource_snapshots,
        )
        if library is not None:
            blueprint_programs = BlueprintProgramService(
                library.source, BlueprintProgramImporter(elements), programs
            )
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
            or settings.workflow_credential_directory is not None
        ):
            receiver = FunctionRef.from_callable(element_runtime)
        compiler = ProgramCompiler(
            programs,
            elements,
            applications,
            dict(profiles),
            settings.default_execution_profile,
            receiver=receiver,
            cancellation=FunctionRef.from_callable(cancel_waits) if interaction_store else None,
            work_limits=settings.work_limits,
            work_admission=FunctionRef.from_callable(admit_work) if settings.work_limits else None,
            profile_access=profile_access,
        )
        placement = None
        if settings.library:
            assert authoring is not None and library is not None
            placement = BlueprintPlacementService(
                authoring, library.resolution, BlueprintProgramImporter(elements), compiler
            )
        handles = None
        if isinstance(settings.host, TemporalHostConfig):
            handles = partial(import_module("outbound.temporal.run_handles").get_handle, host)
        gateway = RunEngineGateway(
            host, compiler, location=host_location(settings.host), handles=handles
        )
        authority = ExecutionGrantAccess(execution_repository, gateway)
        workflow = await WorkflowAccessComponents.create(settings, database, authority)
        review_access, verification_access = workflow.reviews, workflow.verifications
        executions = ExecutionService(
            programs,
            execution_repository,
            gateway,
            interaction_store,
            submission_timeout_seconds=settings.submission_timeout_seconds,
            workflow_access=workflow.admission,
        )
        program_events = None
        if settings.event_sources_enabled:
            assert database is not None
            event_sources = MongoEventSources(database)
            await event_sources.initialize()
            program_events = ProgramEventService(
                event_sources, programs, executions, gateway, consents=workflow.consents
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
                consents=workflow.consents,
            )
        authenticate: Authenticator
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
                RedisSessionReader(redis),
                http,
                secret_key=settings.secret_key.get_secret_value(),
                identity_url=settings.identity_url,
                internal_token=settings.internal_auth_token.get_secret_value(),
            )

        team_editing = None
        builtin_administration = None
        if settings.edit_locks:
            assert resource_authoring is not None and authoring is not None
            lock_client = await resources.enter_async_context(
                owned_redis(settings.redis_uri.get_secret_value(), decode_responses=True)
            )
            await lock_client.ping()
            edit_store = RedisEditLockStore(lock_client)
            team_editing = TeamEditService(
                edit_store,
                resource_authoring,
                authoring,
                ttl=settings.edit_lock_ttl,
            )
            assert library is not None and administrators is not None
            builtin_administration = BuiltinAdministration(
                library.builtin_repository,
                administrators,
                library.resource_configuration,
                edit_store,
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
        reviews = None
        if settings.reviews_enabled:
            assert database is not None
            review_repository = MongoReviewRepository(database)
            await review_repository.initialize()
            reviews = ReviewService(
                review_repository, ExecutionReviews(executions), settings.review_policies
            )
        artifact_access = None
        artifacts = None
        if settings.artifact_directory is not None:
            artifacts = ArtifactService(
                FileArtifactRepository(settings.artifact_directory),
                max_bytes=settings.artifact_max_bytes,
            )
            access_repository = SQLiteArtifactAccessRepository(
                settings.artifact_directory / ".access"
            )
            await access_repository.initialize()
            artifact_access = ArtifactAccessService(
                access_repository, max_bytes=settings.artifact_max_bytes
            )
        verifications = None
        check_runs = None
        check_maintenance = None
        if settings.verification_enabled:
            assert database is not None
            verification_repository = MongoVerificationRepository(database)
            verifications = VerificationService(
                verification_repository, settings.verification_policies, artifacts=artifacts
            )
            if settings.github_checks or settings.program_checks:
                runners = {}
                if settings.github_checks:
                    check_http = await resources.enter_async_context(
                        httpx.AsyncClient(trust_env=False, follow_redirects=False)
                    )
                    runners.update(
                        {
                            name: RegisteredCheckRunner(
                                binding.policy,
                                GitHubActionsCheckRunner(binding, check_http),
                                GitHubCheckReports(binding, check_http)
                                if binding.report_names
                                else None,
                            )
                            for name, binding in settings.github_checks.items()
                        }
                    )
                for name, program_binding in settings.program_checks.items():
                    driver = ProgramCheckRunner(
                        program_binding, executions, programs, artifacts=artifacts
                    )
                    runners[name] = RegisteredCheckRunner(
                        program_binding.policy, driver, driver, lifecycle=driver
                    )
                check_repository = MongoCheckRunRepository(database)
                await check_repository.initialize()
                check_runs = CheckRunService(
                    check_repository,
                    verifications,
                    runners,
                    reports=CheckReportCollector(artifacts) if artifacts is not None else None,
                )
                check_maintenance = CheckJobMaintenance(
                    check_repository, verifications, runners, authority
                )
        # Start upkeep only after its services exist; stop it before closing their clients.
        stop = asyncio.Event()
        credentials: tuple[CredentialMaintenance, ...] = tuple(
            service
            for service in (
                review_access,
                verification_access,
                workflow.artifacts,
                workflow.retirement,
            )
            if service is not None
        )
        task = asyncio.create_task(
            reconcile(
                executions,
                sessions,
                stop,
                settings.reconcile_interval,
                reviews,
                credentials,
                check_maintenance,
            )
        )

        async def stop_reconciliation() -> None:
            stop.set()
            task.cancel()
            await await_owned(asyncio.gather(task, return_exceptions=True))

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
            execution_profiles=profile_access,
            blueprint_placement=placement,
            team_editing=team_editing,
            builtin_administration=builtin_administration,
            resource_snapshots=resource_snapshots,
            workflow_access=workflow.admission,
            actions=actions,
            share_notifications=ShareNotifications(notifications_repository),
            artifacts=artifacts,
            artifact_access=artifact_access,
            reporting=ReportingService(
                MongoReportingReader(
                    database,
                    blueprints=settings.blueprints_collection,
                    resources=settings.resources_collection,
                ),
                administrators,
                programs_repository,
            )
            if settings.storage == StorageKind.MONGO
            and database is not None
            and administrators is not None
            else None,
            artifact_workflow_access=workflow.artifacts,
            verifications=verifications,
            verification_access=verification_access,
            check_runs=check_runs,
            reviews=reviews,
            review_access=review_access,
            program_events=program_events,
            authenticate_verifier=VerifierAuthenticator(
                {
                    identifier: (
                        binding.credential_sha256,
                        VerificationAuthority(verifier=identifier, owners=binding.owners),
                    )
                    for identifier, binding in settings.verification_authorities.items()
                }
            )
            if verifications is not None
            else None,
        )
