"""One detached application policy resolves user/team/default/deny placement grants."""

import pytest
from mas.application.execution.profile_access import ExecutionProfileAccess
from mas.core.identity import Identity
from mas.domain.execution.profile_access import OwnerProfileRule, ProfileAccessPolicy, ProfileGrant
from mas.domain.execution_preferences import ExecutionProfileCatalog
from pydantic import ValidationError


@pytest.fixture
def installed():
    return ExecutionProfileCatalog(
        profiles=("thread", "process", "sandbox"),
        default_profile="thread",
        environment_profiles=("sandbox",),
    )


def test_unconfigured_access_retains_deployment_catalog_as_a_detached_value(installed):
    access = ExecutionProfileAccess(installed)
    assert access.catalog(Identity.user("owner")) == installed
    assert access.catalog(Identity.user("owner")) is not installed


def test_owner_type_default_explicit_deny_and_capabilities_share_one_policy(installed):
    policy = ProfileAccessPolicy(
        default=ProfileGrant(profiles=("thread",), default_profile="thread"),
        owners=(
            OwnerProfileRule(
                owner=Identity.user("same"),
                grant=ProfileGrant(profiles=("process",), default_profile="process"),
            ),
            OwnerProfileRule(
                owner=Identity.team("same"),
                grant=ProfileGrant(profiles=("sandbox",), default_profile="sandbox"),
            ),
            OwnerProfileRule(owner=Identity.user("denied")),
        ),
    )
    access = ExecutionProfileAccess(installed, policy)
    assert access.catalog(Identity.user("same", "Renamed")).profiles == ("process",)
    assert access.catalog(Identity.team("same")).environment_profiles == ("sandbox",)
    assert access.catalog(Identity.user("fallback")).profiles == ("thread",)
    with pytest.raises(PermissionError):
        access.catalog(Identity.user("denied"))
    # Mutating caller-owned identity metadata must not alter the installed policy.
    policy.owners[0].owner.id = "changed"
    assert access.catalog(Identity.user("same")).profiles == ("process",)


def test_configured_policy_without_default_denies_unmatched_and_empty_owners(installed):
    access = ExecutionProfileAccess(installed, ProfileAccessPolicy())
    for owner in (Identity.user("unmatched"), Identity.user("")):
        with pytest.raises(PermissionError):
            access.catalog(owner)


def test_unknown_policy_profile_is_a_startup_error(installed):
    with pytest.raises(ValueError, match="uninstalled"):
        ExecutionProfileAccess(
            installed,
            ProfileAccessPolicy(
                default=ProfileGrant(profiles=("missing",), default_profile="missing")
            ),
        )


def test_ambiguous_owner_rules_cannot_depend_on_config_order():
    with pytest.raises(ValidationError, match="unique"):
        ProfileAccessPolicy(
            owners=(
                OwnerProfileRule(owner=Identity.user("owner")),
                OwnerProfileRule(owner=Identity.user("owner", "Other name")),
            )
        )
