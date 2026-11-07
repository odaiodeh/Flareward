"""Sessions share existing state semantics while owning distinct root executions."""

import asyncio

import pytest
from mas.application.execution.ports import ExecutionMissing
from mas.domain.execution.models import ExecutionPhase
from mas.domain.programs.models import ApplicationDefinition, PathBinding
from mas.session.domain.session_record import SessionInteraction
from mas.session.domain.status import SessionStatus
from mas.session.execution.program_sessions import (
    CreateProgramSession,
    StartSessionTurn,
)
from mas.session.execution.session_store import SessionConflict
from support.scenarios import echo_graph, finish_session, publish


async def test_structured_session_reuses_arbitrary_data_bindings_without_chat(platform, sessions):
    revision = await publish(
        platform, "data-session", ApplicationDefinition(implementation="greeting", version="1")
    )
    record = await sessions.create(
        CreateProgramSession(
            program=revision.reference,
            input_bindings={"name": PathBinding(path=("customer",))},
            output_bindings={"customer": PathBinding(path=("answer",))},
        ),
        platform.owner,
    )
    for key, inputs, expected in (
        ("data-first", {"customer": "Ada"}, "hello Ada"),
        ("data-second", {}, "hello hello Ada"),
    ):
        record = await sessions.start(
            record.run_id, StartSessionTurn(execution_id=key, inputs=inputs), platform.owner
        )
        record = await finish_session(platform.executions, sessions, record)
        assert record.status == SessionStatus.COMPLETED
        assert record.state["customer"] == expected
        assert record.graph_state is None
        assert record.interaction == SessionInteraction.DATA


async def test_graph_session_keeps_history_across_distinct_root_executions(platform, sessions):
    graph = echo_graph().model_copy(
        update={
            "inputs": {
                "user_prompt": PathBinding(path=("user_prompt",)),
                "messages": PathBinding(path=("history",)),
            },
            "outputs": {
                "answer": PathBinding(path=("output",)),
                "messages": PathBinding(path=("messages",)),
            },
        }
    )
    revision = await publish(platform, "session-graph", graph)
    record = await sessions.create(
        CreateProgramSession(
            interaction=SessionInteraction.CONVERSATION,
            program=revision.reference,
            input_bindings={"history": PathBinding(path=("messages",))},
            output_bindings={
                "messages": PathBinding(path=("messages",)),
                "output": PathBinding(path=("answer",)),
            },
        ),
        platform.owner,
    )
    for index, prompt in enumerate(("first", "second")):
        record = await sessions.start(
            record.run_id,
            StartSessionTurn(inputs={"user_prompt": prompt}, execution_id=f"turn-{index}"),
            platform.owner,
            credential_user_id="alice",
        )
        record = await finish_session(platform.executions, sessions, record)
        assert record.status == SessionStatus.COMPLETED
        assert record.graph_state.output == f"greeting:{prompt}"
        assert len(record.graph_state.messages) == index + 1
        execution = await platform.executions.get(f"turn-{index}", platform.owner)
        assert execution.session_id == record.run_id
        assert execution.parent_execution_id is None
        assert execution.context.credential_user_id() == "alice"
    assert record.metadata.title == "first"
    assert [message.content for message in record.graph_state.messages] == ["first", "second"]
    assert len(await sessions.list(platform.owner)) == 1


async def test_concurrent_turns_admit_one_and_idempotent_retry_does_not_stage_again(
    platform,
    sessions,
):
    revision = await publish(
        platform, "session-wait", ApplicationDefinition(implementation="waiting", version="1")
    )
    session = await sessions.create(
        CreateProgramSession(
            interaction=SessionInteraction.CONVERSATION, program=revision.reference
        ),
        platform.owner,
    )
    turns = [
        StartSessionTurn(inputs={"user_prompt": "once"}, execution_id=f"try-{i}") for i in range(2)
    ]
    outcomes = await asyncio.gather(
        *(sessions.start(session.run_id, turn, platform.owner) for turn in turns),
        return_exceptions=True,
    )
    assert sum(isinstance(result, SessionConflict) for result in outcomes) == 1
    current = await sessions.get(session.run_id, platform.owner)
    original = next(turn for turn in turns if turn.execution_id == current.active_execution_id)
    repeated = await sessions.start(session.run_id, original, platform.owner)
    assert len(repeated.graph_state.messages) == 1
    with pytest.raises(SessionConflict, match="different request"):
        await sessions.start(
            session.run_id, original.model_copy(update={"inputs": {}}), platform.owner
        )
    await sessions.cancel(session.run_id, platform.owner)
    current = await finish_session(platform.executions, sessions, repeated)
    assert current.status == SessionStatus.CANCELLED
    assert current.graph_state.messages[-1].metadata["is_cancelled"] is True


