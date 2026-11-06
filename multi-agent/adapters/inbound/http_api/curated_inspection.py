"""Explicit human-admin probes of curated defaults, separate from caller overlays."""

from typing import Annotated

from fastapi import APIRouter, Depends
from mas.application.resources.inspection import CuratedInspection, ResourceInspectionService

from inbound.http_api.dependencies import HumanPrincipal, get_inspection, human_principal
from inbound.http_api.resource_inspection import ValidateConfiguration, ValidateResources

router = APIRouter(prefix="/api/administration/resources", tags=["curated inspection"])
type Human = Annotated[HumanPrincipal, Depends(human_principal)]
type Service = Annotated[ResourceInspectionService, Depends(get_inspection)]


@router.post("/validation", response_model=CuratedInspection)
async def validate(body: ValidateResources, caller: Human, service: Service) -> CuratedInspection:
    return await service.validate_curated(
        body.resource_ids,
        caller.user,
        caller.owner,
        timeout_seconds=body.timeout_seconds,
    )


@router.post("/configuration/validation", response_model=CuratedInspection)
async def validate_configuration(
    body: ValidateConfiguration,
    caller: Human,
    service: Service,
) -> CuratedInspection:
    return await service.validate_curated_config(
        body.category,
        body.type_key,
        body.config,
        caller.user,
        caller.owner,
        name=body.name,
        timeout_seconds=body.timeout_seconds,
    )
