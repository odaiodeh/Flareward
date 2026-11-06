"""Resource transport delegates construction metadata, ownership, and editing policy."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from mas.application.elements.construction.snapshots import ResourceSelection, SavedResourceResolver
from mas.core.enums import ResourceCategory, ResourceOwnership
from mas.core.identity import Identity
from mas.domain.element_bundles import ElementBundle
from mas.domain.execution_preferences import ResourceExecutionDefaults
from mas.resources.authoring import ResourceAuthoringService, ResourcePage, ResourceView
from mas.resources.builtin_models import BuiltinUserConfig
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from inbound.http_api.dependencies import (
    HumanPrincipal,
    authenticated,
    get_resource_snapshots,
    get_resources,
    human_principal,
)

router = APIRouter(prefix="/api/resources", tags=["resources"])
type Caller = Annotated[Identity, Depends(authenticated)]
type Service = Annotated[ResourceAuthoringService, Depends(get_resources)]


class CreateResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: ResourceCategory
    type_key: str = Field(alias="type", min_length=1)
    name: str = Field(min_length=1)
    config: dict[str, JsonValue]
    execution: ResourceExecutionDefaults = Field(default_factory=ResourceExecutionDefaults)


class UpdateResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, JsonValue]
    name: str | None = Field(default=None, min_length=1)
    expected_version: int | None = Field(default=None, ge=0)
    execution: ResourceExecutionDefaults | None = None


class ConfigureBuiltin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, JsonValue]
    expected_version: int | None = Field(default=None, ge=0)


@router.post("/snapshot", response_model=ElementBundle)
async def resource_snapshot(
    selection: ResourceSelection,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    service: Annotated[SavedResourceResolver, Depends(get_resource_snapshots)],
) -> ElementBundle:
    return await service.bundle(selection, principal.owner)


@router.get("/schema/{category}/{type_key}")
async def resource_schema(
    category: ResourceCategory, type_key: str, service: Service
) -> dict[str, Any]:
    return service.schema(category, type_key)


@router.post("", response_model=ResourceView, status_code=201)
async def create_resource(
    request: CreateResource, caller: Caller, service: Service
) -> ResourceView:
    return await service.create(
        caller,
        category=request.category,
        type_key=request.type_key,
        name=request.name,
        config=request.config,
        execution=request.execution,
    )


@router.get("", response_model=ResourcePage)
async def list_resources(
    caller: Caller,
    service: Service,
    category: ResourceCategory | None = None,
    type_key: Annotated[str | None, Query(alias="type")] = None,
    ownership: ResourceOwnership | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
) -> ResourcePage:
    return await service.list(
        caller,
        category=category,
        type_key=type_key,
        ownership=ownership,
        offset=offset,
        limit=limit,
    )


@router.get("/{rid}", response_model=ResourceView)
async def get_resource(rid: str, caller: Caller, service: Service) -> ResourceView:
    return await service.get(rid, caller)


@router.get("/{rid}/configuration", response_model=BuiltinUserConfig | None)
async def get_configuration(rid: str, caller: Caller, service: Service) -> BuiltinUserConfig | None:
    return await service.configuration(rid, caller)


@router.get("/{rid}/configuration-schema")
async def configuration_schema(rid: str, caller: Caller, service: Service) -> dict[str, Any]:
    return await service.configuration_schema(rid, caller)


@router.patch("/{rid}/configuration", response_model=BuiltinUserConfig)
async def configure_builtin(
    rid: str, request: ConfigureBuiltin, caller: Caller, service: Service
) -> BuiltinUserConfig:
    return await service.configure(
        rid, caller, config=request.config, expected_version=request.expected_version
    )


@router.delete("/{rid}/configuration", status_code=204)
async def reset_configuration(
    rid: str,
    caller: Caller,
    service: Service,
    expected_version: Annotated[int | None, Query(ge=0)] = None,
) -> Response:
    await service.reset_configuration(rid, caller, expected_version=expected_version)
    return Response(status_code=204)


@router.put("/{rid}", response_model=ResourceView)
async def update_resource(
    rid: str, request: UpdateResource, caller: Caller, service: Service
) -> ResourceView:
    return await service.update(
        rid,
        caller,
        config=request.config,
        name=request.name,
        expected_version=request.expected_version,
        execution=request.execution,
    )


@router.delete("/{rid}", status_code=204)
async def delete_resource(
    rid: str,
    caller: Caller,
    service: Service,
    expected_version: Annotated[int | None, Query(ge=0)] = None,
) -> Response:
    await service.delete(rid, caller, expected_version=expected_version)
    return Response(status_code=204)
