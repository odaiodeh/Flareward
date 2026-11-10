"""Application-owned check driver and repository doubles share no transport code."""

import asyncio

from lumora.services.identity.domain import Identity
from lumora.services.verification.check_ports import CheckProviderUnavailable, CheckRunnerPolicy
from lumora.services.verification.check_service import RegisteredCheckRunner
from lumora.services.verification.domain.check_runs import (
    CheckJobState,
    CheckRun,
    CheckRunObservation,
    CheckRunStatus,
)
from lumora.services.verification.domain.models import (
    CheckRequirement,
    CheckVerdict,
    VerificationSubject,
)
from lumora.services.verification.models import StartVerification, VerificationPolicy
from lumora.services.verification.ports import VerificationStorageError


class MemoryCheckRunRepository:
    def __init__(self) -> None:
        self.records: dict[str, CheckRun] = {}
        self.fail_evidence_acknowledgement = False
        self.fail_report_acknowledgement = False

    async def create(self, run: CheckRun) -> bool:
        if run.intent_id in self.records:
            return False
        self.records[run.intent_id] = run.model_copy(deep=True)
        return True

    async def get(self, intent_id: str) -> CheckRun | None:
        await asyncio.sleep(0)
        run = self.records.get(intent_id)
        return run.model_copy(deep=True) if run else None

    async def pending_jobs(self, *, after: str, limit: int) -> list[CheckRun]:
        if not 1 <= limit <= 100:
            raise ValueError("Check maintenance page size must be between 1 and 100")
        return [
            run.model_copy(deep=True)
            for key, run in sorted(self.records.items())
            if key > after and run.job_state in {CheckJobState.ACTIVE, CheckJobState.RETIRING}
        ][:limit]

    async def save(self, run: CheckRun, *, expected_revision: int) -> bool:
        await asyncio.sleep(0)
        if run.evidence_recorded and self.fail_evidence_acknowledgement:
            raise VerificationStorageError("Check evidence acknowledgement unavailable")
        if run.reports_collected and self.fail_report_acknowledgement:
            raise VerificationStorageError("Check report acknowledgement unavailable")
        current = self.records.get(run.intent_id)
        if current is None or current.revision != expected_revision:
            return False
        self.records[run.intent_id] = run.model_copy(deep=True)
        return True


class ScriptedCheckRunner:
    configuration_digest = "a" * 64

    def __init__(self, *, lose_acknowledgement: bool = False) -> None:
        self.submissions = 0
        self.lose_acknowledgement = lose_acknowledgement
        self.observation: CheckRunObservation | None = None

    def validate(self, run: CheckRun) -> None:
        pass

    async def submit(self, run: CheckRun) -> CheckRunObservation:
        self.submissions += 1
        self.observation = CheckRunObservation(
            external_id="trusted-ci:1", status=CheckRunStatus.QUEUED
        )
        if self.lose_acknowledgement:
            raise CheckProviderUnavailable("private provider diagnostics")
        return self.observation

    async def reconcile(self, run: CheckRun) -> CheckRunObservation | None:
        return self.observation

    def complete(self, verdict: CheckVerdict = CheckVerdict.PASSED) -> None:
        self.observation = CheckRunObservation(
            external_id="trusted-ci:1", status=CheckRunStatus.COMPLETED, verdict=verdict
        )


def check_policy(owner: Identity) -> CheckRunnerPolicy:
    return CheckRunnerPolicy(
        owners=(owner,),
        policies=frozenset({"source@1"}),
        check="tests@1",
        verifier="github-ci",
        subject_kind="git-revision@1",
    )


def source_policy(owner: Identity, *, requires_reports: bool = False) -> VerificationPolicy:
    return VerificationPolicy(
        owners=(owner,),
        subject_kind="git-revision@1",
        requirements=(
            CheckRequirement(
                check="tests@1",
                verifiers=frozenset({"github-ci"}),
                requires_reports=requires_reports,
            ),
        ),
        timeout_seconds=3600,
    )


def source_request(key: str = "candidate") -> StartVerification:
    return StartVerification(
        key=key,
        policy="source@1",
        subject=VerificationSubject(
            kind="git-revision@1", identity={"repository": "product", "commit": "b" * 40}
        ),
    )


def check_registration(owner: Identity, driver: ScriptedCheckRunner) -> RegisteredCheckRunner:
    return RegisteredCheckRunner(check_policy(owner), driver)
