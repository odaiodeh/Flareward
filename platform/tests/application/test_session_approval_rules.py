"""Session policy commands use persistence/publication ports, never transport clients."""

import asyncio
from unittest.mock import create_autospec

import pytest

from flareward.executions.domain.context import ExecutionContext
from flareward.executions.domain.models import (
    ExecutionFailure,
    ExecutionPhase,
    ExecutionRecord,
    FailureKind,
)
from flareward.executions.models import StartExecution
from flareward.executions.ports import ExecutionError
from flareward.executions.service import ExecutionService
from flareward.programs.domain.models import ProgramRef
from flareward.programs.service import ProgramService
from flareward.services.identity.domain import Identity
from flareward.services.interactions.ports import ApprovalRulesPublisher
from flareward.services.interactions.rules import ApprovalRuleAction, ApprovalRuleChange
from flareward.services.interactions.tools.models import (
    ApprovalDecision,
    ApprovalOverrides,
    ToolAccessMode,
)
from flareward.services.sessions.domain.status import SessionStatus
from flareward.services.sessions.execution.program_sessions import ProgramSessionService
from flareward.services.sessions.execution.session_store import SessionConflict, SessionStore
from flareward.services.sessions.records import SessionRecord


@pytest.fixture
def policy_session():
    owner = Identity.user("owner")
    reference = ProgramRef(program_id="program", revision=1)
    context = ExecutionContext(
        identity=owner, session_id="chat", execution_id="turn", root_execution_id="turn"
    )
    record = SessionRecord(
        run_id="chat",
        identity=owner,
        run_context=context,
        program=reference,
        status=SessionStatus.RUNNING,
        active_execution_id="turn",
        execution_request=StartExecution(program=reference, session_id="chat", execution_id="turn"),
    )
    current = [record]
    store = create_autospec(SessionStore, instance=True)

    async def get(session_id):
        assert session_id == "chat"
        return current[0].model_copy(deep=True)

    async def replace(updated, *, expected_version):
        # Real storage awaits I/O. Yield so simultaneous commands observe a conflict.
        await asyncio.sleep(0)
        if current[0].version != expected_version:
            return False
        current[0] = updated.model_copy(deep=True)
        return True

    async def pending(*, limit=100, after_session_id=None):
        return [] if after_session_id else [current[0].model_copy(deep=True)]

    store.get.side_effect = get
    store.replace.side_effect = replace
    store.pending.side_effect = pending
    executions = create_autospec(ExecutionService, instance=True)
    execution = ExecutionRecord(
        execution_id="turn",
        owner=owner,
        session_id="chat",
        program=reference,
        inputs={},
        context=context,
        phase=ExecutionPhase.RUNNING,
    )
    executions.get.return_value = executions.refresh.return_value = execution
    programs = create_autospec(ProgramService, instance=True)
    publisher = create_autospec(ApprovalRulesPublisher, instance=True)
    service = ProgramSessionService(store, programs, executions, publisher)
    return service, store, executions, publisher, current


async def test_concurrent_rule_commands_merge_without_repeating_execution_effects(policy_session):
    service, _, executions, publisher, current = policy_session
    owner = current[0].identity
    await asyncio.gather(
        *(
            service.change_approval_rule(
                "chat", "turn", ApprovalRuleChange(action="auto_approve", tool_name=tool), owner
            )
            for tool in ("write_a", "write_b")
        )
    )
    rules = await service.approval_rules("chat", owner)
    assert rules.global_rules.auto_approve_tools == {"write_a", "write_b"}
    assert current[0].approval_rules_revision == current[0].version == 2
    assert publisher.save_rules.await_count == 2
    executions.start.assert_not_awaited()
    executions.cancel.assert_not_awaited()


