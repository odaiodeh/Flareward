"""Review effects follow the ordinary typed operation and dependency-construction path."""

from mas.application.elements.operation import BaseOperation, OperationContext
from mas.application.reviews.contracts import CloseReview, OpenReview, ReviewHandle, ReviewSettings
from mas.application.reviews.ports import ReviewGateway
from mas.domain.reviews import ReviewRecord
from pydantic import BaseModel, ConfigDict, Field


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
