"""Legacy-compatible invitation dates and type-aware participant identities."""

from datetime import UTC, datetime, timedelta

import pytest
from mas.core.identity import Identity
from mas.domain.sharing import ShareInvite, matches_share_identity
from pydantic import ValidationError
from support.sharing import invitation


@pytest.mark.parametrize("created", [datetime(2026, 1, 1), "2026-01-01T00:00:00Z"])
def test_expiry_uses_validated_creation_time_and_legacy_dates_are_utc(created):
    invite = invitation(created_at=created, ttl_days=3)
    assert invite.created_at == datetime(2026, 1, 1, tzinfo=UTC)
    assert invite.expires_at == invite.created_at + timedelta(days=3)
    assert invite.is_expired
    assert ShareInvite.model_validate_json(invite.model_dump_json()) == invite


def test_legacy_explicit_expiry_is_preserved_and_bad_timestamps_are_validation_errors():
    invite = invitation(expires_at="2027-01-01T00:00:00")
    assert invite.expires_at == datetime(2027, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError):
        invitation(created_at="private-invalid-date")


def test_sharing_user_compatibility_does_not_mix_team_identity_namespaces():
    assert matches_share_identity(Identity.user("Alice"), Identity.user("alice"))
    assert not matches_share_identity(Identity.user("team"), Identity.team("team"))
    assert not matches_share_identity(Identity.team("Team"), Identity.team("team"))
