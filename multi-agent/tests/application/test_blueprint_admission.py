"""Blueprint ownership and caller scope are application responsibilities."""

from unittest.mock import create_autospec

import pytest
from mas.blueprints.models.blueprint import BlueprintDocument
from mas.blueprints.repository.repository import BlueprintRepository
from mas.blueprints.resolver import BlueprintResolver
from mas.blueprints.service import BlueprintService
from mas.core.caller_scope import CallerScope
from mas.core.identity import Identity


def test_unowned_blueprint_is_denied_before_configuration_is_parsed():
    repository = create_autospec(BlueprintRepository, instance=True)
    repository.load.return_value = BlueprintDocument(
        blueprint_id="private",
        identity=Identity.user("owner"),
        spec_dict={"nodes": "invalid-private-configuration"},
    )
    resolver = create_autospec(BlueprintResolver, instance=True)
    service = BlueprintService(repository, resolver)
    with pytest.raises(PermissionError):
        service.load_owned_resolved("private", Identity.user("other"))
    resolver.resolve.assert_not_called()


def test_owned_blueprint_is_resolved_with_its_callers_scope_and_legacy_fields_tolerated():
    owner = Identity.team("team")
    repository = create_autospec(BlueprintRepository, instance=True)
    repository.load.return_value = BlueprintDocument(
        blueprint_id="owned",
        identity=owner,
        spec_dict={"name": "Owned", "plan": [], "retired_field": "stored-legacy-value"},
    )
    resolver = create_autospec(BlueprintResolver, instance=True)
    service = BlueprintService(repository, resolver)
    result = service.load_owned_resolved("owned", owner)
    assert result is resolver.resolve.return_value
    draft = resolver.resolve.call_args.args[0]
    assert draft.name == "Owned" and "retired_field" not in type(draft).model_fields
    assert resolver.resolve.call_args.kwargs["caller"] == CallerScope(identity=owner)
