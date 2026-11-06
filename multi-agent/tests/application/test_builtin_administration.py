"""Curated-library policy uses owned ports and the ordinary schema/encryption path."""

from unittest.mock import create_autospec

import pytest
from mas.application.access.administrators import AdministratorAccess
from mas.application.collaboration.editing import EditLease, EditLockStore
from mas.application.resources.builtins import BuiltinAdministration, BuiltinRepository
from mas.core.identity import Identity
from mas.resources.configuration import ResourceConfiguration
from mas.resources.errors import (
    BuiltinDependentsPublicError,
    ResourceConflictError,
    ResourceLockedError,
)
from mas.resources.field_encryption import ResourceFieldEncryption
from support.builtins import ADMIN, chain, curated_record
from support.secrets import MemoryCipher


@pytest.fixture
def curated(application):
    entries = {entry.resource.rid: entry for entry in chain()}
    repository = create_autospec(BuiltinRepository, instance=True)

    async def get(rid):
        return entries[rid].model_copy(deep=True)

    repository.get.side_effect = get
    repository.dependents.return_value = ()
    repository.usage.return_value = ([], [])
    administrators = create_autospec(AdministratorAccess, instance=True)
    administrators.allowed.return_value = True
    locks = create_autospec(EditLockStore, instance=True)
    locks.holders.return_value = (None,)
    cipher = MemoryCipher()
    configuration = ResourceConfiguration(
        application.elements, ResourceFieldEncryption(application.elements, cipher)
    )
    service = BuiltinAdministration(repository, administrators, configuration, locks)
    return service, entries, repository, administrators, locks, cipher


@pytest.mark.parametrize(
    "operation", ["get", "list", "preview", "update", "delete", "acquire", "renew", "release"]
)
async def test_every_administrative_path_authorizes_before_storage(curated, operation):
    service, _, repository, administrators, locks, _ = curated
    administrators.allowed.return_value = False
    with pytest.raises(PermissionError):
        if operation == "list":
            await service.list(ADMIN)
        elif operation in {"update", "delete"}:
            await getattr(service, operation)(ADMIN, "root", expected_version=1)
        else:
            await getattr(service, operation)(ADMIN, "root")
    assert not repository.mock_calls and not locks.mock_calls


async def test_publication_is_one_atomic_change_set_with_complete_dependency_fences(curated):
    service, entries, repository, _, _, _ = curated
    view, cascade = await service.update(ADMIN, "root", expected_version=1, public=True)
    assert view.visibility == "public" and view.version == 2
    assert {item.rid for item in cascade} == {"middle", "leaf"}
    observed, changed = repository.commit.call_args.args
    assert {item.resource.rid for item in observed} == set(entries)
    assert all(item.descriptor.visibility == "public" for item in changed)
    assert entries["root"].descriptor.visibility == "draft" and entries["middle"].descriptor is None
    assert all(entry.resource.version == 1 for entry in entries.values())


async def test_selected_team_is_never_the_administrative_human(curated):
    service, _, repository, administrators, _, _ = curated
    with pytest.raises(PermissionError):
        await service.get(Identity.team(ADMIN.id), "root")
    administrators.allowed.assert_not_awaited()
    repository.get.assert_not_awaited()


@pytest.mark.parametrize("fault", ["missing", "cycle", "disabled", "inconsistent"])
async def test_invalid_dependency_closure_never_mutates(curated, fault):
    service, entries, repository, _, _, _ = curated
    if fault == "missing":
        del entries["leaf"]
    elif fault == "cycle":
        entries["leaf"] = curated_record("leaf", dependency="root")
    elif fault == "disabled":
        entries["leaf"].resource.category = "retrievers"
    else:
        entries["middle"].resource.nested_refs = []
    with pytest.raises((KeyError, ValueError)):
        await service.update(ADMIN, "root", expected_version=1, public=True)
    repository.commit.assert_not_awaited()
    assert entries["root"].descriptor.visibility == "draft"


async def test_stale_version_and_foreign_lease_cannot_overwrite(curated):
    service, _, repository, _, locks, _ = curated
    with pytest.raises(ResourceConflictError):
        await service.update(ADMIN, "root", expected_version=2, name="stale")
    locks.holders.return_value = (EditLease(user_id="other", display_name="Other admin"),)
    with pytest.raises(ResourceLockedError):
        await service.update(ADMIN, "root", expected_version=1, name="locked")
    repository.commit.assert_not_awaited()


async def test_public_dependent_blocks_demotion_before_config_or_visibility_changes(curated):
    service, entries, repository, _, _, _ = curated
    entries["root"] = curated_record("root", public=True)
    repository.dependents.side_effect = lambda rid: (
        (curated_record("public-parent", dependency="root", public=True),) if rid == "root" else ()
    )
    with pytest.raises(BuiltinDependentsPublicError):
        await service.update(ADMIN, "root", expected_version=1, public=False, name="new")
    repository.commit.assert_not_awaited()
    assert entries["root"].resource.name == "root"


async def test_new_curated_config_uses_existing_secret_protection_and_authorized_owner(curated):
    service, _, repository, administrators, _, cipher = curated
    owner = Identity.team("engineering")
    view, cascade = await service.create(
        ADMIN,
        owner,
        category="tools",
        type_key="platform_secret_tool",
        name="private",
        config={"api_key": "private-builtin-value"},
    )
    assert view.identity == owner and not cascade
    assert "private-builtin-value" not in view.model_dump_json()
    assert cipher.decrypt(view.cfg_dict["api_key"]) == "private-builtin-value"
    assert repository.commit.call_args.args[0] == ()
    administrators.allowed.return_value = False
    with pytest.raises(PermissionError):
        await service.create(
            ADMIN,
            owner,
            category="tools",
            type_key="platform_secret_tool",
            name="private",
            config={"api_key": "secret"},
        )


async def test_new_public_root_is_not_a_preexisting_read(curated):
    service, _, repository, _, _, _ = curated
    view, cascade = await service.create(
        ADMIN,
        ADMIN,
        category="tools",
        type_key="platform_dependency",
        name="new",
        config={"dependency": "$ref:middle"},
        public=True,
    )
    assert view.visibility == "public" and len(cascade) == 2
    observed, changed = repository.commit.call_args.args
    assert {item.resource.rid for item in observed} == {"middle", "leaf"}
    assert changed[0].resource.rid == view.rid
