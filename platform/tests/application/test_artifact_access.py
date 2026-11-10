"""Capability policy remains independent of HTTP authentication and persistence technology."""

from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError

from lumora.services.artifacts.access import ArtifactAccessService
from lumora.services.artifacts.access_models import ArtifactAccessRequest, ArtifactAccessScope
from lumora.services.artifacts.ports import ArtifactAccessRepository, ArtifactCredentialError
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize("reason", ["expired", "revoked", "changed-secret"])
async def test_invalid_credentials_have_safe_uniform_diagnostics(reason):
    repository = create_autospec(ArtifactAccessRepository, instance=True)
    service = ArtifactAccessService(repository)
    issued = await service.issue(
        ArtifactAccessRequest(scope=ArtifactAccessScope(actions={"read"}, namespaces={"project"})),
        Identity.user("owner"),
    )
    stored = repository.create.call_args.args[0]
    token = issued.credential.get_secret_value()
    changes = {}
    if reason == "expired":
        changes["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    elif reason == "revoked":
        changes["revoked"] = True
    else:
        token = token[:-1] + ("A" if token[-1] != "A" else "B")
    repository.get.return_value = stored.model_copy(
        update={"grant": stored.grant.model_copy(update=changes)}
    )
    with pytest.raises(ArtifactCredentialError) as error:
        await service.authenticate(token)
    assert str(error.value) == "Invalid artifact credential"
    assert token not in repr(issued) and token not in repr(stored)


@pytest.mark.parametrize("actions", [{"read"}, {"publish"}])
def test_unbounded_artifact_capabilities_are_not_valid(actions):
    with pytest.raises(ValidationError):
        ArtifactAccessScope(actions=actions)