async def test_persisted_rule_recovers_after_publication_failure_and_service_restart(
    policy_session,
):
    service, store, executions, publisher, current = policy_session
    publisher.save_rules.side_effect = [
        ExecutionError(ExecutionFailure(kind=FailureKind.INFRASTRUCTURE, message="Unavailable")),
        None,
    ]
    owner = current[0].identity
    with pytest.raises(ExecutionError) as error:
        await service.change_approval_rule(
            "chat", "turn", ApprovalRuleChange(action="auto_reject", tool_name="write"), owner
        )
    assert error.value.failure.code == "approval_rules_sync_pending"
    assert error.value.failure.retryable
    assert (await service.approval_rules("chat", owner)).global_rules.auto_reject_tools == {"write"}
    revision = current[0].approval_rules_revision
    restarted = ProgramSessionService(store, create_autospec(ProgramService), executions, publisher)
    await restarted.reconcile_pending()
    assert publisher.save_rules.await_count == 2
    assert all(call.kwargs["revision"] == revision for call in publisher.save_rules.await_args_list)
    assert current[0].version == revision
    executions.start.assert_not_awaited()


@pytest.mark.parametrize("invalid", ["owner", "turn", "session", "terminal"])
async def test_denied_stale_and_terminal_commands_cannot_change_policy(policy_session, invalid):
    service, store, executions, publisher, current = policy_session
    owner, execution_id = current[0].identity, "turn"
    if invalid == "owner":
        owner = Identity.user("other")
    elif invalid == "turn":
        execution_id = "old-turn"
    elif invalid == "session":
        execution = executions.refresh.return_value
        executions.refresh.return_value = execution.model_copy(
            update={
                "session_id": "another-chat",
                "context": execution.context.model_copy(update={"session_id": "another-chat"}),
            }
        )
    else:
        executions.refresh.return_value = executions.refresh.return_value.model_copy(
            update={"phase": ExecutionPhase.COMPLETED}
        )
    with pytest.raises((PermissionError, SessionConflict)):
        await service.change_approval_rule(
            "chat", execution_id, ApprovalRuleChange(action="auto_approve"), owner
        )
    store.replace.assert_not_awaited()
    publisher.save_rules.assert_not_awaited()
    assert current[0].approval_rules_revision == 0


async def test_observation_does_not_churn_versions_and_metadata_preserves_policy_revision(
    policy_session,
):
    service, store, _, publisher, current = policy_session
    owner = current[0].identity
    await service.refresh("chat", owner)
    store.replace.assert_not_awaited()
    await service.change_approval_rule(
        "chat", "turn", ApprovalRuleChange(action="auto_approve", node_uid="agent"), owner
    )
    revision = current[0].approval_rules_revision
    metadata = current[0].metadata.model_copy(update={"title": "Edited title"}, deep=True)
    await service.update_metadata("chat", metadata, owner)
    assert current[0].version > revision
    assert current[0].approval_rules_revision == revision
    assert publisher.save_rules.await_args.kwargs["revision"] == revision
    cleared = metadata.model_copy(update={"hitl_overrides": ApprovalOverrides().to_dict()})
    await service.update_metadata("chat", cleared, owner)
    assert current[0].approval_rules_revision > revision
    assert await service.approval_rules("chat", owner) == ApprovalOverrides()


def test_rule_commands_preserve_other_scopes_and_node_decisions_take_precedence():
    rules = ApprovalRuleChange(action="auto_reject").apply(ApprovalOverrides())
    rules = ApprovalRuleChange(action="auto_approve", node_uid="writer", tool_name="write").apply(
        rules
    )
    before = rules.to_dict()
    changed = ApprovalRuleChange(action="auto_reject", node_uid="writer", tool_name="write").apply(
        rules
    )
    assert rules.to_dict() == before
    assert rules.resolve("write", ToolAccessMode.WRITE, "writer") == ApprovalDecision.APPROVE
    assert changed.resolve("write", ToolAccessMode.WRITE, "writer") == ApprovalDecision.REJECT
    assert changed.global_rules == rules.global_rules
    assert changed.node_rules["writer"].auto_approve_tools == frozenset()
    cleared = ApprovalRuleChange(action=ApprovalRuleAction.CLEAR, node_uid="writer").apply(rules)
    assert cleared.node_rules == {}
    assert cleared.global_rules == rules.global_rules
    assert ApprovalRuleChange(action="clear").apply(rules) == ApprovalOverrides()
    assert (
        ApprovalRuleChange(action="clear", node_uid="missing", tool_name="write").apply(rules)
        == rules
    )
