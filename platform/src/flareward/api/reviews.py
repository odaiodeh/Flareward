"""Human reviewer sessions and workflow capabilities have distinct review authority."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel

from flareward.api.dependencies import (
    HttpServices,
    HumanPrincipal,
    get_services,
    human_principal,
)
from flareward.services.identity.domain import Identity
from flareward.services.reviews.access import ReviewAccessRequest, ReviewActor, ReviewGrant
from flareward.services.reviews.contracts import CloseReview, OpenReview, SubmitReview
from flareward.services.reviews.domain.models import ReviewId, ReviewRecord
from flareward.services.reviews.ports import ReviewCredentialError, ReviewMissing

router = APIRouter(prefix="/api", tags=["human-review"])


def configured(
    response: Response, services: Annotated[HttpServices, Depends(get_services)]
) -> HttpServices:
    response.headers["Cache-Control"] = "no-store"
    if services.reviews is None or services.review_access is None:
        raise HTTPException(503, "Human Review is unavailable")
    return services


async def actor(
    request: Request, services: Annotated[HttpServices, Depends(configured)]
) -> ReviewActor:
    authorization = request.headers.get("Authorization")
    if authorization is None:
        return ReviewActor(await services.authenticate(request))
    scheme, _, credential = authorization.partition(" ")
    assert services.review_access is not None
    if scheme.lower() != "bearer":
        raise HTTPException(401, "Review authentication required")
    try:
        grant = await services.review_access.authenticate(credential)
    except ReviewCredentialError:
        raise HTTPException(401, "Review authentication required") from None
    request.state.review_grant = grant
    return ReviewActor(grant.owner, grant.scope)


class IssuedReviewAccess(BaseModel):
    grant: ReviewGrant
    credential: str


class ReviewPage(BaseModel):
    reviews: list[ReviewRecord]
    next_cursor: str | None


@router.post("/review-access", status_code=201)
async def issue(
    body: ReviewAccessRequest,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    services: Annotated[HttpServices, Depends(configured)],
    key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ] = None,
) -> IssuedReviewAccess:
    assert services.review_access is not None
    grant, credential = await services.review_access.issue(
        body, principal.owner, principal.user, key=key
    )
    return IssuedReviewAccess(grant=grant, credential=credential.get_secret_value())


@router.get("/review-access/self")
async def self_grant(
    request: Request, principal: Annotated[ReviewActor, Depends(actor)]
) -> ReviewGrant:
    grant = getattr(request.state, "review_grant", None)
    if principal.scope is None or not isinstance(grant, ReviewGrant):
        raise HTTPException(401, "Workflow credential required")
    return grant


@router.delete("/review-access/{grant_id}", status_code=204)
async def revoke(
    grant_id: str,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    services: Annotated[HttpServices, Depends(configured)],
) -> None:
    assert services.review_access is not None
    await services.review_access.revoke(grant_id, principal.owner)


@router.post("/reviews")
async def open_review(
    body: OpenReview,
    principal: Annotated[ReviewActor, Depends(actor)],
    services: Annotated[HttpServices, Depends(configured)],
) -> ReviewRecord:
    assert services.reviews is not None
    return await services.reviews.open(body, principal)


@router.get("/reviews/inbox")
async def inbox(
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    services: Annotated[HttpServices, Depends(configured)],
    after: Annotated[str, Query(pattern=r"^(?:[a-f0-9]{64})?$")] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReviewPage:
    assert services.reviews is not None
    reviews = await services.reviews.inbox(principal.user, after=after, limit=limit)
    return ReviewPage(
        reviews=reviews, next_cursor=reviews[-1].review_id if len(reviews) == limit else None
    )


@router.get("/executions/{root_execution_id}/reviews")
async def execution_reviews(
    root_execution_id: str,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    services: Annotated[HttpServices, Depends(configured)],
    after: Annotated[str, Query(pattern=r"^(?:[a-f0-9]{64})?$")] = "",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReviewPage:
    assert services.reviews is not None
    reviews = await services.reviews.for_execution(
        root_execution_id, principal.owner, after=after, limit=limit
    )
    return ReviewPage(
        reviews=reviews, next_cursor=reviews[-1].review_id if len(reviews) == limit else None
    )


@router.get("/reviews/{review_id}")
async def inspect(
    review_id: ReviewId,
    request: Request,
    principal: Annotated[ReviewActor, Depends(actor)],
    services: Annotated[HttpServices, Depends(configured)],
) -> ReviewRecord:
    assert services.reviews is not None
    if principal.scope is not None:
        return await services.reviews.inspect(review_id, principal)
    try:
        return await services.reviews.inspect(review_id, principal)
    except ReviewMissing:
        user = getattr(request.state, "authenticated_user", "") or (
            principal.identity.id if principal.identity.is_user else ""
        )
        return await services.reviews.for_reviewer(review_id, Identity.user(user))


@router.post("/reviews/{review_id}/responses")
async def respond(
    review_id: ReviewId,
    body: SubmitReview,
    principal: Annotated[HumanPrincipal, Depends(human_principal)],
    services: Annotated[HttpServices, Depends(configured)],
) -> ReviewRecord:
    assert services.reviews is not None
    return await services.reviews.respond(review_id, body, principal.user)


@router.post("/reviews/{review_id}/close")
async def close(
    review_id: ReviewId,
    body: CloseReview,
    principal: Annotated[ReviewActor, Depends(actor)],
    services: Annotated[HttpServices, Depends(configured)],
) -> ReviewRecord:
    if body.review_id != review_id:
        raise HTTPException(409, "Review identity does not match")
    assert services.reviews is not None
    return await services.reviews.close(body, principal)
