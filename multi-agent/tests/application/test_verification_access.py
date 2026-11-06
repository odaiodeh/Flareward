"""A workflow capability cannot attest, widen policy/root scope or outlive revocation."""

import pytest
from mas.application.verification.access import VerificationAccessService
from mas.application.verification.access_models import (
    VerificationAccessRequest,
    VerificationAccessScope,
    VerificationAction,
    VerificationActor,
)
from mas.application.verification.ports import VerificationCredentialError, VerificationMissing
from mas.application.verification.service import VerificationService
from mas.core.identity import Identity
from pydantic import ValidationError
from support.execution_access import ExecutionAuthority
from support.verification import (
    MemoryVerificationAccessRepository,
    MemoryVerificationRepository,
    VerificationClock,
    verification_policy,
    verification_request,
)


def scope(root="root", actions=frozenset(VerificationAction), policies=frozenset({"release@1"})):
    return VerificationAccessScope(root_execution_id=root, actions=actions, policies=policies)


async def test_credentials_are_purpose_scoped_hashed_expiring_and_revocable():
    owner, clock, repository = (
        Identity.user("owner"),
        VerificationClock(),
        MemoryVerificationAccessRepository(),
    )
    service = VerificationAccessService(
        repository,
        {"release@1": verification_policy(owner)},
        clock=clock,
        execution_authority=ExecutionAuthority(),
    )
    issued = await service.issue(
        VerificationAccessRequest(scope=scope(), ttl_seconds=60), owner, owner
    )
    credential = issued.credential.get_secret_value()
    assert (await service.authenticate(credential)).issued_by.owns(owner)
    assert credential not in repository.records[issued.grant.grant_id].model_dump_json()
    assert (await service.list(Identity.team("owner"))) == []
    for invalid in (
        credential.replace("unifai-verification", "unifai-artifact"),
        credential[:-1] + ("A" if credential[-1] != "A" else "B"),
    ):
        with pytest.raises(VerificationCredentialError):
            await service.authenticate(invalid)
    clock.advance(60)
    with pytest.raises(VerificationCredentialError):
        await service.authenticate(credential)
    fresh = await service.issue(VerificationAccessRequest(scope=scope()), owner, owner)
    await service.revoke(fresh.grant.grant_id, owner)
    with pytest.raises(VerificationCredentialError):
        await service.authenticate(fresh.credential.get_secret_value())
    with pytest.raises(VerificationMissing):
        await service.revoke(issued.grant.grant_id, Identity.team("owner"))


async def test_workflow_actors_cannot_cross_root_policy_or_action_boundaries():
    owner, clock = Identity.user("owner"), VerificationClock()
    service = VerificationService(
        MemoryVerificationRepository(), {"release@1": verification_policy(owner)}, clock=clock
    )
    actor = VerificationActor(owner, scope())
    first = await service.start(verification_request(), actor)
    other = await service.start(
        verification_request(), VerificationActor(owner, scope(root="other"))
    )
    assert first.state.plan.plan_id != other.state.plan.plan_id
    assert first.state.plan.root_execution_id == "root"
    with pytest.raises(VerificationMissing):
        await service.inspect(other.state.plan.plan_id, actor)
    with pytest.raises(VerificationMissing):
        await service.inspect(
            first.state.plan.plan_id,
            VerificationActor(owner, scope(policies=frozenset({"other@1"}))),
        )
    readonly = VerificationActor(owner, scope(actions=frozenset({VerificationAction.READ})))
    assert (await service.inspect(first.state.plan.plan_id, readonly)).state == first.state
    with pytest.raises(PermissionError):
        await service.start(verification_request(), readonly)
    with pytest.raises(PermissionError):
        await service.cancel(first.state.plan.plan_id, readonly)
    assert (
        await service.inspect(other.state.plan.plan_id, VerificationActor(owner))
    ).state == other.state


async def test_issuance_requires_an_authenticated_human_and_admitted_creation_policy():
    owner = Identity.user("owner")
    service = VerificationAccessService(
        MemoryVerificationAccessRepository(),
        {"release@1": verification_policy(owner)},
        execution_authority=ExecutionAuthority(),
    )
    for issuer in (Identity.team("owner"), Identity.user("other")):
        with pytest.raises(PermissionError):
            await service.issue(VerificationAccessRequest(scope=scope()), owner, issuer)
    with pytest.raises(PermissionError):
        await service.issue(
            VerificationAccessRequest(scope=scope(policies=frozenset({"unknown@1"}))), owner, owner
        )


@pytest.mark.parametrize("values", [{"policies": []}, {"actions": []}, {"root_execution_id": ""}])
def test_workflow_access_requires_explicit_bounded_scope(values):
    data = scope().model_dump(mode="json")
    with pytest.raises(ValidationError):
        VerificationAccessScope.model_validate({**data, **values})