async def test_cancel_during_preparation_prevents_late_submission(platform, sessions, monkeypatch):
    revision = await publish(
        platform,
        "cancel-before-start",
        ApplicationDefinition(implementation="greeting", version="1"),
    )
    session = await sessions.create(
        CreateProgramSession(
            interaction=SessionInteraction.CONVERSATION, program=revision.reference
        ),
        platform.owner,
    )
    preparing, release = asyncio.Event(), asyncio.Event()
    gateway = platform.gateway
    prepare = gateway.prepare

    async def paused_prepare(*args, **kwargs):
        preparing.set()
        await release.wait()
        return await prepare(*args, **kwargs)

    monkeypatch.setattr(gateway, "prepare", paused_prepare)
    task = asyncio.create_task(
        sessions.start(
            session.run_id,
            StartSessionTurn(inputs={"name": "cancelled"}, execution_id="pre-cancelled"),
            platform.owner,
        )
    )
    await asyncio.wait_for(preparing.wait(), 5)
    cancelled = await sessions.cancel(session.run_id, platform.owner)
    release.set()
    result = await asyncio.wait_for(task, 5)
    assert cancelled.status == result.status == SessionStatus.CANCELLED
    execution = await platform.executions.get("pre-cancelled", platform.owner)
    assert execution.phase == ExecutionPhase.CANCELLED
    with pytest.raises(ExecutionMissing):
        await gateway.status(execution.engine_handle)


async def test_concurrent_identical_submissions_recover_the_same_admitted_turn(
    platform, sessions, session_store, monkeypatch
):
    revision = await publish(
        platform, "same-turn", ApplicationDefinition(implementation="waiting", version="1")
    )
    session = await sessions.create(
        CreateProgramSession(
            interaction=SessionInteraction.CONVERSATION, program=revision.reference
        ),
        platform.owner,
    )
    turn = StartSessionTurn(execution_id="same-turn", inputs={"user_prompt": "Only once"})
    barrier = asyncio.Barrier(2)
    replace = session_store.replace

    async def concurrent_admission(record, *, expected_version):
        if expected_version == session.version:
            await barrier.wait()
        return await replace(record, expected_version=expected_version)

    monkeypatch.setattr(session_store, "replace", concurrent_admission)
    async with asyncio.timeout(5):
        results = await asyncio.gather(
            *(sessions.start(session.run_id, turn, platform.owner) for _ in range(2))
        )
    assert all(record.active_execution_id == turn.execution_id for record in results)
    assert len((await sessions.get(session.run_id, platform.owner)).graph_state.messages) == 1
    await platform.executions.send(turn.execution_id, "answer", "one result", platform.owner)
    finished = await finish_session(platform.executions, sessions, results[0])
    assert finished.status == SessionStatus.COMPLETED
    assert finished.last_result == {"answer": "one result"}


async def test_old_execution_projection_cannot_overwrite_new_turn(platform, sessions, monkeypatch):
    revision = await publish(
        platform,
        "turn-fence",
        ApplicationDefinition(implementation="waiting", version="1"),
    )
    session = await sessions.create(
        CreateProgramSession(
            interaction=SessionInteraction.CONVERSATION, program=revision.reference
        ),
        platform.owner,
    )
    await sessions.start(session.run_id, StartSessionTurn(execution_id="old"), platform.owner)
    await platform.executions.send("old", "answer", "old result", platform.owner)
    await platform.executions.result("old", platform.owner)
    entered, release = asyncio.Event(), asyncio.Event()
    refresh = platform.executions.refresh

    async def delayed_observer(execution_id, caller):
        result = await refresh(execution_id, caller)
        if execution_id == "old" and not entered.is_set():
            entered.set()
            await release.wait()
        return result

    monkeypatch.setattr(platform.executions, "refresh", delayed_observer)
    old_observer = asyncio.create_task(sessions.refresh(session.run_id, platform.owner))
    await asyncio.wait_for(entered.wait(), 5)
    await sessions.refresh(session.run_id, platform.owner)
    await sessions.start(session.run_id, StartSessionTurn(execution_id="new"), platform.owner)
    release.set()
    stale = await asyncio.wait_for(old_observer, 5)
    assert stale.active_execution_id == "new"
    await platform.executions.send("new", "answer", "new result", platform.owner)
    current = await finish_session(platform.executions, sessions, stale)
    assert current.last_result == {"answer": "new result"}


async def test_invalid_output_binding_finishes_session_with_actionable_error(platform, sessions):
    revision = await publish(
        platform,
        "bad-session-binding",
        ApplicationDefinition(implementation="greeting", version="1"),
    )
    record = await sessions.create(
        CreateProgramSession(
            interaction=SessionInteraction.CONVERSATION,
            program=revision.reference,
            output_bindings={"output": PathBinding(path=("missing",))},
        ),
        platform.owner,
    )
    record = await sessions.start(
        record.run_id,
        StartSessionTurn(inputs={"name": "binding"}),
        platform.owner,
    )
    result = await finish_session(platform.executions, sessions, record)
    assert result.status == SessionStatus.FAILED
    assert "Session result binding failed" in result.metadata.status_message
    assert result.last_result == {"answer": "hello binding"}
    assert result.run_context.finished_at is not None
