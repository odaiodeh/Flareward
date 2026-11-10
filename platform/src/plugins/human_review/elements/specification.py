"""Review effects are adapters registered through the existing specs/factories."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from lumora.elements.construction.context import ElementBuildContext
from lumora.elements.factory import BaseFactory
from lumora.elements.specification import BaseElementSpec
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.domain.references import ProviderRef
from lumora.services.reviews.contracts import CloseReview, ReviewHandle
from lumora.services.reviews.domain.models import ReviewRecord
from plugins.human_review.elements.http import HTTPReviewGateway, ReviewTransportSettings
from plugins.human_review.elements.operations import (
    CloseReviewOperation,
    InspectReviewOperation,
    OpenReviewOperation,
    RequestReview,
)


class ReviewConnection(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    access_token: SecretStr | None = Field(default=None, repr=False, min_length=1)


class ReviewOperationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: ProviderRef


class ReviewConnectionFactory(BaseFactory[ReviewConnection, HTTPReviewGateway]):
    def accepts(self, cfg: ReviewConnection, element_type: str) -> bool:
        return element_type == "review_service"

    def create(self, cfg: ReviewConnection, **dependencies: Any) -> HTTPReviewGateway:
        context: ElementBuildContext = dependencies["deps"]
        if context.execution_ctx is None:
            raise ValueError("Review connection requires execution identity")
        return HTTPReviewGateway(
            ReviewTransportSettings.model_validate({}),
            context.execution_ctx.context,
            cfg.access_token,
            source=context.workflow_credentials,
        )


class OpenReviewFactory(BaseFactory[ReviewOperationConfig, OpenReviewOperation]):
    def accepts(self, cfg: ReviewOperationConfig, element_type: str) -> bool:
        return element_type == "open_human_review"

    def create(self, cfg: ReviewOperationConfig, **dependencies: Any) -> OpenReviewOperation:
        return OpenReviewOperation(dependencies["service"])


class InspectReviewFactory(BaseFactory[ReviewOperationConfig, InspectReviewOperation]):
    def accepts(self, cfg: ReviewOperationConfig, element_type: str) -> bool:
        return element_type == "inspect_human_review"

    def create(self, cfg: ReviewOperationConfig, **dependencies: Any) -> InspectReviewOperation:
        return InspectReviewOperation(dependencies["service"])


class CloseReviewFactory(BaseFactory[ReviewOperationConfig, CloseReviewOperation]):
    def accepts(self, cfg: ReviewOperationConfig, element_type: str) -> bool:
        return element_type == "close_human_review"

    def create(self, cfg: ReviewOperationConfig, **dependencies: Any) -> CloseReviewOperation:
        return CloseReviewOperation(dependencies["service"])


class ReviewConnectionSpec(BaseElementSpec):
    category = ResourceCategory.PROVIDER
    type_key = "review_service"
    name = "Human Review service"
    description = "Root-scoped review effects without human decision authority"
    config_schema = ReviewConnection
    factory_cls = ReviewConnectionFactory


class OpenReviewSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "open_human_review"
    name = "Open Human Review"
    description = "Persist an execution-bound review occurrence with frozen response requirements"
    config_schema = ReviewOperationConfig
    factory_cls = OpenReviewFactory
    input_schema = RequestReview
    result_schema = ReviewRecord


class InspectReviewSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "inspect_human_review"
    name = "Inspect Human Review"
    description = "Read the authoritative review decision or terminal lifecycle outcome"
    config_schema = ReviewOperationConfig
    factory_cls = InspectReviewFactory
    input_schema = ReviewHandle
    result_schema = ReviewRecord


class CloseReviewSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "close_human_review"
    name = "Close Human Review"
    description = "Cancel or supersede a pending review without fabricating human approval"
    config_schema = ReviewOperationConfig
    factory_cls = CloseReviewFactory
    input_schema = CloseReview
    result_schema = ReviewRecord


ELEMENT_SPECIFICATIONS = (ReviewConnectionSpec, OpenReviewSpec, InspectReviewSpec, CloseReviewSpec)
