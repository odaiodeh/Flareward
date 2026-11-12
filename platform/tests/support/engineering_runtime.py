"""Shared application-only runtime ports backed by real review/check use cases."""

from collections import deque

from lumora.services.identity.domain import Identity
from lumora.services.verification.access_models import (
    VerificationAccessScope,
    VerificationAction,
    VerificationActor,
)
from lumora.services.verification.check_ports import StartCheckRun
from lumora.services.verification.check_service import CheckRunService
from lumora.services.verification.domain.check_runs import CheckRunObservation, CheckRunStatus
from lumora.services.verification.models import StartVerification
from lumora.services.verification.service import VerificationService
from support.check_runs import (
    MemoryCheckRunRepository,
    ScriptedCheckRunner,
    check_registration,
    source_policy,
)
from support.review_children import ReviewChildren
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
        self.review_children = ReviewChildren(self, self.owner, self.clock, decisions, "checked")
        self.reviews = self.review_children.service
        self.decisions = self.review_children.decisions
        self.work = []

    async def start_child(self, name, inputs, *, key, environment_imports=None):
        if name == "reviewer":
            return self.review_children.start(inputs, key)
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
        elif kind == "confirm_human_review":
            return await self.review_children.invoke(
                inputs, key=key, execution_id=self.execution_id
            )
        else:
            raise AssertionError(kind)
        return result.model_dump(mode="json")

    async def receive(self, name, *, timeout=None):
        return await self.review_children.receive(name, timeout=timeout)

    async def sleep(self, seconds):
        pass
