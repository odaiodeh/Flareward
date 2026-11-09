"""Human subscription management and purpose-separated event delivery transport."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import Field

from flareward.api.dependencies import (
    HttpServices,
    HumanPrincipal,
    get_services,
    human_principal,
)
from flareward.executions.domain.events import ProgramEvent, ProgramEventSource
from flareward.executions.events import (
    CreateEventSource,
    EventAdmission,
    EventAuthenticationError,
    EventSourceSettings,
    ProgramEventService,
    RotateEventCredential,
)
from flareward.models import Model

router = APIRouter(prefix="/api/program-events", tags=["program events"])


def configured(services: Annotated[HttpServices, Depends(get_services)]) -> ProgramEventService:
    if services.program_events is None:
        raise HTTPException(503, "Program event sources are not configured")
    return services.program_events


type Service = Annotated[ProgramEventService, Depends(configured)]
type Human = Annotated[HumanPrincipal, Depends(human_principal)]


class IssuedSourceResponse(Model):
    source: ProgramEventSource
    credential: str = Field(repr=False)


class RotatedCredentialResponse(Model):
    credential: str = Field(repr=False)
    revision: int


@router.post("/sources", status_code=201)
async def create_source(
    body: CreateEventSource, response: Response, principal: Human, service: Service
) -> IssuedSourceResponse:
    issued = await service.create(body, principal.owner, principal.user)
    response.headers["Cache-Control"] = "no-store"
    return IssuedSourceResponse(
        source=issued.source, credential=issued.credential.get_secret_value()
    )


@router.get("/sources")
async def list_sources(
    principal: Human,
    service: Service,
    after: Annotated[str, Query(pattern=r"^(?:[a-f0-9]{32})?$")] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ProgramEventSource]:
    return await service.list(principal.owner, after=after, limit=limit)


@router.get("/sources/{source_id}")
async def get_source(source_id: str, principal: Human, service: Service) -> ProgramEventSource:
    return await service.get(source_id, principal.owner)


@router.get("/sources/{source_id}/settings")
async def source_settings(
    source_id: str, principal: Human, service: Service
) -> EventSourceSettings:
    return await service.settings(source_id, principal.owner)


@router.post("/sources/{source_id}/credential")
async def rotate_credential(
    source_id: str,
    body: RotateEventCredential,
    response: Response,
    principal: Human,
    service: Service,
) -> RotatedCredentialResponse:
    rotated = await service.rotate(source_id, principal.owner, body)
    response.headers["Cache-Control"] = "no-store"
    return RotatedCredentialResponse(
        credential=rotated.credential.get_secret_value(), revision=rotated.revision
    )


@router.delete("/sources/{source_id}", status_code=204)
async def revoke_source(source_id: str, principal: Human, service: Service) -> Response:
    await service.revoke(source_id, principal.owner)
    return Response(status_code=204)


@router.post("/deliveries", status_code=202)
async def deliver_event(
    event: ProgramEvent,
    service: Service,
    authorization: Annotated[str | None, Header()] = None,
) -> EventAdmission:
    scheme, _, credential = (authorization or "").partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(401, "Event delivery authentication required")
    try:
        return await service.deliver(credential, event)
    except EventAuthenticationError:
        raise HTTPException(401, "Event delivery authentication required") from None
