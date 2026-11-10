"""Inspection authorization selects explicit base/overlay views through owned probe ports."""

from unittest.mock import create_autospec

import pytest
from support.builtins import ADMIN, curated_record

from lumora.elements.validation import ElementValidationResult
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.inspection import ResourceInspectionService
from lumora.resources.probes import InspectionMode, InspectionResourceReader, ResourceProbe
from lumora.services.access.administrators import AdministratorAccess
from lumora.services.identity.domain import Identity


@pytest.fixture
def inspection():
    probe = create_autospec(ResourceProbe, instance=True)
    administrators = create_autospec(AdministratorAccess, instance=True)
    resources = create_autospec(InspectionResourceReader, instance=True)
    administrators.allowed.return_value = True
    resources.get.return_value = curated_record("model")
    result = ElementValidationResult(is_valid=True, element_rid="model", element_type="mock")
    probe.validate.return_value, probe.validate_config.return_value = [result], result
    return (
        ResourceInspectionService(probe, administrators, resources),
        probe,
        administrators,
        resources,
    )


@pytest.mark.parametrize("inline", [False, True])
async def test_human_admin_authority_precedes_base_probing(inspection, inline):
    service, probe, administrators, resources = inspection
    administrators.allowed.return_value = False
    with pytest.raises(PermissionError):
        if inline:
            await service.validate_curated_config(ResourceCategory.LLM, "mock", {}, ADMIN, ADMIN)
        else:
            await service.validate_curated(["model"], ADMIN, ADMIN)
    assert not probe.mock_calls and not resources.mock_calls


async def test_base_inspection_keeps_workspace_and_real_credential_human_without_overlays(
    inspection,
):
    service, probe, _, resources = inspection
    owner = Identity.team("engineering")
    report = await service.validate_curated(["model"], ADMIN, owner, timeout_seconds=2)
    assert report.mode == "curated_base" and report.results[0].is_valid
    context = probe.validate.call_args.args[1]
    assert context.owner == owner and context.credential_user_id == ADMIN.id
    assert context.scope.identity is None and context.scope.is_admin
    resources.get.assert_awaited_once_with("model")
    assert probe.validate.call_args.kwargs["timeout_seconds"] == 2


async def test_public_inspection_cannot_inherit_admin_authority(inspection):
    service, probe, administrators, _ = inspection
    owner = Identity.team("engineering")
    await service.validate(["model"], owner, credential_user_id=ADMIN.id, timeout_seconds=2)
    context = probe.validate.call_args.args[1]
    assert context.mode == InspectionMode.OWNER and not context.scope.is_admin
    assert context.scope.identity == owner and context.credential_user_id == ADMIN.id
    await service.cards(["model"], owner)
    assert not probe.cards.call_args.args[1].scope.is_admin
    administrators.allowed.assert_not_awaited()


async def test_team_and_custom_resources_do_not_become_curated_by_assertion(inspection):
    service, probe, administrators, resources = inspection
    with pytest.raises(PermissionError):
        await service.validate_curated(["model"], Identity.team(ADMIN.id), ADMIN)
    administrators.allowed.assert_not_awaited()
    resources.get.return_value = curated_record("model", public=None)
    with pytest.raises(ValueError, match="requires built-in"):
        await service.validate_curated(["model"], ADMIN, ADMIN)
    probe.validate.assert_not_awaited()


@pytest.mark.parametrize(
    "rids,timeout", [(["model"] * 101, 10), ([""], 10), (["model"], 61), (["model"], float("nan"))]
)
async def test_invalid_bounds_never_dispatch_probes(inspection, rids, timeout):
    service, probe, _, _ = inspection
    with pytest.raises(ValueError):
        await service.validate_curated(rids, ADMIN, ADMIN, timeout_seconds=timeout)
    probe.validate.assert_not_awaited()
