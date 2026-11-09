"""Shared application-only runtime ports backed by real review/check use cases."""

from collections import deque

from flareward.services.identity.domain import Identity
from flareward.services.reviews.contracts import OpenReview, SubmitReview
from flareward.services.reviews.service import ReviewService
from flareward.services.verification.access_models import (
    VerificationAccessScope,
    VerificationAction,
    VerificationActor,
)
from flareward.services.verification.check_ports import StartCheckRun
from flareward.services.verification.check_service import CheckRunService
from flareward.services.verification.domain.check_runs import CheckRunObservation, CheckRunStatus
from flareward.services.verification.models import StartVerification
from flareward.services.verification.service import VerificationService
from support.check_runs import (
    MemoryCheckRunRepository,
    ScriptedCheckRunner,
    check_registration,
    source_policy,
)
from support.reviews import MemoryReviews, ReviewExecutions, review_actor, review_policy
from support.verification import MemoryVerificationRepository, VerificationClock


class ImmediateRunner(ScriptedCheckRunner):
    def __init__(self, verdicts):
        super().__init__()
        self.verdicts = deque(verdicts)

    async def submit(self, run):
        self.submissions += 1
        return CheckRunObservation(
            external_id=f"check-{self.submissions}",
            status=CheckRunStatus.COMPLETED,
            verdict=self.verdicts.popleft(),
        )


class CandidateExecution:
    def __init__(self, work):
        self.execution_id = f"child-{work['attempt']}"
        self.work = work

    async def result(self):
        return {
            "subject": {"kind": "git-revision@1", "identity": {"version": self.work["attempt"]}}
        }

    async def cancel(self):
        pass


class ServiceRuntime:
    execution_id = "root"

    def __init__(self, verdicts, decisions):
        self.owner, self.clock = Identity.user("owner"), VerificationClock()
        self.actor = VerificationActor(
            self.owner,
            VerificationAccessScope(
                root_execution_id="root",
                policies=frozenset({"source@1"}),
                actions=frozenset(VerificationAction),
            ),
        )
        self.verification = VerificationService(
            MemoryVerificationRepository(),
            {"source@1": source_policy(self.owner)},
            clock=self.clock,
        )
        self.runner = ImmediateRunner(verdicts)
        self.checks = CheckRunService(
            MemoryCheckRunRepository(),
            self.verification,
            {"ci@1": check_registration(self.owner, self.runner)},
            clock=self.clock,
        )
        self.reviews = ReviewService(
            MemoryReviews(),
            ReviewExecutions(),
            {"release@1": review_policy(self.owner)},
            clock=self.clock,
        )
        self.decisions = deque(decisions)
        self.work = []

    async def start_child(self, name, inputs, *, key, environment_imports=None):
        self.work.append((name, inputs))
        return CandidateExecution(inputs)

    async def invoke_element(self, bundle, inputs, *, key, execution=None):
        kind = next(
            entry.resource.type_key for entry in bundle.entries if entry.resource.key == bundle.root
        )
        if kind == "request_verification":
            result = await self.verification.start(StartVerification(key=key, **inputs), self.actor)
        elif kind == "start_verification_check":
            result = await self.checks.start(StartCheckRun.model_validate(inputs), self.actor)
        elif kind == "refresh_verification_check":
            result = await self.checks.refresh(inputs["intent_id"], self.actor)
        elif kind == "inspect_verification":
            result = await self.verification.inspect(inputs["plan_id"], self.actor)
        elif kind == "open_human_review":
            result = await self.reviews.open(
                OpenReview(key=key, execution_id="root", **inputs), review_actor(self.owner)
            )
        elif kind == "inspect_human_review":
            result = await self.reviews.inspect(inputs["review_id"], review_actor(self.owner))
        else:
            raise AssertionError(kind)
        return result.model_dump(mode="json")

    async def receive(self, name, *, timeout=None):
        review_id = name.removeprefix("flareward.review.")
        review = await self.reviews.inspect(review_id, review_actor(self.owner))
        await self.reviews.respond(
            review_id,
            SubmitReview(
                key="human",
                expected_revision=review.revision,
                decision=self.decisions.popleft(),
                data={"feedback": "checked"},
            ),
            Identity.user("reviewer"),
        )
        return {"untrusted": "wakeup"}

    async def sleep(self, seconds):
        pass
