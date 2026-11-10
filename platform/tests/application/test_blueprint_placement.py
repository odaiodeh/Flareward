"""Placement inspection authorizes before resolving and performs no publication writes."""

from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from support.scenarios import echo_graph

from lumora.executions.domain.placement import GraphPlacementPlan
from lumora.executions.placement import GraphPlacementPreviewer
from lumora.programs.blueprints import BlueprintProgramImporter
from lumora.programs.domain.models import ProgramDefinition
from lumora.programs.templates.authoring import BlueprintAuthoringService
from lumora.programs.templates.contracts import (
    BlueprintDocument,
    BlueprintResolution,
    BlueprintResolutionSource,
)
from lumora.programs.templates.placement import BlueprintPlacementService


@pytest.fixture
def placement_case(application):
    authoring = create_autospec(BlueprintAuthoringService, instance=True)
    source = create_autospec(BlueprintResolutionSource, instance=True)
    source.resolve.return_value = BlueprintResolution(SimpleNamespace(), {})
    importer = create_autospec(BlueprintProgramImporter, instance=True)
    definition = ProgramDefinition(
        program_id="preview", name="Preview", owner=application.owner, implementation=echo_graph()
    )
    importer.convert.return_value = definition
    previewer = create_autospec(GraphPlacementPreviewer, instance=True)
    previewer.preview.return_value = GraphPlacementPlan(
        default_profile="thread", invocations=(), environments={}
    )
    return (
        authoring,
        source,
        importer,
        previewer,
        BlueprintPlacementService(authoring, source, importer, previewer),
    )


async def test_draft_preview_resolves_without_saving(application, placement_case):
    authoring, source, importer, previewer, service = placement_case
    result = await service.preview(application.owner, spec={"plan": []})
    source.resolve.assert_awaited_once_with({"plan": []}, application.owner, stored=False)
    assert importer.convert.call_args.kwargs["owner"] == application.owner
    assert importer.convert.call_args.kwargs["program_id"].startswith("preview-")
    previewer.preview.assert_awaited_once_with(importer.convert.return_value, application.owner)
    assert result == previewer.preview.return_value
    authoring.get.assert_not_awaited()
    authoring.create.assert_not_awaited()


async def test_saved_preview_checks_owner_before_resolving(application, placement_case):
    authoring, source, importer, previewer, service = placement_case
    authoring.get.side_effect = PermissionError("Not the owner")
    with pytest.raises(PermissionError):
        await service.preview(application.owner, blueprint_id="private")
    source.resolve.assert_not_awaited()
    importer.convert.assert_not_called()
    previewer.preview.assert_not_awaited()


async def test_saved_preview_reuses_stored_resolution(application, placement_case):
    authoring, source, _, _, service = placement_case
    authoring.get.return_value = BlueprintDocument(
        blueprint_id="stored", identity=application.owner, spec_dict={"plan": []}
    )
    await service.preview(application.owner, blueprint_id="stored")
    source.resolve.assert_awaited_once_with({"plan": []}, application.owner, stored=True)


async def test_missing_resources_cannot_produce_a_partial_preview(application, placement_case):
    _, source, importer, previewer, service = placement_case
    source.resolve.return_value = BlueprintResolution(SimpleNamespace(), {"resource": "Missing"})
    with pytest.raises(KeyError, match="Blueprint resource not found"):
        await service.preview(application.owner, spec={"plan": []})
    importer.convert.assert_not_called()
    previewer.preview.assert_not_awaited()
