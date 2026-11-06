"""Owned Git subprocesses and detached checkouts in execution-scoped workspaces."""

import asyncio
import errno
import os
import shutil
import signal
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from tempfile import mkdtemp

from mas.application.repositories.operations import ResolveGitRevision
from mas.application.repositories.ports import RepositoryConflict, RepositoryError
from mas.core.async_work import await_owned
from mas.core.identity import Identity
from mas.domain.execution.context import ExecutionContext
from mas.domain.repositories import GitRevision, RepositoryId

from mas_plugins.workspaces import WorkspacePaths

from .config import GitBinding, GitSettings


class GitCLIRepository:
    def __init__(
        self,
        repository: RepositoryId,
        binding: GitBinding,
        owner: Identity,
        settings: GitSettings,
        *,
        executable: str = "git",
    ) -> None:
        if not any(identity.owns(owner) for identity in binding.owners):
            raise PermissionError("Repository access is not permitted")
        self._repository, self._binding = repository, binding.model_copy(deep=True)
        self._owner, self._settings = owner.model_copy(deep=True), settings.model_copy(deep=True)
        self._executable = executable
        self._paths = WorkspacePaths(settings.workspace_root)

    async def resolve(self, reference: str) -> GitRevision:
        request = ResolveGitRevision(reference=reference)
        async with self._temporary() as directory:
            commit = await self._fetch(directory, request.reference)
            return GitRevision(repository=self._repository, commit=commit)

    async def checkout(
        self, revision: GitRevision, workspace: str, context: ExecutionContext
    ) -> None:
        if not self._owner.owns(context.identity):
            raise PermissionError("Repository access is not permitted")
        if revision.repository != self._repository:
            raise ValueError("Candidate belongs to a different repository")
        async with self._temporary() as directory:
            commit = await self._fetch(directory, revision.commit)
            if commit != revision.commit:
                raise RepositoryError("Fetched source does not match the requested commit")
            await self._run(directory, "checkout", "--quiet", "--detach", commit, "--")
            await self._io(partial(self._install, directory, workspace, context))

    async def _fetch(self, directory: Path, reference: str) -> str:
        if len(reference) in (40, 64) and all(
            character in "0123456789abcdef" for character in reference
        ):
            size = 40 if self._binding.object_format == "sha1" else 64
            if len(reference) != size:
                raise ValueError("Commit ID does not match the repository object format")
        await self._run(
            directory, "init", "--quiet", "--object-format=" + self._binding.object_format.value
        )
        await self._run(
            directory,
            "fetch",
            "--quiet",
            "--no-tags",
            "--no-recurse-submodules",
            "--no-write-fetch-head",
            "--no-auto-maintenance",
            "--depth=1",
            "--",
            self._binding.location,
            reference + ":refs/unifai/source",
        )
        result = await self._run(directory, "rev-parse", "--verify", "refs/unifai/source^{commit}")
        try:
            return GitRevision(repository=self._repository, commit=result.decode().strip()).commit
        except ValueError, UnicodeError:
            raise RepositoryError("Repository returned an invalid commit identity") from None

    def _install(self, directory: Path, workspace: str, context: ExecutionContext) -> None:
        parent, name = self._paths.parent(workspace, context.root_execution_id, create=True)
        reserved = False
        try:
            try:
                # Claim an absent destination before publication. Never replace existing work.
                os.mkdir(name, mode=0o700, dir_fd=parent)
            except FileExistsError:
                raise RepositoryConflict("Checkout destination already exists") from None
            reserved = True
            os.rename(directory, name, dst_dir_fd=parent)
            reserved = False
            os.fsync(parent)
        finally:
            if reserved:
                os.rmdir(name, dir_fd=parent)
            os.close(parent)

    @asynccontextmanager
    async def _temporary(self) -> AsyncIterator[Path]:
        temporary: Path | None = None

        def acquire() -> None:
            nonlocal temporary
            root = self._settings.workspace_root
            root.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            os.close(descriptor)
            temporary = Path(mkdtemp(prefix=".git-stage-", dir=root))
            (temporary / "checkout").mkdir(mode=0o700)
            (temporary / "home").mkdir(mode=0o700)

        def release() -> None:
            if temporary is not None:
                shutil.rmtree(temporary)

        try:
            await self._io(acquire)
            assert temporary is not None
            async with asyncio.timeout(self._settings.timeout_seconds):
                yield temporary / "checkout"
        except TimeoutError:
            raise RepositoryError("Repository operation exceeded its time limit") from None
        finally:
            await self._io(release)

    @staticmethod
    async def _io[T](operation: Callable[[], T]) -> T:
        try:
            return await await_owned(asyncio.to_thread(operation))
        except OSError as error:
            if isinstance(error, PermissionError) and error.errno is None:
                raise PermissionError("Workspace access is not permitted") from None
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise PermissionError("Workspace paths must not contain symbolic links") from None
            raise RepositoryError("Repository workspace is unavailable") from None

    async def _run(self, directory: Path, *arguments: str) -> bytes:
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in {"PATH", "LANG", "SSL_CERT_FILE", "SSL_CERT_DIR"}
        }
        environment.update(
            HOME=str(directory.parent / "home"),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
            GIT_NO_REPLACE_OBJECTS="1",
        )
        configuration = (
            "core.hooksPath=" + os.devnull,
            "init.templateDir=" + str(directory.parent / "home"),
            "core.attributesFile=" + os.devnull,
            "core.fsmonitor=false",
            "core.logAllRefUpdates=false",
            "credential.helper=",
            "protocol.allow=never",
            "protocol.file.allow="
            + ("always" if Path(self._binding.location).is_absolute() else "never"),
            "protocol.https.allow=always",
            "http.followRedirects=false",
            "http.sslVerify=true",
            "fetch.fsckObjects=true",
        )
        command = [self._executable]
        for setting in configuration:
            command.extend(("-c", setting))
        process: asyncio.subprocess.Process | None = None

        async def acquire() -> None:
            nonlocal process
            process = await asyncio.create_subprocess_exec(
                *command,
                *arguments,
                cwd=directory,
                env=environment,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )

        try:
            await await_owned(acquire())
            assert process is not None and process.stdout is not None and process.stderr is not None
            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(self._drain(process.stderr))
                output = await self._output(process.stdout)
                code = await process.wait()
            if code != 0:
                raise RepositoryError("Git could not complete the repository operation")
            return output
        except OSError, ExceptionGroup:
            raise RepositoryError("Git could not complete the repository operation") from None
        finally:
            if process is not None:
                await await_owned(self._stop(process))

    @staticmethod
    async def _output(stream: asyncio.StreamReader) -> bytes:
        result = bytearray()
        while chunk := await stream.read(8192):
            result.extend(chunk)
            if len(result) > 65_536:
                raise RepositoryError("Git exceeded its response limit")
        return bytes(result)

    @staticmethod
    async def _drain(stream: asyncio.StreamReader) -> None:
        while await stream.read(8192):
            pass

    @staticmethod
    async def _stop(process: asyncio.subprocess.Process) -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
