"""Private SQLite persistence keeps grant revocation and ownership across API restarts."""

import asyncio
import os
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from pydantic import ValidationError

from lumora.async_work import await_owned
from lumora.services.artifacts.access_models import StoredArtifactAccess
from lumora.services.artifacts.ports import ArtifactStorageError
from lumora.services.identity.domain import Identity


class SQLiteArtifactAccessRepository:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise ValueError("Artifact access storage requires an absolute directory")
        self._root, self._path = root, root / "access.sqlite"

    async def _run[T](self, operation: Callable[[sqlite3.Connection], T]) -> T:
        def execute() -> T:
            with closing(sqlite3.connect(self._path, timeout=5)) as connection, connection:
                return operation(connection)

        try:
            return await await_owned(asyncio.to_thread(execute))
        except OSError, sqlite3.Error:
            raise ArtifactStorageError("Artifact access storage is unavailable") from None

    async def initialize(self) -> None:
        def prepare() -> None:
            self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self._path.is_symlink():
                raise ArtifactStorageError("Artifact access storage entry is invalid")
            try:
                descriptor = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(descriptor)

        try:
            await await_owned(asyncio.to_thread(prepare))
        except OSError:
            raise ArtifactStorageError("Artifact access storage is unavailable") from None
        await self._run(
            lambda connection: connection.executescript(
                "CREATE TABLE IF NOT EXISTS grants ("
                "id TEXT PRIMARY KEY, owner_type TEXT NOT NULL, owner_id TEXT NOT NULL, "
                "data TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);"
                "CREATE INDEX IF NOT EXISTS grants_owner ON grants(owner_type, owner_id, id);"
            )
        )

    async def create(self, access: StoredArtifactAccess) -> None:
        await self._run(
            lambda connection: connection.execute(
                "INSERT INTO grants(id, owner_type, owner_id, data) VALUES (?, ?, ?, ?)",
                (
                    access.grant.grant_id,
                    access.grant.owner.type.value,
                    access.grant.owner.id,
                    access.model_dump_json(),
                ),
            )
        )

    @staticmethod
    def _decode(row: tuple[str, int]) -> StoredArtifactAccess:
        try:
            stored = StoredArtifactAccess.model_validate_json(row[0])
        except ValidationError:
            raise ArtifactStorageError("Artifact access record is invalid") from None
        return stored.model_copy(
            update={"grant": stored.grant.model_copy(update={"revoked": bool(row[1])})}
        )

    async def get(self, grant_id: str) -> StoredArtifactAccess | None:
        row = await self._run(
            lambda connection: connection.execute(
                "SELECT data, revoked FROM grants WHERE id = ?", (grant_id,)
            ).fetchone()
        )
        return self._decode(row) if row else None

    async def list(self, owner: Identity, *, after: str, limit: int) -> list[StoredArtifactAccess]:
        rows = await self._run(
            lambda connection: connection.execute(
                "SELECT data, revoked FROM grants "
                "WHERE owner_type = ? AND owner_id = ? AND id > ? ORDER BY id LIMIT ?",
                (owner.type.value, owner.id, after, limit),
            ).fetchall()
        )
        return [self._decode(row) for row in rows]

    async def revoke(self, grant_id: str) -> None:
        await self._run(
            lambda connection: connection.execute(
                "UPDATE grants SET revoked = 1 WHERE id = ?", (grant_id,)
            )
        )
