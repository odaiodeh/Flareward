"""Application review peers use the real coordinator and service through owned ports."""

from collections import deque

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.services.identity.domain import Identity
from lumora.services.reviews.contracts import ConfirmReview, OpenReview, SubmitReview
from lumora.services.reviews.service import ReviewService
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS
from plugins.human_review.programs.human_review import HumanReviewConfig, human_review
from support.review_programs import review_definition
from support.reviews import MemoryReviews, ReviewExecutions, review_actor, review_policy


class ReviewChildren:
    def __init__(self, runtime, owner, clock, decisions, feedback):
        self.runtime, self.owner, self.clock = runtime, owner, clock
        self.decisions, self.feedback = deque(decisions), feedback
        self.executions = ReviewExecutions()
        self.service = ReviewService(
            MemoryReviews(), self.executions, {"release@1": review_policy(owner)}, clock=clock
        )
        registry = ElementRegistry()
        for spec in ELEMENT_SPECIFICATIONS:
            registry.register_spec_class(spec)
        self.config = HumanReviewConfig.model_validate(review_definition(registry).config)
        self.config.max_checks = 2
        self.opened = []
        self.children = []

    def start(self, inputs, key):
        child = ReviewChild(self, inputs, key)
        self.children.append(child)
        self.executions.parents[child.execution_id] = "root"
        self.executions.executions.add((child.execution_id, "root"))
        return child

    async def invoke(self, inputs, *, key, execution_id):
        actor = review_actor(self.owner)
        if "within_execution_id" in inputs:
            record = await self.service.confirm(ConfirmReview.model_validate(inputs), actor)
        elif "specification" in inputs:
            record = await self.service.open(
                OpenReview(key=key, execution_id=execution_id, **inputs), actor
            )
            self.opened.append(record)
        else:
            record = await self.service.inspect(inputs["review_id"], actor)
        return record.model_dump(mode="json")

    async def receive(self, name, *, timeout=None):
        record = await self.service.inspect(
            name.removeprefix("lumora.review."), review_actor(self.owner)
        )
        decision = self.decisions.popleft() if self.decisions else "pending"
        if decision == "expired":
            self.clock.advance(61)
            raise TimeoutError()
        if decision == "pending":
            raise TimeoutError()
        await self.service.respond(
            record.review_id,
            SubmitReview(
                key="human",
                expected_revision=record.revision,
                decision=decision,
                data={"feedback": self.feedback},
            ),
            Identity.user("reviewer"),
        )
        return {"decision": "approve", "untrusted": True}


class ReviewChild:
    def __init__(self, reviews, inputs, key):
        self.reviews, self.inputs = reviews, inputs
        self.execution_id = f"reviewer-{key}"
        self.cancelled = False

    async def result(self):
        try:
            return await human_review(self, self.inputs, self.reviews.config)
        finally:
            self.reviews.executions.executions.discard((self.execution_id, "root"))

    async def cancel(self):
        self.cancelled = True
        self.reviews.executions.executions.discard((self.execution_id, "root"))

    async def invoke_element(self, bundle, inputs, *, key, execution=None):
        return await self.reviews.invoke(inputs, key=key, execution_id=self.execution_id)

    async def receive(self, name, *, timeout=None):
        return await self.reviews.runtime.receive(name, timeout=timeout)
