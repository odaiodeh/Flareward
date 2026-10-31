"""Native inspection transport preserves caller identity and delegates all library behavior."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from mas.application.elements.validation import ElementValidationResult
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.domain.element_card import ElementCard
from mas.resources.inspection import ResourceInspection
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from inbound.http_api.dependencies import authenticated, get_inspection
from inbound.http_api.inspection_models import ValidationSettings

router = APIRouter(prefix="/api/resources", tags=["resource inspection"])
type Caller = Annotated[Identity, Depends(authenticated)]
type Service = Annotated[ResourceInspection, Depends(get_inspection)]


class ResourceSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_ids: list[str] = Field(max_length=100)


class ValidateResources(ResourceSelection, ValidationSettings):
    pass


class ValidateConfiguration(ValidationSettings):
    category: ResourceCategory
    type_key: str = Field(alias="type", min_length=1)
    config: dict[str, JsonValue]
    name: str | None = None


class EditorValidateResource(ValidationSettings):
    resource_id: str = Field(alias="resourceId", min_length=1)
    team_id: str | None = Field(default=None, alias="teamId")
    # The cookie owns credential identity; accept the older client's field without trusting it.
    user_id: str | None = Field(default=None, alias="userId")


@router.post("/resource.validate", response_model=ElementValidationResult, include_in_schema=False)
async def editor_validate_resource(
    body: EditorValidateResource, request: Request, caller: Caller, service: Service
) -> ElementValidationResult:
    return await validate_resource(body.resource_id, body, request, caller, service)


@router.post("/validation", response_model=list[ElementValidationResult])
async def validate_resources(
    body: ValidateResources, request: Request, caller: Caller, service: Service
) -> list[ElementValidationResult]:
    return await service.validate(
        body.resource_ids,
        caller,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
        timeout_seconds=body.timeout_seconds,
    )


@router.post("/configuration/validation", response_model=ElementValidationResult)
async def validate_configuration(
    body: ValidateConfiguration, request: Request, caller: Caller, service: Service
) -> ElementValidationResult:
    return await service.validate_config(
        body.category,
        body.type_key,
        body.config,
        caller,
        name=body.name,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
        timeout_seconds=body.timeout_seconds,
    )


@router.post("/{rid}/validation", response_model=ElementValidationResult)
async def validate_resource(
    rid: str, body: ValidationSettings, request: Request, caller: Caller, service: Service
) -> ElementValidationResult:
    results = await service.validate(
        [rid],
        caller,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
        timeout_seconds=body.timeout_seconds,
    )
    return results[0]


@router.get("/{rid}/card", response_model=ElementCard)
async def resource_card(rid: str, caller: Caller, service: Service) -> ElementCard:
    return (await service.cards([rid], caller))[rid]


@router.post("/cards", response_model=dict[str, ElementCard])
async def resource_cards(
    body: ResourceSelection, caller: Caller, service: Service
) -> dict[str, ElementCard]:
    return await service.cards(body.resource_ids, caller)
