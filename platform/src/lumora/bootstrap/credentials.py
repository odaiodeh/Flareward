"""Own a receiver's credential stores and reuse Lumora's auth application service."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pymongo import MongoClient

from lumora.async_work import await_owned
from lumora.bootstrap.settings.receiver_settings import ReceiverSettings
from lumora.services.auth.adapters.api_key_strategy import ApiKeyStrategy
from lumora.services.auth.adapters.crypto import FieldCipher
from lumora.services.auth.adapters.mongo.auth_token_repository import MongoCredentialStore
from lumora.services.auth.adapters.mongo.client_config_repository import MongoServerConfigStore
from lumora.services.auth.adapters.oauth2_strategy import OAuth2Strategy
from lumora.services.auth.service import AuthService, AuthStrategyRegistry


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
