"""Own a receiver's credential stores and reuse UnifAI's auth application service."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mas.core.async_work import await_owned
from mas.core.auth.service import AuthService, AuthStrategyRegistry
from outbound.auth.api_key_strategy import ApiKeyStrategy
from outbound.auth.oauth2_strategy import OAuth2Strategy
from outbound.crypto import FieldCipher
from outbound.mongo.auth_token_repository import MongoCredentialStore
from outbound.mongo.client_config_repository import MongoServerConfigStore
from pymongo import MongoClient

from config.receiver_settings import ReceiverSettings


@asynccontextmanager
async def receiver_auth(settings: ReceiverSettings) -> AsyncIterator[AuthService]:
    client: MongoClient | None = None
    try:

        def construct() -> AuthService:
            nonlocal client
            client = MongoClient(
                settings.mongo_uri.get_secret_value(),
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                timeoutMS=10000,
            )
            database = client[settings.mongo_database]
            encryption_key = settings.credential_encryption_key.get_secret_value()
            credentials = MongoCredentialStore(
                collection=database[settings.credentials_collection],
                encryption_key=encryption_key,
            )
            configs = MongoServerConfigStore(
                collection=database[settings.server_configs_collection]
            )
            strategies = AuthStrategyRegistry()
            strategies.register(ApiKeyStrategy())
            strategies.register(OAuth2Strategy())
            return AuthService(
                credentials,
                strategies,
                configs,
                cipher=FieldCipher(encryption_key) if encryption_key else None,
            )

        yield await await_owned(asyncio.to_thread(construct))
    finally:
        if client is not None:
            await await_owned(asyncio.to_thread(client.close))
