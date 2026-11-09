"""Portable user interaction data; existing approval vocabulary remains canonical."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field, JsonValue, TypeAdapter, ValidationError

from flareward.executions.domain.context import APPROVAL_RULES_TAG, ExecutionContext
from flareward.models import Model
from flareward.services.interactions.tools.models import (
    ApprovalDecision,
    ApprovalOverrides,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalRuleSet,
)

REQUEST = TypeAdapter(ApprovalRequest)
RESPONSE = TypeAdapter(ApprovalResponse)


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    RESPONDED = "responded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalTicket(Model):
    execution_id: str
    request: ApprovalRequest
    expires_at: datetime
    status: ApprovalStatus = ApprovalStatus.PENDING


class StreamEvent(Model):
    cursor: str
    execution_id: str
    data: dict[str, JsonValue]


class ApprovalSubmission(Model):
    decision: ApprovalDecision
    feedback: str = ""
    modified_args: dict[str, JsonValue] = Field(default_factory=dict)

    def response(self, request_id: str) -> ApprovalResponse:
        return ApprovalResponse(request_id, self.decision, self.feedback, self.modified_args)


class ApprovalRules(Model):
    approve_all: bool = Field(default=False, strict=True)
    reject_all: bool = Field(default=False, strict=True)
    auto_approve_tools: tuple[str, ...] = ()
    auto_reject_tools: tuple[str, ...] = ()

    def domain(self) -> ApprovalRuleSet:
        return ApprovalRuleSet(
            self.approve_all,
            self.reject_all,
            frozenset(self.auto_approve_tools),
            frozenset(self.auto_reject_tools),
        )


class ApprovalRulesUpdate(Model):
    global_rules: ApprovalRules = Field(default_factory=ApprovalRules)
    node_rules: dict[str, ApprovalRules] = Field(default_factory=dict)

    def domain(self) -> ApprovalOverrides:
        return ApprovalOverrides(
            self.global_rules.domain(),
            {uid: rules.domain() for uid, rules in self.node_rules.items()},
        )


class InteractionConflict(ValueError):
    """The approval is expired, cancelled, or already has another decision."""


class StreamCursorExpired(InteractionConflict):
    """The requested resume point is outside retained stream history."""


def initial_rules(context: ExecutionContext) -> ApprovalOverrides:
    return parse_approval_rules(context.tags.get(APPROVAL_RULES_TAG))


def parse_approval_rules(value: object | None) -> ApprovalOverrides:
    try:
        return ApprovalRulesUpdate.model_validate({} if value is None else value).domain()
    except ValidationError:
        raise ValueError("Invalid approval rules") from None
