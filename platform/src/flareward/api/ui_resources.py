"""Existing editor HTTP shapes mapped to native application resource operations."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from flareward.api.dependencies import authenticated, get_resources
from flareward.api.resources import CreateResource, UpdateResource
from flareward.async_work import await_owned
from flareward.elements.hints import HiddenHint
from flareward.resources.authoring import ResourceAuthoringService, ResourceView
from flareward.resources.domain.categories import ResourceCategory, ResourceOwnership
from flareward.resources.domain.models import Resource
from flareward.services.identity.domain import Identity

router = APIRouter(prefix="/api/resources", tags=["editor resources"], include_in_schema=False)
type Caller = Annotated[Identity, Depends(authenticated)]
type Service = Annotated[ResourceAuthoringService, Depends(get_resources)]


class CreateEditorResource(CreateResource):
    team_id: str | None = Field(default=None, alias="teamId")


class UpdateEditorResource(UpdateResource):
    resource_id: str = Field(alias="resourceId", min_length=1)
    team_id: str | None = Field(default=None, alias="teamId")


class Pagination(BaseModel):
    total: int
    offset: int
    limit: int
    has_more: bool


class EditorResources(BaseModel):
    resources: list[ResourceView]
    pagination: Pagination


@router.get("/resource.schema")
async def resource_schema(caller: Caller) -> dict:
    schema = await await_owned(asyncio.to_thread(Resource.model_json_schema))
    for name, field in schema["properties"].items():
        if name not in {"name", "execution"}:
            field.update(HiddenHint(reason="Server-managed resource metadata").to_hints())
    return schema


@router.get("/resource.get", response_model=ResourceView)
async def get_resource(
    resource_id: Annotated[str, Query(alias="resourceId", min_length=1)],
    caller: Caller,
    service: Service,
) -> ResourceView:
    return await service.get(resource_id, caller)


@router.get("/resources.list", response_model=EditorResources)
async def list_resources(
    caller: Caller,
    service: Service,
    category: ResourceCategory | None = None,
    type_key: Annotated[str | None, Query(alias="type")] = None,
    ownership: ResourceOwnership | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
) -> EditorResources:
    page = await service.list(
        caller,
        category=category,
        type_key=type_key,
        ownership=ownership,
        offset=offset,
        limit=limit,
    )
    return EditorResources(
        resources=page.resources,
        pagination=Pagination(
            total=page.total,
            offset=page.offset,
            limit=page.limit,
            has_more=page.offset + len(page.resources) < page.total,
        ),
    )


@router.post("/resource.save", response_model=ResourceView, status_code=201)
async def create_resource(
    request: CreateEditorResource, caller: Caller, service: Service
) -> ResourceView:
    return await service.create(
        caller,
        category=request.category,
        type_key=request.type_key,
        name=request.name,
        config=request.config,
        execution=request.execution,
    )


@router.put("/resource.update", response_model=ResourceView)
async def update_resource(
    request: UpdateEditorResource, caller: Caller, service: Service
) -> ResourceView:
    return await service.update(
        request.resource_id,
        caller,
        config=request.config,
        name=request.name,
        expected_version=request.expected_version,
        execution=request.execution,
    )


@router.delete("/resource.delete", status_code=204)
async def delete_resource(
    resource_id: Annotated[str, Query(alias="resourceId", min_length=1)],
    caller: Caller,
    service: Service,
    expected_version: Annotated[int | None, Query(ge=0)] = None,
) -> Response:
    await service.delete(resource_id, caller, expected_version=expected_version)
    return Response(status_code=204)
