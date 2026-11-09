"""Pinned, execution-scoped POSIX directory traversal shared by filesystem adapters."""

import hashlib
import os
from pathlib import Path, PurePosixPath


class WorkspacePaths:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise ValueError("Workspace root must be absolute")
        self._root = root

    def parent(self, relative: str, root_execution: str, *, create: bool) -> tuple[int, str]:
        path = PurePosixPath(relative)
        parts = path.parts
        if (
            not root_execution
            or path.is_absolute()
            or len(parts) < 2
            or ".." in parts
            or "\\" in relative
            or "\0" in relative
            or parts[0] != hashlib.sha256(root_execution.encode()).hexdigest()
        ):
            raise PermissionError("Workspace does not belong to this execution")
        if create:
            self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        current = os.open(self._root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=current)
                    except FileExistsError:
                        pass
                following = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current
                )
                os.close(current)
                current = following
            return current, parts[-1]
        except BaseException:
            os.close(current)
            raise
