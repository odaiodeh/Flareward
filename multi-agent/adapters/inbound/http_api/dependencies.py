"""Typed HTTP composition boundary and request-scoped identity dependencies."""

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from mas.application.actions.service import ActionsService
from mas.application.collaboration.editing import TeamEditService
from mas.application.elements.catalog.service import CatalogService
from mas.application.sharing.notifications import ShareNotifications
from mas.blueprints.authoring import BlueprintAuthoringService
from mas.blueprints.inspection import BlueprintInspectionService
from mas.blueprints.placement import BlueprintPlacementService
from mas.blueprints.queries import BlueprintQueryService
from mas.core.execution_preferences import ExecutionProfileCatalog
from mas.core.identity import Identity
from mas.execution.service import ExecutionService
from mas.graph.analysis import BlueprintGraphAnalysisService
from mas.interactions.service import InteractionService
from mas.programs.blueprints import BlueprintProgramService
from mas.programs.service import ProgramService
from mas.resources.authoring import ResourceAuthoringService
from mas.resources.inspection import ResourceInspection
from mas.scheduling.programs import ProgramScheduleService
from mas.session.execution.blueprint_sessions import BlueprintSessionService
from mas.session.execution.program_sessions import ProgramSessionService
from mas.session.execution.queries import SessionQueryService

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
    inspection: ResourceInspection | None = None
    blueprint_inspection: BlueprintInspectionService | None = None
    graph_analysis: BlueprintGraphAnalysisService | None = None
    schedules: ProgramScheduleService | None = None
    catalog: CatalogService | None = None
    blueprint_queries: BlueprintQueryService | None = None
    blueprint_sessions: BlueprintSessionService | None = None
    session_queries: SessionQueryService | None = None
    execution_profiles: ExecutionProfileCatalog | None = None
    blueprint_placement: BlueprintPlacementService | None = None
    team_editing: TeamEditService | None = None
    actions: ActionsService | None = None
    share_notifications: ShareNotifications | None = None


type ServicesFactory = Callable[[], AbstractAsyncContextManager[HttpServices]]


def get_services(request: Request) -> HttpServices:
    services = getattr(request.app.state, "platform", None)
    if services is None:
        raise HTTPException(status_code=503, detail="Application startup has not completed")
    return services


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


def get_inspection(services: Annotated[HttpServices, Depends(get_services)]) -> ResourceInspection:
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
