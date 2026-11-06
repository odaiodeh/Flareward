"""Human-authenticated reporting routes translate application-owned projections."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from mas.application.reporting.models import OwnerOverview, SystemReport, TimeRange
from mas.application.reporting.service import ReportingService

from inbound.http_api.dependencies import (
    HttpServices,
    HumanPrincipal,
    get_services,
    human_principal,
)

router = APIRouter(prefix="/api/reporting", tags=["reporting"])
type Human = Annotated[HumanPrincipal, Depends(human_principal)]


def reporting(services: Annotated[HttpServices, Depends(get_services)]) -> ReportingService:
    if services.reporting is None:
        raise HTTPException(503, "Reporting requires durable application storage")
    return services.reporting


type Service = Annotated[ReportingService, Depends(reporting)]


@router.get("/overview", response_model=OwnerOverview)
async def overview(service: Service, caller: Human) -> OwnerOverview:
    return await service.overview(caller.owner)


@router.get("/system", response_model=SystemReport)
async def system(
    service: Service,
    caller: Human,
    time_range: TimeRange = TimeRange.ALL,
    owner_offset: Annotated[int, Query(ge=0)] = 0,
    owner_limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> SystemReport:
    return await service.system(caller.user, time_range, offset=owner_offset, limit=owner_limit)
