"""Review effects follow the ordinary typed operation and dependency-construction path."""

from pydantic import BaseModel, ConfigDict, Field

from flareward.elements.operation import BaseOperation, OperationContext
from flareward.services.reviews.contracts import (
    CloseReview,
    OpenReview,
    ReviewHandle,
    ReviewSettings,
)
from flareward.services.reviews.domain.models import ReviewRecord
from flareward.services.reviews.ports import ReviewGateway


class RequestReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    policy: str = Field(min_length=1, max_length=128)
    specification: ReviewSettings


class OpenReviewOperation(BaseOperation[RequestReview, ReviewRecord]):
    def __init__(self, gateway: ReviewGateway) -> None:
        self._gateway = gateway

    async def execute(self, request: RequestReview, context: OperationContext) -> ReviewRecord:
        return await self._gateway.open(
            OpenReview(
                key=context.key,
                execution_id=context.execution.execution_id,
                policy=request.policy,
                specification=request.specification,
            )
        )


class InspectReviewOperation(BaseOperation[ReviewHandle, ReviewRecord]):
    def __init__(self, gateway: ReviewGateway) -> None:
        self._gateway = gateway

    async def execute(self, request: ReviewHandle, context: OperationContext) -> ReviewRecord:
        return await self._gateway.inspect(request.review_id)


class CloseReviewOperation(BaseOperation[CloseReview, ReviewRecord]):
    def __init__(self, gateway: ReviewGateway) -> None:
        self._gateway = gateway

    async def execute(self, request: CloseReview, context: OperationContext) -> ReviewRecord:
        return await self._gateway.close(request)
