"""Shared application-only runtime ports backed by real review/check use cases."""

from collections import deque
from unittest.mock import create_autospec

from flareward.programs.ports import ChildExecution
from flareward.services.identity.domain import Identity
from flareward.services.reviews.contracts import OpenReview, SubmitReview
from flareward.services.reviews.service import ReviewService
from plugins.adlc.programs.design import (
    DesignWork,
)
from support.feature_design import DesignerConfig, designer
from support.reviews import MemoryReviews, ReviewExecutions, review_actor, review_policy
from support.verification import VerificationClock


class DesignRuntime:
    execution_id = "root"

    def __init__(self, decisions):
        self.owner, self.clock = Identity.user("owner"), VerificationClock()
        self.reviews = ReviewService(
            MemoryReviews(),
            ReviewExecutions(),
            {"release@1": review_policy(self.owner)},
            clock=self.clock,
        )
        self.decisions = deque(decisions)
        self.work, self.opened = [], []
        self.child = None

    async def start_child(self, name, inputs, *, key, environment_imports=None):
        self.work.append(DesignWork.model_validate(inputs))
        child = create_autospec(ChildExecution, instance=True)
        child.execution_id = f"design-{len(self.work)}"
        child.result.return_value = await designer(self, inputs, DesignerConfig())
        self.child = child
        return child

    async def invoke_element(self, bundle, inputs, *, key, execution=None):
        if "specification" in inputs:
            review = await self.reviews.open(
                OpenReview(key=key, execution_id=self.execution_id, **inputs),
                review_actor(self.owner),
            )
            self.opened.append(review)
        else:
            review = await self.reviews.inspect(inputs["review_id"], review_actor(self.owner))
        return review.model_dump(mode="json")

    async def receive(self, name, *, timeout=None):
        review = await self.reviews.inspect(
            name.removeprefix("flareward.review."), review_actor(self.owner)
        )
        decision = self.decisions.popleft() if self.decisions else "pending"
        if decision == "pending":
            raise TimeoutError()
        if decision == "expired":
            self.clock.advance(61)
            raise TimeoutError()
        await self.reviews.respond(
            review.review_id,
            SubmitReview(
                key="human",
                expected_revision=review.revision,
                decision=decision,
                data={"feedback": "Add an error case"},
            ),
            Identity.user("reviewer"),
        )
        return {"decision": "approve", "untrusted": True}

    async def sleep(self, seconds):
        pass
