"""Lost acknowledgments recover the exact stored request through a real Local host."""

import asyncio

import pytest
from mas.execution.models import ExecutionPhase, StartExecution, SubmissionState
from mas.execution.service import ExecutionService
from mas.programs.models import ApplicationDefinition
from outbound.run_engine.gateway import RunEngineGateway
from runengine.coordination.errors import RunContractError, RunSubmissionError
from runengine.coordination.ports import RunHost
from support.scenarios import publish


class ReplyLossHost(RunHost):
    def __init__(self, host, *, before=False, hold=False, collision=False):
        self.host = host
        self.before = before
        self.hold = hold
        self.collision = collision
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.requests = []

    @property
    def capabilities(self):
        return self.host.capabilities

    async def start(self, request):
        self.requests.append(request.model_dump_json())
        if self.collision:
            raise RunContractError.already_exists(request.run_id)
        if self.before and len(self.requests) == 1:
            raise RunSubmissionError("Request reply lost before acceptance", run_id=request.run_id)
        handle = await self.host.start(request)
        self.started.set()
        if self.hold:
            await self.release.wait()
        if len(self.requests) == 1:
            raise RunSubmissionError("Accepted start reply lost", run_id=request.run_id)
        return handle

    async def get_handle(self, run_id):
        if self.collision:
            pytest.fail("A refused collision must never grant ownership")
        return await self.host.get_handle(run_id)

    async def shutdown(self):
        await self.host.shutdown()


async def request(platform):
    revision = await publish(
        platform,
        "recover",
        ApplicationDefinition(
            implementation="greeting",
            version="1",
            config={"prefix": "original "},
        ),
    )
    return StartExecution(
        program=revision.reference, inputs={"name": "result"}, execution_id="public-id"
    )


async def test_accepted_start_with_lost_reply_reconnects_without_another_start(platform):
    host = ReplyLossHost(platform.host)
    service = ExecutionService(
        platform.programs, platform.records, RunEngineGateway(host, platform.compiler)
    )
    submission = await request(platform)
    pending = await service.start(submission, platform.owner)
    assert pending.submission == SubmissionState.UNCONFIRMED
    assert pending.engine_handle != pending.execution_id
    recovered = await service.start(submission, platform.owner)
    result = await service.result(recovered.execution_id, platform.owner)
    assert result.phase == ExecutionPhase.COMPLETED
    assert result.result == {"answer": "original result"}
    assert len(host.requests) == 1


async def test_unaccepted_start_reuses_persisted_snapshot_after_service_restart(
    platform, monkeypatch
):
    host = ReplyLossHost(platform.host, before=True)
    gateway = RunEngineGateway(host, platform.compiler)
    service = ExecutionService(platform.programs, platform.records, gateway)
    submission = await request(platform)
    await service.start(submission, platform.owner)

    async def refuse_recompilation(*args, **kwargs):
        pytest.fail("Recovery must not compile a new request")

    monkeypatch.setattr(platform.compiler, "compile", refuse_recompilation)
    restarted = ExecutionService(platform.programs, platform.records, gateway)
    recovered = await restarted.start(submission, platform.owner)
    result = await restarted.result(recovered.execution_id, platform.owner)
    assert result.result == {"answer": "original result"}
    assert len(host.requests) == 2
    assert host.requests[0] == host.requests[1]


async def test_cancelling_submission_wait_preserves_recovery_identity(platform):
    host = ReplyLossHost(platform.host, hold=True)
    service = ExecutionService(
        platform.programs, platform.records, RunEngineGateway(host, platform.compiler)
    )
    submission = await request(platform)
    task = asyncio.create_task(service.start(submission, platform.owner))
    await host.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    record = await service.get("public-id", platform.owner)
    assert record.submission == SubmissionState.UNCONFIRMED
    result = await service.result("public-id", platform.owner)
    assert result.phase == ExecutionPhase.COMPLETED
    assert len(host.requests) == 1


async def test_first_start_collision_is_refused_without_adopting_foreign_execution(platform):
    host = ReplyLossHost(platform.host, collision=True)
    service = ExecutionService(
        platform.programs, platform.records, RunEngineGateway(host, platform.compiler)
    )
    record = await service.start(await request(platform), platform.owner)
    assert record.phase == ExecutionPhase.FAILED
    assert record.submission == SubmissionState.REFUSED
    await service.cancel(record.execution_id, platform.owner)
    assert (
        await service.result(record.execution_id, platform.owner)
    ).phase == ExecutionPhase.FAILED


async def test_reconciliation_persists_results_without_an_http_result_reader(platform):
    submission = await request(platform)
    record = await platform.executions.start(submission, platform.owner)
    await platform.host.get_handle(record.engine_handle)
    await (await platform.host.get_handle(record.engine_handle)).result()
    await platform.executions.reconcile_pending()
    stored = await platform.records.get(record.execution_id)
    assert stored.phase == ExecutionPhase.COMPLETED
    assert stored.result == {"answer": "original result"}


async def test_inputs_are_detached_before_async_compilation(platform, monkeypatch):
    submission = await request(platform)
    entered, release = asyncio.Event(), asyncio.Event()
    gateway = platform.gateway
    original = gateway.prepare

    async def paused(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(gateway, "prepare", paused)
    task = asyncio.create_task(platform.executions.start(submission, platform.owner))
    await asyncio.wait_for(entered.wait(), 5)
    submission.inputs["name"] = "changed after submission"
    release.set()
    record = await task
    result = await platform.executions.result(record.execution_id, platform.owner)
    assert result.inputs == {"name": "result"}
    assert result.result == {"answer": "original result"}


async def test_reconciliation_advances_past_waiting_and_broken_records(platform, monkeypatch):
    waiting = await publish(
        platform, "scanner-wait", ApplicationDefinition(implementation="waiting", version="1")
    )
    greeting = await publish(
        platform, "scanner-finish", ApplicationDefinition(implementation="greeting", version="1")
    )
    first = await platform.executions.start(
        StartExecution(program=waiting.reference, execution_id="a"),
        platform.owner,
    )
    await platform.executions.start(
        StartExecution(program=greeting.reference, execution_id="z", inputs={"name": "last"}),
        platform.owner,
    )
    gateway = platform.gateway
    status = gateway.status

    async def isolated_error(handle):
        if handle == first.engine_handle:
            raise RuntimeError("One unavailable host record")
        return await status(handle)

    monkeypatch.setattr(gateway, "status", isolated_error)
    async with asyncio.timeout(5):
        while True:
            await platform.executions.reconcile_pending(limit=1)
            current = await platform.executions.get("z", platform.owner)
            if current.phase == ExecutionPhase.COMPLETED:
                break
            await asyncio.sleep(0.01)
    assert current.result == {"answer": "hello last"}
