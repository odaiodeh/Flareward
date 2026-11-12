"""Catalog metadata for native clients and the existing workflow editor."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from lumora.api.dependencies import (
    HttpServices,
    HumanPrincipal,
    authenticated,
    get_catalog,
    get_services,
    human_principal,
)
from lumora.async_work import await_owned
from lumora.elements.catalog.dto import CatalogListDTO, ElementDetailDTO
from lumora.elements.catalog.service import CatalogService
from lumora.executions.domain.preferences import ExecutionProfileCatalog
from lumora.programs.authoring import ProgramInterfacePreview
from lumora.programs.domain.models import ProgramBody
from lumora.programs.registry import CoordinatorDescriptor
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.access.catalog import WorkflowAccessDescriptor
from lumora.services.identity.domain import Identity

router = APIRouter(prefix="/api/catalog", tags=["catalog"], dependencies=[Depends(authenticated)])
type Service = Annotated[CatalogService, Depends(get_catalog)]


class Categories(BaseModel):
    categories: list[ResourceCategory]


@router.get("/workflow-access", response_model=tuple[WorkflowAccessDescriptor, ...])
async def workflow_access(
    response: Response,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    services: Annotated[HttpServices, Depends(get_services)],
) -> tuple[WorkflowAccessDescriptor, ...]:
    response.headers["Cache-Control"] = "private, no-store"
    return services.workflow_access.describe(principal.owner) if services.workflow_access else ()


@router.get("/programs", response_model=list[CoordinatorDescriptor])
async def programs(
    services: Annotated[HttpServices, Depends(get_services)],
) -> list[CoordinatorDescriptor]:
    return services.programs.implementations()


@router.post("/programs/interface", response_model=ProgramInterfacePreview)
async def program_interface(
    body: ProgramBody,
    response: Response,
    services: Annotated[HttpServices, Depends(get_services)],
) -> ProgramInterfacePreview:
    response.headers["Cache-Control"] = "private, no-store"
    return services.programs.preview_interface(body)


@router.get("/execution-profiles", response_model=ExecutionProfileCatalog)
async def execution_profiles(
    services: Annotated[HttpServices, Depends(get_services)],
    caller: Annotated[Identity, Depends(authenticated)],
) -> ExecutionProfileCatalog:
    if services.execution_profiles is None:
        raise HTTPException(status_code=503, detail="Execution profiles are not configured")
    return services.execution_profiles.catalog(caller)


@router.get("/categories", response_model=Categories)
@router.get("/categories.list.get", response_model=Categories, include_in_schema=False)
async def categories(service: Service) -> Categories:
    return Categories(categories=[ResourceCategory(value) for value in service.list_categories()])


@router.get("/elements", response_model=CatalogListDTO)
@router.get("/elements.list.get", response_model=CatalogListDTO, include_in_schema=False)
async def elements(service: Service) -> CatalogListDTO:
    return service.get_all_elements_summary()


@router.get("/elements/{category}/{type_key}", response_model=ElementDetailDTO)
async def element(category: ResourceCategory, type_key: str, service: Service) -> ElementDetailDTO:
    return await await_owned(
        asyncio.to_thread(service.get_element_detail, category.value, type_key)
    )


@router.get("/element.spec.get", response_model=ElementDetailDTO, include_in_schema=False)
async def editor_element(
    category: ResourceCategory,
    type_key: Annotated[str, Query(alias="type", min_length=1)],
    service: Service,
) -> ElementDetailDTO:
    return await element(category, type_key, service)
