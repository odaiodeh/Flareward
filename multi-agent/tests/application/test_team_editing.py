"""Editing policy authorizes the selected entity before touching a lease store."""

from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from mas.application.collaboration.editing import (
    EditEntityKind,
    EditLease,
    EditLockStore,
    TeamEditService,
)
from mas.blueprints.authoring import BlueprintAuthoringService
from mas.core.identity import Identity
from mas.resources.authoring import ResourceAuthoringService


@pytest.fixture
def editing():
    store = create_autospec(EditLockStore, instance=True)
    resources = create_autospec(ResourceAuthoringService, instance=True)
    blueprints = create_autospec(BlueprintAuthoringService, instance=True)
    owner = Identity.team("workspace")
    resources.get.return_value = blueprints.get.return_value = SimpleNamespace(identity=owner)
    store.acquire.return_value = None
    store.renew.return_value = True
    store.holders.return_value = (None,)
    return owner, store, resources, blueprints, TeamEditService(store, resources, blueprints)


@pytest.mark.parametrize("kind", list(EditEntityKind))
async def test_acquisition_checks_entity_owner_and_uses_the_trusted_actor(editing, kind):
    owner, store, resources, blueprints, service = editing
    lease = EditLease(user_id="human", display_name="human", lease_id="editor")
    assert await service.acquire(owner, kind, "entity", lease) is None
    (resources if kind == EditEntityKind.RESOURCE else blueprints).get.assert_awaited_once_with(
        "entity", owner
    )
    scope, actual, ttl = store.acquire.call_args.args
    assert scope.team_id == owner.id and actual == lease and ttl == 180


@pytest.mark.parametrize("operation", ["acquire", "renew", "holders"])
async def test_foreign_entities_are_rejected_before_lease_state_is_accessed(editing, operation):
    owner, store, resources, _, service = editing
    resources.get.return_value = SimpleNamespace(identity=Identity.team("other"))
    with pytest.raises(PermissionError):
        if operation == "holders":
            await service.holders(owner, EditEntityKind.RESOURCE, ("foreign",))
        else:
            await getattr(service, operation)(
                owner,
                EditEntityKind.RESOURCE,
                "foreign",
                EditLease(user_id="human", display_name="human"),
            )
    getattr(store, operation).assert_not_awaited()


async def test_personal_scope_cannot_be_used_as_a_team_namespace(editing):
    _, store, _, _, service = editing
    with pytest.raises(PermissionError):
        await service.acquire(
            Identity.user("human"),
            EditEntityKind.RESOURCE,
            "entity",
            EditLease(user_id="human", display_name="human"),
        )
    store.acquire.assert_not_awaited()


async def test_release_remains_possible_after_the_entity_is_deleted(editing):
    owner, store, resources, blueprints, service = editing
    await service.release(
        owner,
        EditEntityKind.RESOURCE,
        "deleted",
        EditLease(user_id="human", display_name="human", lease_id="editor"),
    )
    resources.get.assert_not_awaited()
    blueprints.get.assert_not_awaited()
    store.release.assert_awaited_once()
