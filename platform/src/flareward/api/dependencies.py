"""Typed HTTP composition boundary and request-scoped identity dependencies."""

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from flareward.api.verification_auth import EvidenceAuthenticator
from flareward.elements.catalog.service import CatalogService
from flareward.elements.construction.snapshots import SavedResourceResolver
from flareward.executions.events import ProgramEventService
from flareward.executions.placement import ProfileAccess
from flareward.executions.service import ExecutionService
from flareward.programs.blueprints import BlueprintProgramService
from flareward.programs.graph.analysis import BlueprintGraphAnalysisService
from flareward.programs.service import ProgramService
from flareward.programs.templates.authoring import BlueprintAuthoringService
from flareward.programs.templates.inspection import BlueprintInspectionService
from flareward.programs.templates.placement import BlueprintPlacementService
from flareward.programs.templates.queries import BlueprintQueryService
from flareward.resources.authoring import ResourceAuthoringService
from flareward.resources.builtins import BuiltinAdministration
from flareward.resources.inspection import ResourceInspectionService
from flareward.services.access.admission import WorkflowAccessService
from flareward.services.actions.service import ActionsService
from flareward.services.administration.service import ConfigurationService
from flareward.services.artifacts.access import ArtifactAccessService
from flareward.services.artifacts.service import ArtifactService
from flareward.services.artifacts.workflow_access import ArtifactWorkflowAccessService
from flareward.services.collaboration.editing import TeamEditService
from flareward.services.identity.consent import ConsentService
from flareward.services.identity.domain import Identity
from flareward.services.interactions.service import InteractionService
from flareward.services.reporting.service import ReportingService
from flareward.services.reviews.access import ReviewAccessService
from flareward.services.reviews.service import ReviewService
from flareward.services.scheduling.programs import ProgramScheduleService
from flareward.services.sessions.execution.blueprint_sessions import BlueprintSessionService
from flareward.services.sessions.execution.program_sessions import ProgramSessionService
from flareward.services.sessions.execution.queries import SessionQueryService
from flareward.services.sharing.notifications import ShareNotifications
from flareward.services.verification.access import VerificationAccessService
from flareward.services.verification.check_service import CheckRunService
from flareward.services.verification.service import VerificationService

type Authenticator = Callable[[Request], Awaitable[Identity]]


@dataclass(frozen=True)
class HttpServices:
    programs: ProgramService
    executions: ExecutionService
    authenticate: Authenticator
    sessions: ProgramSessionService | None = None
    interactions: InteractionService | None = None
    blueprints: BlueprintProgramService | None = None
    authoring: BlueprintAuthoringService | None = None
    resources: ResourceAuthoringService | None = None
    inspection: ResourceInspectionService | None = None
    blueprint_inspection: BlueprintInspectionService | None = None
    graph_analysis: BlueprintGraphAnalysisService | None = None
    schedules: ProgramScheduleService | None = None
    catalog: CatalogService | None = None
    blueprint_queries: BlueprintQueryService | None = None
    blueprint_sessions: BlueprintSessionService | None = None
    session_queries: SessionQueryService | None = None
    execution_profiles: ProfileAccess | None = None
    blueprint_placement: BlueprintPlacementService | None = None
    team_editing: TeamEditService | None = None
    actions: ActionsService | None = None
    share_notifications: ShareNotifications | None = None
    artifacts: ArtifactService | None = None
    artifact_access: ArtifactAccessService | None = None
    artifact_workflow_access: ArtifactWorkflowAccessService | None = None
    verifications: VerificationService | None = None
    authenticate_verifier: EvidenceAuthenticator | None = None
    verification_access: VerificationAccessService | None = None
    check_runs: CheckRunService | None = None
    reviews: ReviewService | None = None
    review_access: ReviewAccessService | None = None
    program_events: ProgramEventService | None = None
    reporting: ReportingService | None = None
    builtin_administration: BuiltinAdministration | None = None
    resource_snapshots: SavedResourceResolver | None = None
    workflow_access: WorkflowAccessService | None = None
    configuration: ConfigurationService | None = None
    consents: ConsentService | None = None


type ServicesFactory = Callable[[], AbstractAsyncContextManager[HttpServices]]


def get_services(request: Request) -> HttpServices:
    services = getattr(request.app.state, "platform", None)
    if not isinstance(services, HttpServices):
        raise HTTPException(status_code=503, detail="Application startup has not completed")
    return services


def get_artifacts(services: Annotated[HttpServices, Depends(get_services)]) -> ArtifactService:
    if services.artifacts is None:
        raise HTTPException(status_code=503, detail="Artifact storage is not configured")
    return services.artifacts


def get_artifact_access(
    services: Annotated[HttpServices, Depends(get_services)],
) -> ArtifactAccessService:
    if services.artifact_access is None:
        raise HTTPException(status_code=503, detail="Artifact access is not configured")
    return services.artifact_access


def get_actions(services: Annotated[HttpServices, Depends(get_services)]) -> ActionsService:
    if services.actions is None:
        raise HTTPException(status_code=503, detail="Actions are not configured")
    return services.actions


