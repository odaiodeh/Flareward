"""Artifact credentials never authenticate unrelated API routes or issue other credentials."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from lumora.api.dependencies import (
    HttpServices,
    HumanPrincipal,
    get_artifact_access,
    get_services,
    human_principal,
)
from lumora.services.artifacts.access import ArtifactAccessService
from lumora.services.artifacts.access_models import (
    ArtifactAccessGrant,
    ArtifactAccessRequest,
    ArtifactActor,
    ArtifactWorkflowGrant,
)
from lumora.services.artifacts.ports import ArtifactCredentialError

router = APIRouter(prefix="/api/artifact-access", tags=["artifact-access"])
type AccessService = Annotated[ArtifactAccessService, Depends(get_artifact_access)]
type Human = Annotated[HumanPrincipal, Depends(human_principal)]


class IssuedAccessResponse(BaseModel):
    grant: ArtifactAccessGrant
    credential: str = Field(repr=False)


async def artifact_actor(
    request: Request, services: Annotated[HttpServices, Depends(get_services)]
) -> ArtifactActor:
    authorization = request.headers.get("Authorization")
    if authorization is None:
        return ArtifactActor(await services.authenticate(request))
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid artifact credential")
    for service in (services.artifact_access, services.artifact_workflow_access):
        if service is None:
            continue
        try:
            grant = await service.authenticate(credential)
        except ArtifactCredentialError:
            continue
        request.state.artifact_grant = grant
        return ArtifactActor(grant.owner, grant.scope)
    raise HTTPException(status_code=401, detail="Invalid artifact credential")


@router.post("", response_model=IssuedAccessResponse, status_code=201)
async def issue(
    request: ArtifactAccessRequest, service: AccessService, caller: Human
) -> JSONResponse:
    issued = await service.issue(request, caller.owner)
    response = IssuedAccessResponse(
        grant=issued.grant, credential=issued.credential.get_secret_value()
    )
    return JSONResponse(
        response.model_dump(mode="json"), status_code=201, headers={"Cache-Control": "no-store"}
    )


@router.get("", response_model=list[ArtifactAccessGrant])
async def list_grants(
    service: AccessService,
    caller: Human,
    after: str = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ArtifactAccessGrant]:
    return await service.list(caller.owner, after=after, limit=limit)


@router.get("/self", response_model=ArtifactAccessGrant | ArtifactWorkflowGrant)
async def current(
    request: Request, caller: Annotated[ArtifactActor, Depends(artifact_actor)]
) -> ArtifactAccessGrant | ArtifactWorkflowGrant:
    grant = getattr(request.state, "artifact_grant", None)
    if not isinstance(grant, (ArtifactAccessGrant, ArtifactWorkflowGrant)):
        raise HTTPException(status_code=401, detail="An artifact credential is required")
    return grant


@router.delete("/{grant_id}", status_code=204)
async def revoke(grant_id: str, service: AccessService, caller: Human) -> Response:
    await service.revoke(grant_id, caller.owner)
    return Response(status_code=204)
