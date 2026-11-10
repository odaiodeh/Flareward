"""Contained POSIX workspace file access with pinned directory handles and atomic writes."""

import asyncio
import errno
import hashlib
import os
import stat
from collections.abc import AsyncIterable, AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from lumora.async_work import await_owned
from lumora.executions.domain.context import ExecutionContext
from lumora.services.artifacts.domain.models import ContentIdentity
from lumora.services.artifacts.ports import (
    ArtifactConflict,
    ArtifactIntegrityError,
    ArtifactLimitExceeded,
    ArtifactStorageError,
    FileSource,
)
from lumora.services.workspaces.domain.files import WorkspaceFile
from plugins.workspaces import WorkspacePaths


class WorkspaceFileSystem:
    def __init__(self, root: Path, *, max_bytes: int) -> None:
        if not root.is_absolute() or max_bytes < 1:
            raise ValueError("Workspace files require an absolute root and positive byte limit")
        self._paths, self._max_bytes = WorkspacePaths(root), max_bytes

    def _parent(
        self, file: WorkspaceFile, context: ExecutionContext, *, create: bool
    ) -> tuple[int, str]:
        return self._paths.parent(
            f"{file.workspace}/{file.path}", context.root_execution_id, create=create
        )

    @staticmethod
    def _open(directory: int, name: str) -> BinaryIO:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise PermissionError("Workspace source must be a regular file")
            return os.fdopen(descriptor, "rb")
        except BaseException:
            os.close(descriptor)
            raise

    def _identify(self, source: BinaryIO) -> ContentIdentity:
        digest, size = hashlib.sha256(), 0
        while chunk := source.read(1_048_576):
            size += len(chunk)
            if size > self._max_bytes:
                raise ArtifactLimitExceeded("Workspace file exceeds its byte limit")
            digest.update(chunk)
        source.seek(0)
        return ContentIdentity(sha256=digest.hexdigest(), size_bytes=size)

    async def _chunks(self, source: BinaryIO) -> AsyncIterator[bytes]:
        size = 0
        while chunk := await self._io(partial(source.read, 1_048_576)):
            size += len(chunk)
            if size > self._max_bytes:
                raise ArtifactLimitExceeded("Workspace file exceeds its byte limit")
            yield chunk

    @staticmethod
    def _failure(error: OSError) -> Exception:
        if isinstance(error, PermissionError) and error.errno is None:
            return PermissionError("Workspace access is not permitted")
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            return PermissionError("Workspace paths must not contain symbolic links")
        if error.errno == errno.ENOENT:
            return FileNotFoundError("Workspace file not found")
        return ArtifactStorageError("Workspace file access is unavailable")

    async def _io[T](self, operation: Callable[[], T]) -> T:
        try:
            return await await_owned(asyncio.to_thread(operation))
        except OSError as error:
            raise self._failure(error) from None

    @asynccontextmanager
    async def source(
        self, file: WorkspaceFile, context: ExecutionContext
    ) -> AsyncIterator[FileSource]:
        source: BinaryIO | None = None

        def acquire() -> ContentIdentity:
            nonlocal source
            directory, name = self._parent(file, context, create=False)
            try:
                source = self._open(directory, name)
            finally:
                os.close(directory)
            return self._identify(source)

        def release() -> None:
            if source is not None:
                source.close()

        try:
            identity = await self._io(acquire)
            assert source is not None
            yield FileSource(identity, self._chunks(source))
        finally:
            await self._io(release)

    async def materialize(
        self,
        file: WorkspaceFile,
        reference: ContentIdentity,
        content: AsyncIterable[bytes],
        context: ExecutionContext,
    ) -> None:
        if reference.size_bytes > self._max_bytes:
            raise ArtifactLimitExceeded("Workspace file exceeds its byte limit")
        directory: int | None = None
        destination: BinaryIO | None = None
        temporary, name = ".artifact-" + uuid4().hex, ""

        def acquire() -> None:
            nonlocal directory, destination, name
            directory, name = self._parent(file, context, create=True)
            descriptor = os.open(
                temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory
            )
            try:
                destination = os.fdopen(descriptor, "wb")
            except BaseException:
                os.close(descriptor)
                raise

        def commit() -> None:
            assert destination is not None and directory is not None
            destination.flush()
            os.fsync(destination.fileno())
            destination.close()
            try:
                os.link(
                    temporary,
                    name,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                    follow_symlinks=False,
                )
            except FileExistsError:
                with self._open(directory, name) as existing:
                    if self._identify(existing) != ContentIdentity(
                        sha256=reference.sha256, size_bytes=reference.size_bytes
                    ):
                        raise ArtifactConflict(
                            "Workspace destination already contains different bytes"
                        ) from None
            os.fsync(directory)

        def release() -> None:
            if destination is not None:
                destination.close()
            if directory is not None:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
                finally:
                    os.close(directory)

        try:
            await self._io(acquire)
            assert destination is not None
            digest, size = hashlib.sha256(), 0
            async for chunk in content:
                size += len(chunk)
                if size > reference.size_bytes:
                    raise ArtifactIntegrityError("Materialized bytes exceed their declared size")
                digest.update(chunk)
                await self._io(partial(destination.write, chunk))
            if size != reference.size_bytes or digest.hexdigest() != reference.sha256:
                raise ArtifactIntegrityError("Materialized bytes do not match their identity")
            await self._io(commit)
        finally:
            await self._io(release)
