"""Portable result contract for Programs that obtain a human review."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from lumora.services.reviews.domain.models import ReviewRecord


class ReviewWaitReason(StrEnum):
    RESOLVED = "resolved"
    CHECK_LIMIT = "check_limit"


class HumanReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    review: ReviewRecord
    reason: ReviewWaitReason
