"""Private per-root file delivery, with durable slot fencing and bounded reads."""

import asyncio
import fcntl
import hashlib
import hmac
import json
import os
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from lumora.async_work import await_owned
from lumora.services.access.issuance import (
    CredentialIssuanceClosed,
    CredentialMaterial,
    CredentialMaterialUnavailable,
    CredentialReservation,
    digest,
)
from lumora.services.identity.domain import Identity

_LIMIT = 131_072
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class _PrivateFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    reservation: CredentialReservation
    credential: SecretStr


class FileWorkflowCredentials:
    def __init__(self, directory: Path) -> None:
        if not directory.is_absolute():
            raise ValueError("Managed workflow credentials require an absolute directory")
        self._directory = Path(os.path.normpath(directory))
        self._key = "workflow-files@1:" + hashlib.sha256(os.fsencode(self._directory)).hexdigest()

    @property
    def key(self) -> str:
        return self._key

    @staticmethod
    def _private(descriptor: int, *, directory: bool = False) -> None:
        entry = os.fstat(descriptor)
        kind = stat.S_ISDIR(entry.st_mode) if directory else stat.S_ISREG(entry.st_mode)
        if not kind or entry.st_uid != os.geteuid() or entry.st_mode & 0o077:
            raise CredentialMaterialUnavailable()

    @contextmanager
    def _root(self, owner: Identity, root: str, *, create: bool) -> Iterator[int]:
        if not owner.id or not root:
            raise CredentialMaterialUnavailable()
        if create:
            self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        base = os.open(self._directory, _DIRECTORY_FLAGS)
        try:
            self._private(base, directory=True)
            name = digest([owner.type.value, owner.id, root])
            if create:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=base)
                except FileExistsError:
                    pass
            descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=base)
            try:
                self._private(descriptor, directory=True)
                yield descriptor
            finally:
                os.close(descriptor)
        finally:
            os.close(base)

    @staticmethod
    def _name(reservation: CredentialReservation) -> str:
        return digest(reservation.purpose) + "." + reservation.binding_id + ".json"

    @classmethod
    def _read(cls, parent: int, name: str) -> bytes:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as source:
            cls._private(source.fileno())
            data = source.read(_LIMIT + 1)
        if len(data) > _LIMIT:
            raise CredentialMaterialUnavailable()
        return data

    @classmethod
    @contextmanager
    def _locked(cls, parent: int, name: str) -> Iterator[int]:
        descriptor = os.open(
            "." + name + ".lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=parent,
        )
        try:
            cls._private(descriptor)
            deadline = time.monotonic() + 5
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise CredentialMaterialUnavailable() from None
                    time.sleep(0.01)
            yield descriptor
        finally:
            os.close(descriptor)

    @staticmethod
    def _mark(descriptor: int, value: bytes) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.write(descriptor, value) != 1:
            raise CredentialMaterialUnavailable()
        os.ftruncate(descriptor, 1)
        os.fsync(descriptor)

    def _deliver(self, material: CredentialMaterial) -> None:
        reservation = material.reservation
        if reservation.delivery_key != self.key:
            raise CredentialMaterialUnavailable()
        data = json.dumps(
            {
                "reservation": reservation.model_dump(mode="json"),
                "credential": material.credential.get_secret_value(),
            },
            separators=(",", ":"),
        ).encode()
        if len(data) > _LIMIT:
            raise CredentialMaterialUnavailable()
        name = self._name(reservation)
        with self._root(reservation.owner, reservation.root_execution_id, create=True) as parent:
            with self._locked(parent, name) as marker:
                state = os.read(marker, 256)
                active = b"A"
                if state == b"R":
                    raise CredentialIssuanceClosed()
                if state and state != active:
                    raise CredentialMaterialUnavailable()
                try:
                    existing = _PrivateFile.model_validate_json(self._read(parent, name))
                except FileNotFoundError:
                    existing = None
                if existing is not None and (
                    existing.reservation != reservation
                    or not hmac.compare_digest(
                        existing.credential.get_secret_value(),
                        material.credential.get_secret_value(),
                    )
                ):
                    raise CredentialMaterialUnavailable()
                self._mark(marker, active)
                if existing is not None:
                    return
                staging = "." + name + "." + uuid4().hex + ".tmp"
                try:
                    descriptor = os.open(
                        staging,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=parent,
                    )
                    with os.fdopen(descriptor, "wb") as output:
                        output.write(data)
                        output.flush()
                        os.fsync(output.fileno())
                    os.replace(staging, name, src_dir_fd=parent, dst_dir_fd=parent)
                    os.fsync(parent)
                finally:
                    try:
                        os.unlink(staging, dir_fd=parent)
                    except FileNotFoundError:
                        pass

    async def deliver(self, material: CredentialMaterial) -> None:
        try:
            await await_owned(asyncio.to_thread(self._deliver, material))
        except CredentialIssuanceClosed:
            raise
        except OSError, ValueError:
            raise CredentialMaterialUnavailable() from None

    def _retire(self, reservation: CredentialReservation) -> None:
        if reservation.delivery_key != self.key:
            raise CredentialMaterialUnavailable()
        name = self._name(reservation)
        with self._root(reservation.owner, reservation.root_execution_id, create=True) as parent:
            with self._locked(parent, name) as marker:
                state = os.read(marker, 256)
                allowed = (b"", b"A", b"R")
                if state not in allowed:
                    raise CredentialMaterialUnavailable()
                try:
                    existing = _PrivateFile.model_validate_json(self._read(parent, name))
                except FileNotFoundError:
                    existing = None
                if existing is not None and existing.reservation != reservation:
                    raise CredentialMaterialUnavailable()
                self._mark(marker, b"R")
                if existing is not None:
                    os.unlink(name, dir_fd=parent)
                with os.scandir(parent) as entries:
                    for index, entry in enumerate(entries):
                        if index >= 512:
                            raise CredentialMaterialUnavailable()
                        if entry.name.startswith("." + name + ".") and entry.name.endswith(".tmp"):
                            data = entry.stat(follow_symlinks=False)
                            if not stat.S_ISREG(data.st_mode) or data.st_uid != os.geteuid():
                                raise CredentialMaterialUnavailable()
                            os.unlink(entry.name, dir_fd=parent)
                os.fsync(parent)

    async def retire(self, reservation: CredentialReservation) -> None:
        try:
            await await_owned(asyncio.to_thread(self._retire, reservation))
        except OSError, ValueError:
            raise CredentialMaterialUnavailable() from None

    def _resolve(self, purpose: str, owner: Identity, root: str) -> SecretStr:
        prefix = digest(purpose) + "."
        found: SecretStr | None = None
        with self._root(owner, root, create=False) as parent:
            with os.scandir(parent) as entries:
                for index, entry in enumerate(entries):
                    if index >= 512:
                        raise CredentialMaterialUnavailable()
                    if not (entry.name.startswith(prefix) and entry.name.endswith(".json")):
                        continue
                    document = _PrivateFile.model_validate_json(self._read(parent, entry.name))
                    row = document.reservation
                    if (
                        row.purpose != purpose
                        or not row.owner.owns(owner)
                        or row.root_execution_id != root
                        or row.delivery_key is None
                        or self._name(row) != entry.name
                    ):
                        raise CredentialMaterialUnavailable()
                    if row.maximum_expiry <= datetime.now(UTC):
                        continue
                    marker = self._read(parent, "." + entry.name + ".lock")
                    if marker != b"A":
                        raise CredentialMaterialUnavailable()
                    if found is not None:
                        raise CredentialMaterialUnavailable()
                    found = document.credential
        if found is None:
            raise CredentialMaterialUnavailable()
        return found

    async def resolve(self, purpose: str, owner: Identity, root_execution_id: str) -> SecretStr:
        try:
            return await await_owned(
                asyncio.to_thread(self._resolve, purpose, owner, root_execution_id)
            )
        except OSError, ValueError, ValidationError:
            raise CredentialMaterialUnavailable() from None
