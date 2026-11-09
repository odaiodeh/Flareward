"""Actual streaming storage, atomic retries, corruption detection and owned cleanup."""

import asyncio

import pytest
from support.artifacts import chunks, publication

from flareward.services.artifacts.access_models import ArtifactActor
from flareward.services.artifacts.adapters.filesystem import FileArtifactRepository
from flareward.services.artifacts.ports import (
    ArtifactConflict,
    ArtifactIntegrityError,
    ArtifactMissing,
)
from flareward.services.artifacts.service import ArtifactService
from flareward.services.identity.domain import Identity


@pytest.fixture
def artifact_store(tmp_path):
    root = tmp_path / "artifacts"
    return (
        root,
        ArtifactService(FileArtifactRepository(root)),
        ArtifactActor(Identity.user("owner")),
    )


async def test_content_and_metadata_survive_a_new_storage_instance(artifact_store):
    root, service, owner = artifact_store
    record = await service.publish(publication(), chunks(), owner)
    restored = ArtifactService(FileArtifactRepository(root))
    assert await restored.inspect(record.reference.artifact_id, owner) == record
    async with restored.open(record.reference, owner) as content:
        assert b"".join([chunk async for chunk in content]) == b"candidate"
    directory = root / record.reference.artifact_id
    assert (directory / "content").stat().st_mode & 0o777 == 0o600
    assert (directory / "metadata.json").stat().st_mode & 0o777 == 0o600
    assert not list(root.glob(".upload-*"))


async def test_concurrent_identical_retries_retain_one_commit(artifact_store):
    root, service, owner = artifact_store
    records = await asyncio.gather(
        *(service.publish(publication(), chunks(), owner) for _ in range(6))
    )
    assert all(record == records[0] for record in records)
    assert len(list(root.iterdir())) == 1


async def test_conflicting_concurrent_publications_do_not_replace_committed_content(artifact_store):
    root, service, owner = artifact_store
    results = await asyncio.gather(
        service.publish(publication(), chunks(), owner),
        service.publish(publication(b"different"), chunks(b"different"), owner),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ArtifactConflict) for result in results) == 1
    record = next(result for result in results if not isinstance(result, BaseException))
    async with service.open(record.reference, owner) as content:
        assert b"".join([chunk async for chunk in content]) in (b"candidate", b"different")
    assert len(list(root.iterdir())) == 1


@pytest.mark.parametrize("data", [b"wrongdata", b"short", b"too much content"])
async def test_invalid_stream_never_publishes_and_releases_staging(artifact_store, data):
    root, service, owner = artifact_store
    with pytest.raises(ArtifactIntegrityError):
        await service.publish(publication(), chunks(data), owner)
    assert not list(root.iterdir())


async def test_cancelled_upload_closes_its_file_and_removes_partial_content(
    artifact_store, monkeypatch
):
    root, service, owner = artifact_store
    repository = FileArtifactRepository(root)
    opened, started = [], asyncio.Event()
    original = repository._private_file

    def track(path):
        stream = original(path)
        opened.append(stream)
        return stream

    async def interrupted():
        yield b"can"
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(repository, "_private_file", track)
    task = asyncio.create_task(
        ArtifactService(repository).publish(publication(), interrupted(), owner)
    )
    await asyncio.wait_for(started.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert opened and all(stream.closed for stream in opened)
    assert not list(root.iterdir())


async def test_corrupt_stored_bytes_are_detected_against_the_recorded_reference(artifact_store):
    root, service, owner = artifact_store
    record = await service.publish(publication(), chunks(), owner)
    (root / record.reference.artifact_id / "content").write_bytes(b"different")
    with pytest.raises(ArtifactIntegrityError):
        async with service.open(record.reference, owner) as content:
            _ = [chunk async for chunk in content]


async def test_storage_paths_cannot_escape_through_ids_or_symlinks(artifact_store, tmp_path):
    root, service, owner = artifact_store
    with pytest.raises(ArtifactMissing):
        await service.inspect("../outside", owner)
    outside = tmp_path / "outside"
    outside.mkdir()
    root.mkdir(exist_ok=True)
    (root / ("0" * 64)).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ArtifactIntegrityError):
        await service.inspect("0" * 64, owner)
