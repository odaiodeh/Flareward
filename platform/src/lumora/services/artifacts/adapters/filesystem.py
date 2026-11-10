"""Stream into private staging and atomically publish an immutable artifact directory."""

import asyncio
import errno
import hashlib
import os
import re
import shutil
import tempfile
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import BinaryIO

from pydantic import ValidationError

from lumora.async_work import await_owned
from lumora.services.artifacts.domain.models import ArtifactRecord, BlobArtifactRef
from lumora.services.artifacts.ports import (
    ArtifactConflict,
    ArtifactIntegrityError,
    ArtifactMissing,
    ArtifactStorageError,
)


class FileArtifactRepository:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise ValueError("Artifact storage requires an absolute directory")
        self._root = root

    def _directory(self, artifact_id: str) -> Path:
        if re.fullmatch(r"[a-f0-9]{64}", artifact_id) is None:
            raise ArtifactMissing("Artifact not found")
        directory = self._root / artifact_id
        if directory.is_symlink():
            raise ArtifactIntegrityError("Artifact storage entry is invalid")
        return directory

    @staticmethod
    def _private_file(path: Path) -> BinaryIO:
        return open(path, "xb", opener=lambda name, flags: os.open(name, flags, 0o600))

    def _get(self, artifact_id: str) -> ArtifactRecord:
        try:
            path = self._directory(artifact_id) / "metadata.json"
            if path.is_symlink():
                raise ArtifactIntegrityError("Artifact metadata is invalid")
            with path.open("rb") as source:
                data = source.read(65_537)
            if len(data) > 65_536:
                raise ArtifactIntegrityError("Artifact metadata exceeds its limit")
            record = ArtifactRecord.model_validate_json(data)
            if record.reference.artifact_id != artifact_id:
                raise ArtifactIntegrityError("Artifact metadata identity does not match")
            return record
        except FileNotFoundError:
            raise ArtifactMissing("Artifact not found") from None
        except ValidationError:
            raise ArtifactIntegrityError("Artifact metadata is invalid") from None

    async def get(self, artifact_id: str) -> ArtifactRecord:
        try:
            return await asyncio.to_thread(self._get, artifact_id)
        except OSError:
            raise ArtifactStorageError("Artifact storage is unavailable") from None

    @staticmethod
    def _same(existing: ArtifactRecord, record: ArtifactRecord) -> ArtifactRecord:
        if not existing.matches(record):
            raise ArtifactConflict("Artifact publication key already identifies different content")
        return existing

    async def put(self, record: ArtifactRecord, content: AsyncIterable[bytes]) -> ArtifactRecord:
        stage: Path | None = None
        destination: BinaryIO | None = None

        def acquire() -> None:
            nonlocal stage, destination
            self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
            stage = Path(tempfile.mkdtemp(prefix=".upload-", dir=self._root))
            destination = self._private_file(stage / "content")

        def release() -> None:
            if destination is not None:
                destination.close()
            if stage is not None:
                try:
                    shutil.rmtree(stage)
                except FileNotFoundError:
                    pass

        def commit() -> ArtifactRecord:
            assert destination is not None and stage is not None
            destination.flush()
            os.fsync(destination.fileno())
            destination.close()
            with self._private_file(stage / "metadata.json") as metadata:
                metadata.write(record.model_dump_json().encode())
                metadata.flush()
                os.fsync(metadata.fileno())
            self._sync_directory(stage)
            try:
                stage.rename(self._directory(record.reference.artifact_id))
            except OSError as error:
                if error.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                    raise
                return self._same(self._get(record.reference.artifact_id), record)
            self._sync_directory(self._root)
            return record

        try:
            try:
                return self._same(await self.get(record.reference.artifact_id), record)
            except ArtifactMissing:
                pass
            await await_owned(asyncio.to_thread(acquire))
            assert destination is not None
            digest, size = hashlib.sha256(), 0
            async for chunk in content:
                size += len(chunk)
                if size > record.reference.size_bytes:
                    raise ArtifactIntegrityError("Artifact exceeds its declared size")
                digest.update(chunk)
                await await_owned(asyncio.to_thread(destination.write, chunk))
            if size != record.reference.size_bytes or digest.hexdigest() != record.reference.sha256:
                raise ArtifactIntegrityError("Artifact content does not match its identity")
            return await await_owned(asyncio.to_thread(commit))
        except OSError:
            raise ArtifactStorageError("Artifact storage is unavailable") from None
        finally:
            try:
                await await_owned(asyncio.to_thread(release))
            except OSError:
                raise ArtifactStorageError("Artifact staging cleanup failed") from None

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @asynccontextmanager
    async def open(self, reference: BlobArtifactRef) -> AsyncIterator[AsyncIterator[bytes]]:
        source: BinaryIO | None = None

        def acquire() -> None:
            nonlocal source
            path = self._directory(reference.artifact_id) / "content"
            if path.is_symlink():
                raise ArtifactIntegrityError("Artifact content entry is invalid")
            source = path.open("rb")

        def release() -> None:
            if source is not None:
                source.close()

        try:
            try:
                await await_owned(asyncio.to_thread(acquire))
            except FileNotFoundError:
                raise ArtifactMissing("Artifact not found") from None
            except OSError:
                raise ArtifactStorageError("Artifact storage is unavailable") from None
            assert source is not None
            yield self._chunks(source, reference)
        finally:
            try:
                await await_owned(asyncio.to_thread(release))
            except OSError:
                raise ArtifactStorageError("Artifact content cleanup failed") from None

    async def _chunks(self, source: BinaryIO, reference: BlobArtifactRef) -> AsyncIterator[bytes]:
        try:
            digest, size = hashlib.sha256(), 0
            while chunk := await await_owned(asyncio.to_thread(source.read, 1_048_576)):
                size += len(chunk)
                if size > reference.size_bytes:
                    raise ArtifactIntegrityError("Artifact stored size does not match")
                digest.update(chunk)
                yield chunk
            if size != reference.size_bytes or digest.hexdigest() != reference.sha256:
                raise ArtifactIntegrityError("Artifact stored content does not match")
        except OSError:
            raise ArtifactStorageError("Artifact storage is unavailable") from None
