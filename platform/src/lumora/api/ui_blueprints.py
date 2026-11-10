"""Existing editor transport mapped to native blueprint authoring and inspection services."""

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field, computed_field

from lumora.api.dependencies import (
    authenticated,
    get_authoring,
    get_blueprint_inspection,
    get_blueprint_queries,
)
from lumora.api.inspection_models import ValidationSettings
from lumora.async_work import await_owned
from lumora.elements.validation_services.models import BlueprintValidationResult
from lumora.programs.templates.authoring import BlueprintAuthoringService
from lumora.programs.templates.contracts import (
    BlueprintData,
    BlueprintDocument,
    BlueprintSummary,
    BlueprintView,
)
from lumora.programs.templates.input.files import parse_blueprint
from lumora.programs.templates.inspection import BlueprintInspectionService
from lumora.programs.templates.models.prompt_shortcuts import PromptShortcutItem, PromptShortcuts
from lumora.programs.templates.queries import BlueprintQueryService
from lumora.services.identity.domain import Identity

router = APIRouter(prefix="/api/blueprints", tags=["editor blueprints"], include_in_schema=False)
type Caller = Annotated[Identity, Depends(authenticated)]
type Authoring = Annotated[BlueprintAuthoringService, Depends(get_authoring)]
type Queries = Annotated[BlueprintQueryService, Depends(get_blueprint_queries)]
type Inspection = Annotated[BlueprintInspectionService, Depends(get_blueprint_inspection)]
type BlueprintId = Annotated[str, Query(alias="blueprintId", min_length=1)]


