"""Portable execution metadata requires explicit authority and JSON-only values."""

import pytest
from pydantic import SecretStr, ValidationError

from lumora.executions.domain.context import ExecutionContext
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize("payload", ({}, {"identity": None}))
def test_missing_identity_is_rejected_without_inventing_an_owner(payload):
    original = dict(payload)
    with pytest.raises(ValidationError):
        ExecutionContext.model_validate(payload)
    assert payload == original


def test_unknown_context_fields_are_rejected_instead_of_silently_discarded():
    with pytest.raises(ValidationError):
        ExecutionContext.model_validate({"identity": Identity.user("owner"), "authority": "admin"})


@pytest.mark.parametrize("value", (object(), SecretStr("private")))
def test_runtime_objects_and_secret_wrappers_cannot_cross_the_context_boundary(value):
    with pytest.raises(ValidationError):
        ExecutionContext(identity=Identity.user("owner"), tags={"nested": [value]})


def test_team_owner_and_acting_credential_user_remain_separate_across_round_trip():
    owner = Identity.team("engineering")
    context = ExecutionContext(identity=owner, tags={"trace": {"attempts": [1, 2]}})
    assert context.credential_user_id() == ""
    assert context.with_credential_user(owner.id) is context
    delegated = context.with_credential_user("alice").with_hitl(True)
    restored = ExecutionContext.model_validate_json(delegated.model_dump_json())
    assert restored.identity == owner
    assert restored.credential_user_id() == "alice"
    assert restored.hitl_enabled
    assert context.tags == {"trace": {"attempts": [1, 2]}}
