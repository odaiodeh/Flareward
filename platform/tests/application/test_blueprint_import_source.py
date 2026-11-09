"""Import reuses authoring ownership and resolution without a second storage path."""

from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest

from flareward.programs.templates.authoring import BlueprintAuthoringService
from flareward.programs.templates.contracts import (
    BlueprintDocument,
    BlueprintResolution,
    BlueprintResolutionSource,
)
from flareward.programs.templates.resolution import BlueprintImportSource


@pytest.fixture
def source_case(application):
    authoring = create_autospec(BlueprintAuthoringService, instance=True)
    authoring.get.return_value = BlueprintDocument(
        blueprint_id="source", identity=application.owner, spec_dict={"plan": []}
    )
    resolution = create_autospec(BlueprintResolutionSource, instance=True)
    resolution.resolve.return_value = BlueprintResolution(SimpleNamespace(), {})
    return authoring, resolution, BlueprintImportSource(authoring, resolution)


async def test_import_authorizes_before_resolution(application, source_case):
    authoring, resolution, source = source_case
    authoring.get.side_effect = PermissionError("The caller does not own this blueprint")
    with pytest.raises(PermissionError):
        await source.resolve("source", application.owner)
    resolution.resolve.assert_not_awaited()


async def test_import_uses_the_shared_saved_resolution_contract(application, source_case):
    authoring, resolution, source = source_case
    result = await source.resolve("source", application.owner)
    authoring.get.assert_awaited_once_with("source", application.owner)
    resolution.resolve.assert_awaited_once_with({"plan": []}, application.owner, stored=True)
    assert result is resolution.resolve.return_value.blueprint


async def test_import_rejects_missing_dependencies_instead_of_saving_a_partial_program(
    application, source_case
):
    _, resolution, source = source_case
    resolution.resolve.return_value = BlueprintResolution(SimpleNamespace(), {"missing": "Missing"})
    with pytest.raises(KeyError, match="missing"):
        await source.resolve("source", application.owner)
