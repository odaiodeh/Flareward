"""Native inspection owns blocking probes, including sibling failures and cancellation."""

import asyncio
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from pymongo.errors import PyMongoError

from flareward.elements.exceptions import ElementInspectionError
from flareward.elements.validation import ElementValidationResult
from flareward.resources.adapters.mongo.resource_inspection import StoredResourceProbe
from flareward.resources.builtin_aware_service import BuiltinAwareResourceService
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.errors import ResourceStorageError
from flareward.resources.probes import InspectionContext
from flareward.services.identity.domain import Identity


@pytest.fixture
def inspection_case():
    service = create_autospec(BuiltinAwareResourceService, instance=True)
    return service, StoredResourceProbe(service)


async def test_inspection_preserves_owner_and_human_identity_at_all_entrypoints(inspection_case):
    service, inspection = inspection_case
    owner = Identity.team("workspace")
    service.validate_resource_async.return_value = ElementValidationResult(
        is_valid=True, element_rid="resource", element_type="fixture"
    )
    results = await inspection.validate(
        ["resource", "resource"], InspectionContext(owner, "human"), timeout_seconds=2
    )
    assert len(results) == 2 and all(result.is_valid for result in results)
    for call in service.validate_resource_async.call_args_list:
        assert call.kwargs["caller"].identity == owner
        assert call.kwargs["user_id"] == "workspace"
        assert call.kwargs["credential_user_id"] == "human"
        assert call.kwargs["timeout_seconds"] == 2
    await inspection.validate_config(
        ResourceCategory.LLM, "mock", {}, InspectionContext(owner, "human")
    )
    assert service.validate_config_async.call_args.kwargs["caller"].identity == owner
    assert service.validate_config_async.call_args.kwargs["credential_user_id"] == "human"
    await inspection.cards(["resource"], InspectionContext(owner))
    assert service.get_cards.call_args.kwargs["caller"].identity == owner


@pytest.mark.parametrize(
    "error,expected",
    [
        (PyMongoError("private-value"), ResourceStorageError),
        (RuntimeError("private-value"), ElementInspectionError),
        (
            ValidationError.from_exception_data(
                "Config", [{"type": "int_parsing", "loc": ("field",), "input": "private-value"}]
            ),
            ValueError,
        ),
    ],
)
async def test_inspection_translates_storage_schema_and_provider_failures(
    inspection_case, error, expected
):
    service, inspection = inspection_case
    service.get_cards.side_effect = error
    with pytest.raises(expected) as raised:
        await inspection.cards(["resource"], InspectionContext(Identity.user("owner")))
    assert "private-value" not in str(raised.value)
    service.validate_resource_async.side_effect = KeyError("private-value")
    result = await inspection.validate(["missing"], InspectionContext(Identity.user("owner")))
    assert not result[0].is_valid and "private-value" not in result[0].model_dump_json()


@pytest.mark.parametrize("cancel", [False, True])
async def test_inspection_drains_siblings_before_failure_or_cancellation(inspection_case, cancel):
    service, inspection = inspection_case
    entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def validate(rid, **kwargs):
        if rid == "failure":
            await entered.wait()
            raise RuntimeError("private-failure")
        entered.set()
        try:
            await release.wait()
        finally:
            await release.wait()
            finished.set()
        return ElementValidationResult(is_valid=True, element_rid=rid, element_type="fixture")

    service.validate_resource_async.side_effect = validate
    task = asyncio.create_task(
        inspection.validate(["slow", "failure"], InspectionContext(Identity.user("owner")))
    )
    try:
        async with asyncio.timeout(5):
            await entered.wait()
        if cancel:
            task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError if cancel else ElementInspectionError):
        await task
    assert finished.is_set()
