"""Blueprint library reads remain owned and safe before application inspection begins."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import create_autospec

import pytest
from mas.blueprints.exceptions import BlueprintStorageError
from mas.blueprints.resolver import BlueprintResolver
from mas.blueprints.schema import blueprint_schemas
from mas.core.identity import Identity
from outbound.mongo.blueprint_resolution import StoredBlueprintResolution
from pymongo.errors import PyMongoError
from support.blueprints import inline_blueprint, library_elements


@pytest.fixture
def source_case():
    resolver = create_autospec(BlueprintResolver, instance=True)
    resolver.resolve_tolerant.return_value = (SimpleNamespace(), {})
    return resolver, StoredBlueprintResolution(
        resolver, blueprint_schemas(library_elements()).draft
    )


async def test_saved_reads_tolerate_retired_fields_and_forward_caller_scope(source_case):
    resolver, source = source_case
    owner = Identity.team("team")
    data = {**inline_blueprint().model_dump(mode="json"), "retired_field": "legacy"}
    assert (
        await source.resolve(data, owner, stored=True)
    ).blueprint is resolver.resolve_tolerant.return_value[0]
    assert resolver.resolve_tolerant.call_args.args[1].identity == owner
    with pytest.raises(ValueError) as raised:
        await source.resolve(data, owner, stored=False)
    assert "legacy" not in str(raised.value)
    resolver.resolve_tolerant.side_effect = PyMongoError("private-storage-value")
    with pytest.raises(BlueprintStorageError) as raised:
        await source.resolve(data, owner, stored=True)
    assert "private-storage-value" not in str(raised.value)


async def test_cancelled_library_resolution_finishes_before_owner_cleanup(source_case):
    resolver, source = source_case
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    loop_thread = threading.get_ident()

    def resolve(*args):
        assert threading.get_ident() != loop_thread
        entered.set()
        assert release.wait(5)
        finished.set()
        return SimpleNamespace(), {}

    resolver.resolve_tolerant.side_effect = resolve
    task = asyncio.create_task(source.resolve({"plan": []}, Identity.user("owner"), stored=False))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()
