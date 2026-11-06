"""Application-owned admission claim contract shared by actual storage adapters."""

from datetime import UTC, datetime, timedelta

from mas.application.execution.models import PreparedExecution, SubmissionClaim
from mas.application.execution.ports import ExecutionRepository
from mas.core.identity import Identity
from mas.domain.execution.context import ExecutionContext
from mas.domain.execution.models import ExecutionPhase, ExecutionRecord, SubmissionState
from mas.domain.programs.models import ProgramRef


async def assert_submission_claim_contract(repository: ExecutionRepository) -> None:
    owner, now = Identity.user("claim-owner"), datetime(2026, 11, 3, tzinfo=UTC)
    record = ExecutionRecord(
        execution_id="claim-run",
        owner=owner,
        program=ProgramRef(program_id="claim-contract", revision=1),
        inputs={},
        context=ExecutionContext(
            identity=owner,
            execution_id="claim-run",
            root_execution_id="claim-run",
            engine_handle="private-native-claim-run",
        ),
    )
    snapshot = PreparedExecution(format="claim-test/1", payload_json='{"frozen":true}')
    assert await repository.create(record, snapshot)
    first = SubmissionClaim(token="a" * 32, expires_at=now + timedelta(seconds=10))
    second = SubmissionClaim(token="b" * 32, expires_at=now + timedelta(seconds=25))
    assert await repository.claim_submission(record.execution_id, first, now=now)
    assert not await repository.claim_submission(
        record.execution_id, second, now=now + timedelta(seconds=1), recover=True
    )
    assert await repository.claim_submission(
        record.execution_id, second, now=now + timedelta(seconds=11), recover=True
    )
    accepted = record.model_copy(
        update={"phase": ExecutionPhase.RUNNING, "submission": SubmissionState.ACCEPTED}
    )
    assert not await repository.finish_submission(accepted, first.token)
    assert (await repository.get(record.execution_id)).submission == SubmissionState.STARTING
    assert await repository.submission_claim(record.execution_id) == second
    await repository.request_cancellation(record.execution_id)
    assert await repository.finish_submission(accepted, second.token)
    assert await repository.submission_claim(record.execution_id) is None
    assert (await repository.get(record.execution_id)).cancel_requested
    refused = record.model_copy(
        update={"phase": ExecutionPhase.FAILED, "submission": SubmissionState.REFUSED}
    )
    await repository.update(refused)
    await repository.update(accepted.model_copy(update={"cancel_requested": False}))
    latest = await repository.get(record.execution_id)
    assert latest.submission == SubmissionState.ACCEPTED and latest.phase == ExecutionPhase.RUNNING
    assert latest.cancel_requested
    assert (
        first.token not in latest.model_dump_json() and second.token not in latest.model_dump_json()
    )
    assert await repository.get_prepared(record.execution_id) == snapshot
