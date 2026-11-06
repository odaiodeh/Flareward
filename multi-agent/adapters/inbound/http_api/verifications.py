"""Human plan control and separately authenticated evidence admission."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from mas.application.verification.access_models import VerificationActor
from mas.application.verification.models import (
    StartVerification,
    SubmitCheckEvidence,
    VerificationView,
)
from pydantic import StringConstraints

from inbound.http_api.dependencies import HttpServices, get_services
from inbound.http_api.verification_access import verification_actor


def private_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/api", tags=["verification"], dependencies=[Depends(private_response)])
type PlanId = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


def configured(services: Annotated[HttpServices, Depends(get_services)]) -> HttpServices:
    if services.verifications is None:
        raise HTTPException(503, "Verification storage is not configured")
    return services


@router.post("/verifications")
async def start(
    body: StartVerification,
    actor: Annotated[VerificationActor, Depends(verification_actor)],
    services: Annotated[HttpServices, Depends(configured)],
) -> VerificationView:
    assert services.verifications is not None
    return await services.verifications.start(body, actor)


@router.get("/verifications/{plan_id}")
async def inspect(
    plan_id: PlanId,
    actor: Annotated[VerificationActor, Depends(verification_actor)],
    services: Annotated[HttpServices, Depends(configured)],
) -> VerificationView:
    assert services.verifications is not None
    return await services.verifications.inspect(plan_id, actor)


@router.post("/verifications/{plan_id}/cancel")
async def cancel(
    plan_id: PlanId,
    actor: Annotated[VerificationActor, Depends(verification_actor)],
    services: Annotated[HttpServices, Depends(configured)],
) -> VerificationView:
    assert services.verifications is not None
    return await services.verifications.cancel(plan_id, actor)


@router.post("/verification-evidence")
async def attest(
    body: SubmitCheckEvidence,
    request: Request,
    services: Annotated[HttpServices, Depends(configured)],
) -> VerificationView:
    if services.authenticate_verifier is None:
        raise HTTPException(503, "Verifier authentication is not configured")
    authority = await services.authenticate_verifier(request)
    assert services.verifications is not None
    return await services.verifications.submit(body, authority)