class EditorScope(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    team_id: str | None = Field(default=None, alias="teamId")


class BlueprintSource(EditorScope):
    source: str = Field(alias="blueprintRaw", min_length=1)


class BlueprintCreate(BlueprintSource):
    metadata: BlueprintData = Field(default_factory=dict)


class BlueprintSelection(EditorScope):
    blueprint_id: str = Field(alias="blueprintId", min_length=1)


class VersionedSelection(BlueprintSelection):
    expected_version: int | None = Field(default=None, ge=0)


class BlueprintUpdate(BlueprintSource, VersionedSelection):
    pass


class MetadataUpdate(VersionedSelection):
    metadata: BlueprintData


class ShortcutUpdate(VersionedSelection):
    prompts: list[BlueprintData]


class SavedValidation(BlueprintSelection, ValidationSettings):
    pass


class DraftValidation(ValidationSettings):
    draft: str = Field(min_length=1)


class EditorBlueprint(BlueprintView):
    @computed_field
    @property
    def user_id(self) -> str:
        return self.identity.id


class EditorSummary(BlueprintSummary):
    @computed_field
    @property
    def user_id(self) -> str:
        return self.identity.id


class EditorBlueprints(BaseModel):
    items: list[EditorBlueprint]
    total: int
    skip: int
    limit: int


class EditorStatus(BaseModel):
    status: Literal["success"] = "success"


class SavedBlueprint(EditorStatus):
    blueprint_id: str
    version: int


class EditorPrompts(BaseModel):
    prompts: tuple[PromptShortcutItem, ...]


def editor_document(document: BlueprintDocument) -> EditorBlueprint:
    return EditorBlueprint.model_validate(document.model_dump())


@router.get("/blueprint.draft.schema.get")
async def draft_schema(caller: Caller, service: Authoring) -> dict:
    return await await_owned(asyncio.to_thread(service.schema))


@router.get("/available.blueprints.get", response_model=list[EditorBlueprint])
async def list_drafts(
    caller: Caller,
    service: Authoring,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[EditorBlueprint]:
    return [
        editor_document(document)
        for document in (await service.list(caller, skip=skip, limit=limit)).items
    ]


@router.get("/available.blueprints.summary.get", response_model=list[EditorSummary])
async def list_summaries(
    caller: Caller,
    service: Queries,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[EditorSummary]:
    return [
        EditorSummary.model_validate(summary.model_dump())
        for summary in await service.summaries(caller, skip=skip, limit=limit)
    ]


@router.get("/available.blueprints.resolved.get", response_model=EditorBlueprint | EditorBlueprints)
async def resolved_blueprints(
    caller: Caller,
    service: Queries,
    blueprint_id: Annotated[str | None, Query(alias="blueprintId", min_length=1)] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    sort_desc: Annotated[bool, Query(alias="sortDesc")] = True,
) -> EditorBlueprint | EditorBlueprints:
    if blueprint_id is not None:
        return editor_document(await service.get(blueprint_id, caller))
    page = await service.list(caller, skip=skip, limit=limit, sort_desc=sort_desc)
    return EditorBlueprints(
        items=[editor_document(document) for document in page.items],
        total=page.total,
        skip=page.skip,
        limit=page.limit,
    )


@router.get("/blueprint.info.get", response_model=EditorBlueprint)
async def get_blueprint(
    blueprint_id: BlueprintId, caller: Caller, service: Authoring
) -> EditorBlueprint:
    return editor_document(await service.get(blueprint_id, caller))


@router.post("/blueprint.save", response_model=SavedBlueprint, status_code=201)
async def save_blueprint(
    body: BlueprintCreate, caller: Caller, service: Authoring
) -> SavedBlueprint:
    spec = await await_owned(asyncio.to_thread(parse_blueprint, body.source))
    document = await service.create(spec, caller, metadata=body.metadata)
    return SavedBlueprint(blueprint_id=document.blueprint_id, version=document.version)


@router.put("/blueprint.update", response_model=SavedBlueprint)
async def update_blueprint(
    body: BlueprintUpdate, caller: Caller, service: Authoring
) -> SavedBlueprint:
    # Authorize before parsing the editor's source, just as native authoring does.
    previous = await service.get(body.blueprint_id, caller, expected_version=body.expected_version)
    spec = await await_owned(asyncio.to_thread(parse_blueprint, body.source))
    document = await service.update(
        body.blueprint_id, spec, caller, expected_version=previous.version
    )
    return SavedBlueprint(blueprint_id=document.blueprint_id, version=document.version)


@router.delete("/remove.blueprint", response_model=EditorStatus)
async def delete_blueprint(
    blueprint_id: BlueprintId, caller: Caller, service: Authoring
) -> EditorStatus:
    await service.delete(blueprint_id, caller)
    return EditorStatus()


@router.put("/blueprint.metadata.set", response_model=EditorStatus)
async def set_metadata(body: MetadataUpdate, caller: Caller, service: Authoring) -> EditorStatus:
    await service.set_metadata(
        body.blueprint_id, body.metadata, caller, expected_version=body.expected_version
    )
    return EditorStatus()


@router.get("/blueprint.prompt-shortcuts.get", response_model=EditorPrompts)
async def get_shortcuts(
    blueprint_id: BlueprintId, caller: Caller, service: Authoring
) -> EditorPrompts:
    document = await service.get(blueprint_id, caller)
    return EditorPrompts(prompts=PromptShortcuts.from_spec(document.spec_dict).prompts)


@router.put("/blueprint.prompt-shortcuts.set", response_model=EditorPrompts)
async def set_shortcuts(body: ShortcutUpdate, caller: Caller, service: Authoring) -> EditorPrompts:
    document = await service.set_shortcuts(
        body.blueprint_id, body.prompts, caller, expected_version=body.expected_version
    )
    return EditorPrompts(prompts=PromptShortcuts.from_spec(document.spec_dict).prompts)


@router.post("/blueprint.validate", response_model=BlueprintValidationResult)
async def validate_blueprint(
    body: SavedValidation, request: Request, caller: Caller, service: Inspection
) -> BlueprintValidationResult:
    return await service.validate(
        caller,
        blueprint_id=body.blueprint_id,
        timeout_seconds=body.timeout_seconds,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
    )


@router.post("/draft.validate", response_model=BlueprintValidationResult)
async def validate_draft(
    body: DraftValidation, request: Request, caller: Caller, service: Inspection
) -> BlueprintValidationResult:
    spec = await await_owned(asyncio.to_thread(parse_blueprint, body.draft))
    return await service.validate(
        caller,
        spec=spec,
        timeout_seconds=body.timeout_seconds,
        credential_user_id=getattr(request.state, "authenticated_user", ""),
    )
