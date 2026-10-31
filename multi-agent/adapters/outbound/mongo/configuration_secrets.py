"""Immutable, owner-scoped encrypted values behind opaque configuration references."""

import asyncio
from uuid import uuid4

from mas.core.async_work import await_owned
from mas.core.auth.credentials.ports import CipherError, TokenCipher
from mas.core.identity import Identity
from mas.core.secrets import SECRET_PREFIX, reference_id
from mas.execution.models import ExecutionFailure, FailureKind
from mas.execution.ports import ExecutionError
from pydantic import SecretStr
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError


class MongoConfigurationSecrets:
    def __init__(self, database: AsyncDatabase, cipher: TokenCipher) -> None:
        self._collection, self._cipher = database.program_configuration_secrets, cipher

    async def put(self, owner: Identity, value: SecretStr) -> str:
        identifier = uuid4().hex
        encrypted = await await_owned(
            asyncio.to_thread(self._cipher.encrypt, value.get_secret_value())
        )
        try:
            await self._collection.insert_one(
                {
                    "_id": identifier,
                    "owner": {"type": owner.type.value, "id": owner.id},
                    "value": encrypted,
                }
            )
        except PyMongoError:
            raise unavailable() from None
        return SECRET_PREFIX + identifier

    async def get(self, owner: Identity, reference: str) -> SecretStr:
        try:
            document = await self._collection.find_one(
                {
                    "_id": reference_id(reference),
                    "owner": {"type": owner.type.value, "id": owner.id},
                }
            )
        except PyMongoError:
            raise unavailable() from None
        if document is None:
            raise PermissionError("Configuration secret is unavailable to this owner")
        try:
            value = await await_owned(asyncio.to_thread(self._cipher.decrypt, document["value"]))
        except CipherError:
            raise unavailable() from None
        return SecretStr(value)


def unavailable() -> ExecutionError:
    return ExecutionError(
        ExecutionFailure(
            kind=FailureKind.INFRASTRUCTURE,
            code="configuration_secrets_unavailable",
            message="Configuration secret storage is unavailable",
            retryable=False,
        )
    )
