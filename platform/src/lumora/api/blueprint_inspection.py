"""Native blueprint inspection delegates authorization and probing to the application."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from lumora.api.dependencies import (
    authenticated,
    get_blueprint_inspection,
    get_blueprint_placement,
)
from lumora.api.inspection_models import ValidationSettings
from lumora.elements.domain.cards import ElementCard
from lumora.elements.validation_services.models import BlueprintValidationResult
from lumora.executions.domain.placement import GraphPlacementPlan
from lumora.programs.templates.contracts import BlueprintData
from lumora.programs.templates.inspection import BlueprintInspectionService
from lumora.programs.templates.placement import BlueprintPlacementService
from lumora.services.identity.domain import Identity

router = APIRouter(prefix="/api/blueprints", tags=["blueprint inspection"])
type Caller = Annotated[Identity, Depends(authenticated)]
type Service = Annotated[BlueprintInspectionService, Depends(get_blueprint_inspection)]
type Placement = Annotated[BlueprintPlacementService, Depends(get_blueprint_placement)]


class DraftSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec: BlueprintData


class ValidateDraft(DraftSelection, ValidationSettings):
    pass


@router.post("/draft/placement", response_model=GraphPlacementPlan)
async def draft_placement(
    body: DraftSelection, caller: Caller, service: Placement
) -> GraphPlacementPlan:
    return await service.preview(caller, spec=body.spec)


@router.get("/{blueprint_id}/placement", response_model=GraphPlacementPlan)
async def blueprint_placement(
    blueprint_id: str, caller: Caller, service: Placement
) -> GraphPlacementPlan:
    return await service.preview(caller, blueprint_id=blueprint_id)


@router.post("/draft/validation", response_model=BlueprintValidationResult)
async def validate_draft(
    body: ValidateDraft, request: Request, caller: Caller, service: Service
) -> BlueprintValidationResult:
    return await service.validate(
        caller,
        spec=body.spec,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
        timeout_seconds=body.timeout_seconds,
    )


@router.post("/draft/cards", response_model=dict[str, ElementCard])
async def draft_cards(
    body: DraftSelection, caller: Caller, service: Service
) -> dict[str, ElementCard]:
    return await service.cards(caller, spec=body.spec)


@router.post("/{blueprint_id}/validation", response_model=BlueprintValidationResult)
async def validate_blueprint(
    blueprint_id: str, body: ValidationSettings, request: Request, caller: Caller, service: Service
) -> BlueprintValidationResult:
    return await service.validate(
        caller,
        blueprint_id=blueprint_id,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
        timeout_seconds=body.timeout_seconds,
    )


@router.get("/{blueprint_id}/cards", response_model=dict[str, ElementCard])
async def blueprint_cards(
    blueprint_id: str, caller: Caller, service: Service
) -> dict[str, ElementCard]:
    return await service.cards(caller, blueprint_id=blueprint_id)
