"""Actions use explicit registrations, independent data, trusted context and async effects."""

import asyncio

import pytest
from support.action_scenarios import (
    FailingAction,
    IdentityAction,
    IdentityInput,
    IdentityOutput,
    InvalidOutputAction,
)

from flareward.resources.domain.categories import AuthErrorCode
from flareward.services.actions.auth.discovery.action import DiscoveryAction
from flareward.services.actions.contracts import ActionContext, ActionType
from flareward.services.actions.service import (
    ActionExecutionFailed,
    ActionInputInvalid,
    ActionMissing,
    ActionsService,
)
from flareward.services.identity.domain import Identity


def context(user="alice"):
    return ActionContext(owner=Identity.team("team"), credential_user_id=user)


async def test_registrations_and_metadata_are_per_service_and_detached():
    first, second = ActionsService((IdentityAction(),)), ActionsService()
    metadata = first.get_actions_metadata(element_type="fixture", tags={"identity"})
    assert [item.uid for item in metadata] == ["fixture.identity"]
    assert not second.get_actions_metadata()
    assert not first.get_actions_metadata(element_type="other")
    assert not first.get_actions_metadata(action_type=ActionType.DISCOVERY)
    metadata[0].input_schema.clear()
    assert first.get_actions_metadata()[0].input_schema["properties"]
    with pytest.raises(ValueError, match="Duplicate action registration"):
        first.register_instance(IdentityAction())
    with pytest.raises(ActionMissing, match="Action not found"):
        await second.execute("fixture.identity", {}, context())


def test_registration_rejects_classes_and_synchronous_implementations_before_dispatch():
    class SyncAction(IdentityAction):
        def execute(self, input_data, context):
            return None

    for action in (IdentityAction, SyncAction()):
        with pytest.raises(TypeError, match="async action instances"):
            ActionsService((action,))


async def test_concurrent_invocations_use_authenticated_humans_and_preserve_team_ownership():
    service = ActionsService((IdentityAction(),))
    authored = {"user_id": "forged", "count": 7}
    results = await asyncio.gather(
        *(service.execute("fixture.identity", authored, context(user)) for user in ("alice", "bob"))
    )
    assert [result.actor for result in results] == ["alice", "bob"]
    assert all(result.owner == "team" and result.count == 7 for result in results)
    assert authored == {"user_id": "forged", "count": 7}


@pytest.mark.parametrize(
    "uid,arguments,error",
    [
        ("fixture.identity", {"count": "private-input"}, ActionInputInvalid),
        ("fixture.failure", {}, ActionExecutionFailed),
        ("fixture.invalid-output", {}, ActionExecutionFailed),
    ],
)
async def test_contract_and_provider_errors_do_not_echo_inputs_or_provider_values(
    uid, arguments, error
):
    service = ActionsService((IdentityAction(), FailingAction(), InvalidOutputAction()))
    with pytest.raises(error) as caught:
        await service.execute(uid, arguments, context())
    assert "private" not in str(caught.value)


async def test_cancellation_reaches_the_action_and_is_not_reported_as_a_business_result():
    started, released = asyncio.Event(), asyncio.Event()

    class WaitingAction(IdentityAction):
        async def execute(
            self, input_data: IdentityInput, context: ActionContext
        ) -> IdentityOutput:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                released.set()

    service = ActionsService((WaitingAction(),))
    task = asyncio.create_task(service.execute("fixture.identity", {}, context()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert released.is_set()


async def test_disabled_credential_backend_is_not_misreported_as_an_unauthenticated_user():
    service = ActionsService((DiscoveryAction(),))
    result = await service.execute("auth.discovery", {"server_identifier": "fixture"}, context())
    assert not result.success and result.error_code == AuthErrorCode.AUTH_SERVICE_UNAVAILABLE