def get_share_notifications(
    services: Annotated[HttpServices, Depends(get_services)],
) -> ShareNotifications:
    if services.share_notifications is None:
        raise HTTPException(status_code=503, detail="Sharing notifications are not configured")
    return services.share_notifications


def get_team_editing(services: Annotated[HttpServices, Depends(get_services)]) -> TeamEditService:
    if services.team_editing is None:
        raise HTTPException(status_code=501, detail="Team editing leases are not configured")
    return services.team_editing


def get_blueprint_placement(
    services: Annotated[HttpServices, Depends(get_services)],
) -> BlueprintPlacementService:
    if services.blueprint_placement is None:
        raise HTTPException(status_code=503, detail="Blueprint placement is not configured")
    return services.blueprint_placement


async def authenticated(
    request: Request,
    services: Annotated[HttpServices, Depends(get_services)],
) -> Identity:
    return await services.authenticate(request)


@dataclass(frozen=True)
class HumanPrincipal:
    owner: Identity
    user: Identity


async def human_principal(
    request: Request,
    services: Annotated[HttpServices, Depends(get_services)],
) -> HumanPrincipal:
    """A supplied bearer cannot acquire human authority through a session cookie."""
    if request.headers.get("Authorization") is not None:
        raise HTTPException(401, "Human session required")
    owner = await services.authenticate(request)
    user = getattr(request.state, "authenticated_user", "") or (owner.id if owner.is_user else "")
    if not user:
        raise HTTPException(401, "Human session required")
    return HumanPrincipal(owner, Identity.user(user))


def get_sessions(
    services: Annotated[HttpServices, Depends(get_services)],
) -> ProgramSessionService:
    if services.sessions is None:
        raise HTTPException(status_code=503, detail="Session services are not configured")
    return services.sessions


def get_interactions(
    services: Annotated[HttpServices, Depends(get_services)],
) -> InteractionService:
    if services.interactions is None:
        raise HTTPException(status_code=503, detail="Execution interactions are not configured")
    return services.interactions


def get_blueprints(
    services: Annotated[HttpServices, Depends(get_services)],
) -> BlueprintProgramService:
    if services.blueprints is None:
        raise HTTPException(status_code=503, detail="Blueprint library is not configured")
    return services.blueprints


def get_authoring(
    services: Annotated[HttpServices, Depends(get_services)],
) -> BlueprintAuthoringService:
    if services.authoring is None:
        raise HTTPException(status_code=503, detail="Blueprint authoring is not configured")
    return services.authoring


def get_resources(
    services: Annotated[HttpServices, Depends(get_services)],
) -> ResourceAuthoringService:
    if services.resources is None:
        raise HTTPException(status_code=503, detail="Resource authoring is not configured")
    return services.resources


def get_resource_snapshots(
    services: Annotated[HttpServices, Depends(get_services)],
) -> SavedResourceResolver:
    if services.resource_snapshots is None:
        raise HTTPException(status_code=503, detail="Resource snapshots are not configured")
    return services.resource_snapshots


def get_inspection(
    services: Annotated[HttpServices, Depends(get_services)],
) -> ResourceInspectionService:
    if services.inspection is None:
        raise HTTPException(status_code=503, detail="Resource inspection is not configured")
    return services.inspection


def get_blueprint_inspection(
    services: Annotated[HttpServices, Depends(get_services)],
) -> BlueprintInspectionService:
    if services.blueprint_inspection is None:
        raise HTTPException(status_code=503, detail="Blueprint inspection is not configured")
    return services.blueprint_inspection


def get_graph_analysis(
    services: Annotated[HttpServices, Depends(get_services)],
) -> BlueprintGraphAnalysisService:
    if services.graph_analysis is None:
        raise HTTPException(status_code=503, detail="Graph analysis is not configured")
    return services.graph_analysis


def get_schedules(
    services: Annotated[HttpServices, Depends(get_services)],
) -> ProgramScheduleService:
    if services.schedules is None:
        raise HTTPException(
            status_code=503, detail="Program scheduling requires durable coordination"
        )
    return services.schedules


def get_catalog(services: Annotated[HttpServices, Depends(get_services)]) -> CatalogService:
    if services.catalog is None:
        raise HTTPException(status_code=503, detail="Element catalog is not configured")
    return services.catalog


def get_blueprint_queries(
    services: Annotated[HttpServices, Depends(get_services)],
) -> BlueprintQueryService:
    if services.blueprint_queries is None:
        raise HTTPException(status_code=503, detail="Blueprint queries are not configured")
    return services.blueprint_queries


def get_blueprint_sessions(
    services: Annotated[HttpServices, Depends(get_services)],
) -> BlueprintSessionService:
    if services.blueprint_sessions is None:
        raise HTTPException(status_code=503, detail="Blueprint sessions are not configured")
    return services.blueprint_sessions


def get_session_queries(
    services: Annotated[HttpServices, Depends(get_services)],
) -> SessionQueryService:
    if services.session_queries is None:
        raise HTTPException(status_code=503, detail="Session queries are not configured")
    return services.session_queries
