"""Async composition root owning server clients and execution reconciliation."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from importlib import import_module
from typing import Any

import httpx
from pymongo import AsyncMongoClient
from runengine.adapters.coordination.config import LocalHostConfig, TemporalHostConfig
from runengine.bootstrap.hosts import RunHostBuilder
from runengine.core.refs import FunctionRef

from flareward.api.authentication import DevelopmentAuthenticator, SessionAuthenticator
from flareward.api.dependencies import Authenticator, HttpServices
from flareward.api.verification_auth import VerifierAuthenticator
from flareward.async_work import await_owned
from flareward.bootstrap.actions import build_actions
from flareward.bootstrap.administration import settings_sections
from flareward.bootstrap.elements import installed_elements
from flareward.bootstrap.programs import installed_applications
from flareward.bootstrap.receiver import element_runtime
from flareward.bootstrap.settings.execution_policies import load_execution_profiles
from flareward.bootstrap.settings.interaction_settings import InteractionBackend
from flareward.bootstrap.settings.platform_settings import (
    AuthenticationKind,
    PlatformSettings,
    StorageKind,
)
from flareward.bootstrap.settings.receiver_settings import CredentialBackend
from flareward.bootstrap.settings.tracing_settings import TracingBackend
from flareward.bootstrap.work_budgets import admit_work
from flareward.bootstrap.workflow_access import WorkflowAccessComponents
from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.catalog.service import CatalogService
from flareward.elements.construction.secrets import ConfigurationSecrets
from flareward.elements.construction.snapshots import SavedResourceResolver
from flareward.executions.access import ExecutionGrantAccess
from flareward.executions.adapters.memory.execution_repository import MemoryExecutionRepository
from flareward.executions.adapters.mongo.event_sources import MongoEventSources
from flareward.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from flareward.executions.adapters.run_engine.inbound.interactions import cancel_waits
from flareward.executions.adapters.run_engine.outbound.compiler import ProgramCompiler
from flareward.executions.adapters.run_engine.outbound.gateway import RunEngineGateway
from flareward.executions.adapters.run_engine.outbound.location import host_location
from flareward.executions.adapters.run_engine.outbound.profiles import profile_catalog
from flareward.executions.events import ProgramEventService
from flareward.executions.ports import (
    ExecutionLocationUnavailable,
    ExecutionMissing,
    ExecutionRepository,
)
from flareward.executions.profile_access import ExecutionProfileAccess
from flareward.executions.service import ExecutionService
from flareward.programs.adapters.memory.program_repository import MemoryProgramRepository
from flareward.programs.adapters.mongo.program_repository import MongoProgramRepository
from flareward.programs.blueprints import BlueprintProgramImporter, BlueprintProgramService
from flareward.programs.ports import ProgramRepository
from flareward.programs.registry import ApplicationRegistry
from flareward.programs.service import ProgramService
from flareward.programs.templates.placement import BlueprintPlacementService
from flareward.resources.adapters.mongo.configuration_secrets import MongoConfigurationSecrets
from flareward.resources.builtins import BuiltinAdministration
from flareward.services.access.administrators import AdministratorPolicy
from flareward.services.access.maintenance import CredentialMaintenance
from flareward.services.administration.adapters.mongo.action_settings import MongoActionSettings
from flareward.services.administration.adapters.mongo.administrators import (
    MongoAdministratorDirectory,
)
from flareward.services.administration.adapters.mongo.settings import MongoSettingsRepository
from flareward.services.administration.service import ConfigurationService
from flareward.services.artifacts.access import ArtifactAccessService
from flareward.services.artifacts.adapters.access import SQLiteArtifactAccessRepository
from flareward.services.artifacts.adapters.filesystem import FileArtifactRepository
from flareward.services.artifacts.service import ArtifactService
from flareward.services.auth.adapters.crypto import FieldCipher
from flareward.services.auth.adapters.redis_sessions import RedisSessionReader
from flareward.services.collaboration.adapters.redis.edit_locks import RedisEditLockStore
from flareward.services.collaboration.editing import TeamEditService
from flareward.services.connections.adapters.redis import owned_redis
from flareward.services.identity.adapters.memory.consent import MemoryConsents
from flareward.services.identity.adapters.mongo.consent import MongoConsents
from flareward.services.identity.consent import ConsentService
from flareward.services.interactions.adapters.redis_store import RedisInteractionStore
from flareward.services.interactions.service import InteractionService
from flareward.services.reporting.adapters.mongo.reporting import MongoReportingReader
from flareward.services.reporting.service import ReportingService
from flareward.services.reviews.adapters.executions import ExecutionReviews
from flareward.services.reviews.adapters.mongo.reviews import MongoReviewRepository
from flareward.services.reviews.service import ReviewService
from flareward.services.scheduling.programs import ProgramScheduleService
from flareward.services.sessions.adapters.memory.session_store import MemorySessionStore
from flareward.services.sessions.adapters.mongo.session_store import MongoSessionStore
from flareward.services.sessions.execution.blueprint_sessions import BlueprintSessionService
from flareward.services.sessions.execution.program_sessions import ProgramSessionService
from flareward.services.sessions.execution.queries import SessionQueryService
from flareward.services.sessions.execution.session_store import SessionStore
from flareward.services.sharing.adapters.memory.share_notifications import MemoryShareNotifications
from flareward.services.sharing.adapters.mongo.share_notifications import MongoShareNotifications
from flareward.services.sharing.notifications import (
    ShareNotifications,
    ShareNotificationsRepository,
)
from flareward.services.verification.adapters.mongo.check_runs import MongoCheckRunRepository
from flareward.services.verification.adapters.mongo.verification_repository import (
    MongoVerificationRepository,
)
from flareward.services.verification.check_service import CheckRunService, RegisteredCheckRunner
from flareward.services.verification.maintenance import CheckJobMaintenance
from flareward.services.verification.models import VerificationAuthority
from flareward.services.verification.program_checks import ProgramCheckRunner
from flareward.services.verification.reports import CheckReportCollector
from flareward.services.verification.service import VerificationService
from plugins.github_actions.github import GitHubActionsCheckRunner
from plugins.github_actions.github_reports import GitHubCheckReports

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
            elements = installed_elements(settings.element_modules, plugins=settings.plugins)
        if applications is None:
            applications = installed_applications(
                settings.application_modules, plugins=settings.plugins
            )
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
                import_module("flareward.bootstrap.credentials").receiver_auth(settings)
            )
        actions = build_actions(
            auth=action_auth,
            settings=MongoActionSettings(
                mongo[settings.admin_config_database][settings.admin_config_collection]
            )
            if database is not None
            else None,
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
        configuration_service = None
        if database is not None and administrators is not None:
            settings_repository = MongoSettingsRepository(
                mongo[settings.admin_config_database][settings.admin_config_collection]
            )
            await settings_repository.initialize()
            configuration_service = ConfigurationService(
                settings_repository, administrators, settings_sections(settings.admin_allowed_users)
            )
        consents = ConsentService(
            MongoConsents(database) if database is not None else MemoryConsents()
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
            factory = import_module("flareward.bootstrap.library").compose_library
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
            handles = partial(
                import_module("flareward.services.scheduling.adapters.temporal.handles").get_handle,
                host,
            )
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
                "flareward.services.scheduling.adapters.temporal.programs"
            ).TemporalProgramSchedules
            admission = import_module("flareward.bootstrap.scheduling").admit_scheduled_execution
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
            configuration=configuration_service,
            consents=consents,
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
