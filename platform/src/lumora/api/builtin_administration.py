"""Curated-library HTTP transport; administration policy remains in its application service."""

from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from lumora.api.dependencies import (
    HttpServices,
    HumanPrincipal,
    get_services,
    human_principal,
)
from lumora.api.edit_locks import Acquisition, Released, Renewal, holder_view
from lumora.api.resources import CreateResource
from lumora.executions.domain.preferences import ResourceExecutionDefaults
from lumora.resources.authoring import ResourcePage, ResourceView
from lumora.resources.builtins import BuiltinAdministration
from lumora.resources.domain.categories import ResourceCategory

router = APIRouter(prefix="/api/administration/resources", tags=["curated library"])
type Human = Annotated[HumanPrincipal, Depends(human_principal)]


def administration(
    services: Annotated[HttpServices, Depends(get_services)],
) -> BuiltinAdministration:
    if services.builtin_administration is None:
        raise HTTPException(
            503, "Curated administration requires durable library and editing services"
        )
    return services.builtin_administration


type Service = Annotated[BuiltinAdministration, Depends(administration)]


class CreateBuiltin(CreateResource):
    public: bool = False


class UpdateBuiltin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    config: dict[str, JsonValue] | None = None
    name: str | None = Field(default=None, min_length=1)
    public: bool | None = None
    execution: ResourceExecutionDefaults | None = None


class DependencySummary(BaseModel):
    rid: str
    name: str
    category: ResourceCategory


class BuiltinResult(ResourceView):
    cascaded_resources: tuple[DependencySummary, ...] = ()

    @classmethod
    def from_result(cls, result: tuple[ResourceView, tuple[ResourceView, ...]]) -> Self:
        root, children = result
        return cls(
            **root.model_dump(), cascaded_resources=tuple(summary(child) for child in children)
        )


def summary(resource: ResourceView) -> DependencySummary:
    return DependencySummary(rid=resource.rid, name=resource.name, category=resource.category)


@router.get("", response_model=ResourcePage)
async def list_resources(
    caller: Human,
    service: Service,
    category: ResourceCategory | None = None,
    type_key: Annotated[str | None, Query(alias="type")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> ResourcePage:
    return await service.list(
        caller.user, category=category, type_key=type_key, offset=offset, limit=limit
    )


@router.post("", response_model=BuiltinResult, status_code=201)
async def create_resource(body: CreateBuiltin, caller: Human, service: Service) -> BuiltinResult:
    return BuiltinResult.from_result(
        await service.create(
            caller.user,
            caller.owner,
            category=body.category,
            type_key=body.type_key,
            name=body.name,
            config=body.config,
            public=body.public,
            execution=body.execution,
        )
    )


@router.get("/{rid}", response_model=ResourceView)
async def get_resource(rid: str, caller: Human, service: Service) -> ResourceView:
    return await service.get(caller.user, rid)


@router.put("/{rid}", response_model=BuiltinResult)
async def update_resource(
    rid: str, body: UpdateBuiltin, caller: Human, service: Service
) -> BuiltinResult:
    return BuiltinResult.from_result(
        await service.update(
            caller.user,
            rid,
            expected_version=body.expected_version,
            config=body.config,
            name=body.name,
            public=body.public,
            execution=body.execution,
        )
    )


@router.delete("/{rid}", status_code=204)
async def delete_resource(
    rid: str,
    caller: Human,
    service: Service,
    expected_version: Annotated[int, Query(ge=1)],
) -> Response:
    await service.delete(caller.user, rid, expected_version=expected_version)
    return Response(status_code=204)


@router.get("/{rid}/publication-preview", response_model=tuple[DependencySummary, ...])
async def preview(rid: str, caller: Human, service: Service) -> tuple[DependencySummary, ...]:
    return tuple(summary(item) for item in await service.preview(caller.user, rid))


@router.post("/{rid}/edit-lease", response_model=Acquisition)
async def acquire(rid: str, caller: Human, service: Service) -> Acquisition:
    holder = await service.acquire(caller.user, rid)
    return Acquisition(acquired=holder is None, lockedBy=holder_view(holder))


@router.put("/{rid}/edit-lease", response_model=Renewal)
async def renew(rid: str, caller: Human, service: Service) -> Renewal:
    return Renewal(renewed=await service.renew(caller.user, rid))


@router.delete("/{rid}/edit-lease", response_model=Released)
async def release(rid: str, caller: Human, service: Service) -> Released:
    await service.release(caller.user, rid)
    return Released()
