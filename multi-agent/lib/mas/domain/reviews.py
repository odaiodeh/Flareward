"""Immutable human-review occurrences and decisions, independent of engine/tool protocols."""

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_serializer,
    model_validator,
)

from mas.core.identity import Identity

type ReviewId = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
REVIEW_MESSAGE_PREFIX = "unifai.review."


def _empty_response_schema() -> dict[str, JsonValue]:
    return {"type": "object", "additionalProperties": False}


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    DECIDED = "decided"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class ReviewTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    prompt: str = Field(min_length=1, max_length=8192)
    response_schema: dict[str, JsonValue] = Field(default_factory=_empty_response_schema)
    decisions: frozenset[ReviewDecision] = Field(default=frozenset(ReviewDecision), min_length=1)
    timeout_seconds: int = Field(default=3600, ge=1, le=2_592_000)

    @field_serializer("decisions")
    def ordered_decisions(self, values: frozenset[ReviewDecision]) -> list[str]:
        return sorted(values)

    def canonical(self) -> bytes:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()

    @model_validator(mode="after")
    def bounded_specification(self) -> Self:
        try:
            if len(self.canonical()) > 131_072:
                raise ValueError("Review specification exceeds its byte limit")
        except RecursionError, UnicodeError:
            raise ValueError("Review specification is not portable JSON") from None
        return self

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical()).hexdigest()


class ReviewSpecification(ReviewTemplate):
    subject: JsonValue


class ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    key: str = Field(min_length=1, max_length=128)
    decision: ReviewDecision
    data: JsonValue = Field(default_factory=dict)
    issued_by: Identity
    recorded_at: AwareDatetime

    @model_validator(mode="after")
    def human_response(self) -> Self:
        if not self.issued_by.is_user or not self.issued_by.id:
            raise ValueError("Review response requires an authenticated human")
        return self


class ReviewRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    review_id: ReviewId
    owner: Identity
    root_execution_id: str = Field(min_length=1, max_length=256)
    execution_id: str = Field(min_length=1, max_length=256)
    key: str = Field(min_length=1, max_length=256)
    policy: str = Field(min_length=1, max_length=128)
    reviewers: frozenset[str] = Field(min_length=1, max_length=128)
    specification: ReviewSpecification
    created_at: AwareDatetime
    expires_at: AwareDatetime
    status: ReviewStatus = ReviewStatus.PENDING
    response: ReviewResponse | None = None
    superseded_by: ReviewId | None = None
    delivery_pending: bool = False
    revision: int = Field(default=0, ge=0)

    @field_serializer("reviewers")
    def ordered_reviewers(self, values: frozenset[str]) -> list[str]:
        return sorted(values)

    @property
    def message_name(self) -> str:
        return REVIEW_MESSAGE_PREFIX + self.review_id

    @model_validator(mode="after")
    def consistent_state(self) -> Self:
        if not self.owner.id or self.expires_at <= self.created_at:
            raise ValueError("Review requires owner identity and a future deadline")
        if (self.status == ReviewStatus.DECIDED) != (self.response is not None):
            raise ValueError("Only decided reviews have a human response")
        if self.response is not None and (
            self.response.issued_by.id not in self.reviewers
            or self.response.decision not in self.specification.decisions
            or not self.created_at <= self.response.recorded_at < self.expires_at
        ):
            raise ValueError("Review response does not match its occurrence")
        if (self.status == ReviewStatus.SUPERSEDED) != (
            self.superseded_by is not None
        ) or self.superseded_by == self.review_id:
            raise ValueError("Superseded review must identify a different replacement")
        if self.status == ReviewStatus.PENDING and self.delivery_pending:
            raise ValueError("Only terminal review states notify a waiting program")
        return self
