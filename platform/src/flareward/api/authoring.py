"""Thin native authoring routes; identity and write semantics belong to the application."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from flareward.api.dependencies import authenticated, get_authoring
from flareward.programs.templates.authoring import BlueprintAuthoringService
from flareward.programs.templates.contracts import BlueprintData, BlueprintDocument, BlueprintPage
from flareward.programs.templates.models.prompt_shortcuts import PromptShortcuts
from flareward.services.identity.domain import Identity

router = APIRouter(prefix="/api/blueprints", tags=["blueprint authoring"])
type Service = Annotated[BlueprintAuthoringService, Depends(get_authoring)]
type Caller = Annotated[Identity, Depends(authenticated)]


class CreateBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec: BlueprintData
    metadata: BlueprintData = Field(default_factory=dict)


class UpdateBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec: BlueprintData
    expected_version: int | None = Field(default=None, ge=0)


class MetadataUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metadata: BlueprintData
    expected_version: int | None = Field(default=None, ge=0)


class ShortcutsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompts: list[BlueprintData]
    expected_version: int | None = Field(default=None, ge=0)


@router.get("/schema")
async def draft_schema(service: Service) -> dict:
    return service.schema()


@router.post("", response_model=BlueprintDocument, status_code=201)
async def create_blueprint(
    request: CreateBlueprint, caller: Caller, service: Service
) -> BlueprintDocument:
    return await service.create(request.spec, caller, metadata=request.metadata)


@router.get("", response_model=BlueprintPage)
async def list_blueprints(
    caller: Caller,
    service: Service,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    sort_desc: bool = True,
) -> BlueprintPage:
    return await service.list(caller, skip=skip, limit=limit, sort_desc=sort_desc)


@router.get("/{blueprint_id}", response_model=BlueprintDocument)
async def get_blueprint(blueprint_id: str, caller: Caller, service: Service) -> BlueprintDocument:
    return await service.get(blueprint_id, caller)


@router.put("/{blueprint_id}", response_model=BlueprintDocument)
async def update_blueprint(
    blueprint_id: str, request: UpdateBlueprint, caller: Caller, service: Service
) -> BlueprintDocument:
    return await service.update(
        blueprint_id, request.spec, caller, expected_version=request.expected_version
    )


@router.delete("/{blueprint_id}", status_code=204)
async def delete_blueprint(
    blueprint_id: str,
    caller: Caller,
    service: Service,
    expected_version: Annotated[int | None, Query(ge=0)] = None,
) -> Response:
    await service.delete(blueprint_id, caller, expected_version=expected_version)
    return Response(status_code=204)


@router.patch("/{blueprint_id}/metadata", response_model=BlueprintDocument)
async def set_metadata(
    blueprint_id: str, request: MetadataUpdate, caller: Caller, service: Service
) -> BlueprintDocument:
    return await service.set_metadata(
        blueprint_id, request.metadata, caller, expected_version=request.expected_version
    )


@router.get("/{blueprint_id}/prompt-shortcuts")
async def get_shortcuts(blueprint_id: str, caller: Caller, service: Service) -> dict:
    document = await service.get(blueprint_id, caller)
    return {"prompts": PromptShortcuts.from_spec(document.spec_dict).to_storage() or []}


@router.put("/{blueprint_id}/prompt-shortcuts", response_model=BlueprintDocument)
async def set_shortcuts(
    blueprint_id: str, request: ShortcutsUpdate, caller: Caller, service: Service
) -> BlueprintDocument:
    return await service.set_shortcuts(
        blueprint_id, request.prompts, caller, expected_version=request.expected_version
    )
