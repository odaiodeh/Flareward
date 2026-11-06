"""Scoped check requests; provider credentials and trusted attestation remain server-side."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from mas.application.verification.access_models import VerificationActor
from mas.application.verification.check_ports import ResolveCheckRun, StartCheckRun
from mas.application.verification.check_service import CheckRunService
from mas.core.identity import Identity
from mas.domain.check_runs import CheckRun

from inbound.http_api.dependencies import HttpServices, get_services
from inbound.http_api.verification_access import verification_actor
from inbound.http_api.verifications import PlanId, private_response

router = APIRouter(
    prefix="/api/verification-checks",
    tags=["verification"],
    dependencies=[Depends(private_response)],
)


def configured(services: Annotated[HttpServices, Depends(get_services)]) -> CheckRunService:
    if services.check_runs is None:
        raise HTTPException(503, "Check execution is not configured")
    return services.check_runs


@router.post("")
async def start(
    body: StartCheckRun,
    actor: Annotated[VerificationActor, Depends(verification_actor)],
    checks: Annotated[CheckRunService, Depends(configured)],
) -> CheckRun:
    return await checks.start(body, actor)


@router.post("/{intent_id}/refresh")
async def refresh(
    intent_id: PlanId,
    actor: Annotated[VerificationActor, Depends(verification_actor)],
    checks: Annotated[CheckRunService, Depends(configured)],
) -> CheckRun:
    return await checks.refresh(intent_id, actor)


@router.get("/{intent_id}")
async def inspect(
    intent_id: PlanId,
    actor: Annotated[VerificationActor, Depends(verification_actor)],
    checks: Annotated[CheckRunService, Depends(configured)],
) -> CheckRun:
    return await checks.inspect(intent_id, actor)


@router.post("/{intent_id}/resolve")
async def resolve(
    intent_id: PlanId,
    body: ResolveCheckRun,
    request: Request,
    actor: Annotated[VerificationActor, Depends(verification_actor)],
    checks: Annotated[CheckRunService, Depends(configured)],
) -> CheckRun:
    if actor.scope is not None:
        raise HTTPException(403, "Check resolution requires a human session")
    owner = actor.identity
    user = getattr(request.state, "authenticated_user", "") or (owner.id if owner.is_user else "")
    if not user:
        raise HTTPException(401, "Authenticated human issuer required")
    return await checks.resolve(intent_id, body, owner, Identity.user(user))
