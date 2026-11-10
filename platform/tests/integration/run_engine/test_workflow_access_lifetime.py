"""Both workflow grant purposes follow actual native root completion/cancellation."""

import pytest
from support.reviews import MemoryReviewAccess, review_policy
from support.scenarios import publish
from support.verification import MemoryVerificationAccessRepository, verification_policy

from lumora.executions.access import ExecutionGrantAccess
from lumora.executions.domain.models import TERMINAL_PHASES
from lumora.executions.models import StartExecution
from lumora.programs.domain.models import ApplicationDefinition
from lumora.services.reviews.access import ReviewAccessRequest, ReviewAccessService, ReviewScope
from lumora.services.reviews.ports import ReviewCredentialError
from lumora.services.verification.access import VerificationAccessService
from lumora.services.verification.access_models import (
    VerificationAccessRequest,
    VerificationAccessScope,
    VerificationAction,
)
from lumora.services.verification.ports import VerificationCredentialError


@pytest.mark.parametrize("purpose", ["review", "verification"])
@pytest.mark.parametrize("finish", ["complete", "cancel"])
async def test_workflow_token_loses_authority_without_waiting_for_projection_or_expiry(
    platform, purpose, finish
):
    owner = platform.owner
    authority = ExecutionGrantAccess(platform.records, platform.gateway)
    if purpose == "review":
        access = ReviewAccessService(
            MemoryReviewAccess(), {"release@1": review_policy(owner)}, execution_authority=authority
        )
        request = ReviewAccessRequest(
            scope=ReviewScope(
                root_execution_id="root",
                policies=frozenset({"release@1"}),
                actions=frozenset({"open", "read", "close"}),
            )
        )
        _, token = await access.issue(request, owner, owner)
        error = ReviewCredentialError
    else:
        access = VerificationAccessService(
            MemoryVerificationAccessRepository(),
            {"release@1": verification_policy(owner)},
            execution_authority=authority,
        )
        request = VerificationAccessRequest(
            scope=VerificationAccessScope(
                root_execution_id="root",
                policies=frozenset({"release@1"}),
                actions=frozenset(VerificationAction),
            )
        )
        token = (await access.issue(request, owner, owner)).credential
        error = VerificationCredentialError
    credential = token.get_secret_value()
    with pytest.raises(error):
        await access.authenticate(credential)
    program = await publish(
        platform, "waiting", ApplicationDefinition(implementation="waiting", version="1")
    )
    record = await platform.executions.start(
        StartExecution(program=program.reference, execution_id="root"), owner
    )
    assert (await access.authenticate(credential)).owner.owns(owner)
    if finish == "complete":
        await platform.executions.send("root", "answer", {"done": True}, owner)
        await (await platform.host.get_handle(record.engine_handle)).result()
        assert (await platform.records.get("root")).phase not in TERMINAL_PHASES
    else:
        await platform.executions.cancel("root", owner)
    with pytest.raises(error):
        await access.authenticate(credential)
    with pytest.raises(PermissionError):
        await access.issue(request, owner, owner)
