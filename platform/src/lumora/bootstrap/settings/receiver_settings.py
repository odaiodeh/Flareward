"""Receiver-local services and secrets; never included in invocation payloads."""

from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator

from lumora.bootstrap.settings.interaction_settings import InteractionSettings
from lumora.bootstrap.settings.tracing_settings import TracingBackend


class CredentialBackend(StrEnum):
    DISABLED = "disabled"
    MONGO = "mongo"


from lumora.bootstrap.settings.plugins import DEFAULT_PLUGINS


class ReceiverSettings(InteractionSettings):
    plugins: tuple[str, ...] = DEFAULT_PLUGINS
    element_modules: tuple[str, ...] = ()
    credentials: CredentialBackend = CredentialBackend.DISABLED
    mongo_uri: SecretStr = SecretStr("mongodb://localhost:27017")
    mongo_database: str = "Lumora"
    credentials_collection: str = "credentials"
    server_configs_collection: str = "server_configs"
    credential_encryption_key: SecretStr = SecretStr("")
    configuration_secrets: bool = False
    workflow_credential_directory: Path | None = None
    tracing: TracingBackend = TracingBackend.DISABLED
    langfuse_public_key: SecretStr = SecretStr("")
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_base_url: AnyHttpUrl = AnyHttpUrl("https://us.cloud.langfuse.com")
    tracing_timeout: float = Field(default=5, ge=0.001, le=60, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        if (
            self.workflow_credential_directory is not None
            and not self.workflow_credential_directory.is_absolute()
        ):
            raise ValueError("Managed workflow credentials require an absolute directory")
        if self.credentials == CredentialBackend.MONGO and not (
            self.credential_encryption_key.get_secret_value()
        ):
            raise ValueError("Mongo credentials require LUMORA_CREDENTIAL_ENCRYPTION_KEY")
        if self.configuration_secrets and not self.credential_encryption_key.get_secret_value():
            raise ValueError("Configuration secrets require LUMORA_CREDENTIAL_ENCRYPTION_KEY")
        if self.tracing == TracingBackend.LANGFUSE and not (
            self.langfuse_public_key.get_secret_value()
            and self.langfuse_secret_key.get_secret_value()
        ):
            raise ValueError("Langfuse tracing requires local public and secret keys")
        if (
            self.langfuse_base_url.username
            or self.langfuse_base_url.password
            or self.langfuse_base_url.query
            or self.langfuse_base_url.fragment
        ):
            raise ValueError("Langfuse URL must not contain credentials, query, or fragment")
        return self
