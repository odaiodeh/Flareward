"""Shared application-only job retirement scenario and explicit control port double."""

from dataclasses import dataclass

from flareward.services.identity.domain import Identity
from flareward.services.verification.access_models import (
    VerificationAccessScope,
    VerificationAction,
    VerificationActor,
)
from flareward.services.verification.check_ports import (
    CheckProviderUnavailable,
    CheckRunRepository,
    StartCheckRun,
)
from flareward.services.verification.check_service import CheckRunService, RegisteredCheckRunner
from flareward.services.verification.domain.check_runs import CheckJobState, CheckRun
from flareward.services.verification.domain.models import CheckRequirement
from flareward.services.verification.maintenance import CheckJobMaintenance
from flareward.services.verification.service import VerificationService
from support.check_runs import (
    MemoryCheckRunRepository,
    ScriptedCheckRunner,
    check_policy,
    source_policy,
    source_request,
)
from support.execution_access import ExecutionAuthority
from support.verification import MemoryVerificationRepository, VerificationClock


class ControlledCheckJob:
    def __init__(self) -> None:
        self.terminal = False
        self.calls: list[str] = []
        self.unavailable: set[str] = set()

    async def stop(self, run: CheckRun) -> bool:
        self.calls.append(run.intent_id)
        if run.intent_id in self.unavailable:
            raise CheckProviderUnavailable("Private provider failure")
        return self.terminal


@dataclass(frozen=True)
class CheckJobScenario:
    owner: Identity
    actor: VerificationActor
    repository: CheckRunRepository
    clock: VerificationClock
    roots: ExecutionAuthority
    driver: ScriptedCheckRunner
    control: ControlledCheckJob
    verification: VerificationService
    service: CheckRunService
    registration: RegisteredCheckRunner

    def maintenance(self) -> CheckJobMaintenance:
        return CheckJobMaintenance(
            self.repository, self.verification, {"checks@1": self.registration}, self.roots
        )


def check_job_scenario(
    repository: CheckRunRepository | None = None, *, extra_checks: tuple[CheckRequirement, ...] = ()
) -> CheckJobScenario:
    owner, clock = Identity.user("owner"), VerificationClock()
    actor = VerificationActor(
        owner,
        VerificationAccessScope(
            root_execution_id="root",
            policies=frozenset({"source@1"}),
            actions=frozenset(VerificationAction),
        ),
    )
    repository = repository or MemoryCheckRunRepository()
    policy = source_policy(owner)
    policy = policy.model_copy(update={"requirements": (*policy.requirements, *extra_checks)})
    verification = VerificationService(
        MemoryVerificationRepository(), {"source@1": policy}, clock=clock
    )
    driver, control, roots = ScriptedCheckRunner(), ControlledCheckJob(), ExecutionAuthority()
    registration = RegisteredCheckRunner(check_policy(owner), driver, lifecycle=control)
    service = CheckRunService(repository, verification, {"checks@1": registration}, clock=clock)
    return CheckJobScenario(
        owner, actor, repository, clock, roots, driver, control, verification, service, registration
    )


async def assert_pending_job_queries(case: CheckJobScenario) -> list[CheckRun]:
    records = []
    for key in ("one", "two", "three"):
        plan = (await case.verification.start(source_request(key), case.actor)).state.plan
        records.append(
            await case.service.start(
                StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), case.actor
            )
        )
    borrowed = CheckRunService(
        case.repository,
        case.verification,
        {
            "checks@1": RegisteredCheckRunner(check_policy(case.owner), case.driver),
        },
        clock=case.clock,
    )
    plan = (await case.verification.start(source_request("borrowed"), case.actor)).state.plan
    unmanaged = await borrowed.start(
        StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), case.actor
    )
    assert unmanaged.job_state is None
    records.sort(key=lambda run: run.intent_id)
    closed = records[0].model_copy(
        update={
            "job_state": CheckJobState.CLOSED,
            "revision": records[0].revision + 1,
        }
    )
    assert await case.repository.save(closed, expected_revision=records[0].revision)
    pending = await case.repository.pending_jobs(after="", limit=100)
    assert [run.intent_id for run in pending] == [run.intent_id for run in records[1:]]
    first = await case.repository.pending_jobs(after="", limit=1)
    second = await case.repository.pending_jobs(after=first[0].intent_id, limit=1)
    assert [first[0].intent_id, second[0].intent_id] == [run.intent_id for run in records[1:]]
    assert await case.repository.pending_jobs(after=second[0].intent_id, limit=100) == []
    return [closed, *records[1:]]
