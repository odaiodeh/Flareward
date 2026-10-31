"""Blueprint display policy depends on application ports, without HTTP or a database."""

from unittest.mock import create_autospec

import pytest
from mas.blueprints.authoring import BlueprintAuthoringService
from mas.blueprints.contracts import (
    BlueprintDocument,
    BlueprintPage,
    BlueprintResolution,
    BlueprintResolutionSource,
)
from mas.blueprints.queries import BlueprintQueryService
from mas.blueprints.schema import blueprint_schemas
from mas.core.identity import Identity
from support.blueprints import inline_blueprint, library_elements


@pytest.fixture
def queries():
    owner = Identity.user("owner")
    spec = inline_blueprint("private-display-value").model_dump(mode="json", exclude_none=True)
    spec.pop("prompt_shortcuts", None)
    resolved = blueprint_schemas(library_elements()).resolved.model_validate(spec)
    spec["prompt_shortcuts"] = [{"id": "12345678", "text": "Run"}]
    document = BlueprintDocument(blueprint_id="saved", identity=owner, spec_dict=spec)
    authoring = create_autospec(BlueprintAuthoringService, instance=True)
    authoring.get.return_value = document
    authoring.list.return_value = BlueprintPage(items=[document], total=2, skip=0, limit=1)
    source = create_autospec(BlueprintResolutionSource, instance=True)
    source.resolve.return_value = BlueprintResolution(resolved, {"gone": "Missing dependency"})
    return BlueprintQueryService(authoring, source), authoring, source, owner


async def test_display_masks_declared_credentials_without_changing_authoring_or_resolved_data(
    queries,
):
    service, authoring, source, owner = queries
    before = authoring.get.return_value.model_copy(deep=True)
    view = await service.get("saved", owner)
    assert view.spec_dict["llms"][0]["config"]["api_key"] == "********"
    assert view.spec_dict["prompt_shortcuts"] == before.spec_dict["prompt_shortcuts"]
    assert view.missing_resources == {"gone": "Missing dependency"}
    assert "private-display-value" not in view.model_dump_json()
    assert authoring.get.return_value == before
    assert source.resolve.return_value.blueprint.llms[0].config.api_key == "private-display-value"
    source.resolve.assert_awaited_once_with(before.spec_dict, owner, stored=True)
    authoring.update.assert_not_awaited()
    authoring.create.assert_not_awaited()


async def test_display_checks_authorization_before_resolving_external_resources(queries):
    service, authoring, source, _ = queries
    authoring.get.side_effect = PermissionError("Access denied")
    with pytest.raises(PermissionError):
        await service.get("saved", Identity.user("other"))
    source.resolve.assert_not_awaited()


async def test_display_page_keeps_missing_resource_reports_and_pagination(queries):
    service, authoring, _, owner = queries
    page = await service.list(owner, skip=0, limit=1, sort_desc=False)
    assert (page.total, page.skip, page.limit) == (2, 0, 1)
    assert len(page.items) == 1 and page.items[0].missing_resources == {
        "gone": "Missing dependency"
    }
    authoring.list.assert_awaited_once_with(owner, skip=0, limit=1, sort_desc=False)


async def test_summaries_do_not_resolve_elements_or_return_configuration(queries):
    service, authoring, source, owner = queries
    summaries = await service.summaries(owner, limit=1)
    assert summaries[0].name == "Authored blueprint"
    assert summaries[0].identity == owner
    assert "spec_dict" not in summaries[0].model_dump()
    source.resolve.assert_not_awaited()
    authoring.list.assert_awaited_once_with(owner, skip=0, limit=1, sort_desc=True)
