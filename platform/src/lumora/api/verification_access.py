"""Native humans issue workflow capabilities; bearer credentials never fall back to cookies."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, StringConstraints

from lumora.api.dependencies import (
    HttpServices,
    HumanPrincipal,
    get_services,
    human_principal,
)
from lumora.services.verification.access_models import (
    VerificationAccessGrant,
    VerificationAccessRequest,
    VerificationActor,
)
from lumora.services.verification.ports import VerificationCredentialError

router = APIRouter(prefix="/api/verification-access", tags=["verification-access"])
type GrantId = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]


class IssuedVerificationResponse(BaseModel):
    grant: VerificationAccessGrant
    credential: str


async def verification_actor(
    request: Request,
    services: Annotated[HttpServices, Depends(get_services)],
) -> VerificationActor:
    authorization = request.headers.get("Authorization")
    if authorization is not None:
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() != "bearer" or services.verification_access is None:
            raise HTTPException(401, "Verification authentication required")
        try:
            grant = await services.verification_access.authenticate(credential)
        except VerificationCredentialError:
            raise HTTPException(401, "Verification authentication required") from None
        request.state.verification_grant = grant
        return VerificationActor(grant.owner, grant.scope)
    return VerificationActor(await services.authenticate(request))


def configured(services: Annotated[HttpServices, Depends(get_services)]) -> HttpServices:
    if services.verification_access is None:
        raise HTTPException(503, "Verification access is not configured")
    return services


@router.post("", status_code=201)
async def issue(
    body: VerificationAccessRequest,
    response: Response,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    services: Annotated[HttpServices, Depends(configured)],
    key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ] = None,
) -> IssuedVerificationResponse:
    assert services.verification_access is not None
    issued = await services.verification_access.issue(
        body, principal.owner, principal.user, key=key
    )
    response.headers["Cache-Control"] = "no-store"
    return IssuedVerificationResponse(
        grant=issued.grant, credential=issued.credential.get_secret_value()
    )


@router.get("")
async def list_grants(
    response: Response,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    services: Annotated[HttpServices, Depends(configured)],
    after: Annotated[str, Query(pattern=r"^(?:[a-f0-9]{32})?$")] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[VerificationAccessGrant]:
    assert services.verification_access is not None
    response.headers["Cache-Control"] = "no-store"
    return await services.verification_access.list(principal.owner, after=after, limit=limit)


@router.get("/self")
async def inspect_grant(
    request: Request,
    response: Response,
    actor: Annotated[VerificationActor, Depends(verification_actor)],
) -> VerificationAccessGrant:
    if actor.scope is None:
        raise HTTPException(401, "Workflow credential required")
    response.headers["Cache-Control"] = "no-store"
    grant = getattr(request.state, "verification_grant", None)
    if not isinstance(grant, VerificationAccessGrant):
        raise HTTPException(401, "Workflow credential required")
    return grant


@router.delete("/{grant_id}", status_code=204)
async def revoke(
    grant_id: GrantId,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    services: Annotated[HttpServices, Depends(configured)],
) -> None:
    assert services.verification_access is not None
    await services.verification_access.revoke(grant_id, principal.owner)
