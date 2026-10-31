"""Receiver and API transport settings, resolved locally rather than serialized in programs."""

from enum import StrEnum
from os import environ
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
    SettingsError,
)


class InteractionBackend(StrEnum):
    REDIS = "redis"
    DISABLED = "disabled"


class InteractionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UNIFAI_", extra="ignore", populate_by_name=True, hide_input_in_errors=True
    )
    interactions: InteractionBackend = InteractionBackend.REDIS
    redis_uri: SecretStr = SecretStr("redis://localhost:6379/0")
    interaction_ttl: int = Field(default=86400, ge=300)
    max_stream_events: int = Field(default=10000, ge=100)
    stream_buffer_capacity: int = Field(default=256, ge=1)
    approval_timeout: float = Field(default=300, gt=0)
    shared_storage: str = "/app/shared"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        directory = environ.get("UNIFAI_SECRETS_DIR")
        explicit = (
            isinstance(file_secret_settings, SecretsSettingsSource)
            and file_secret_settings.secrets_dir is not None
        )
        if directory is not None and not explicit:
            path = Path(directory).expanduser()
            if not path.is_absolute() or not path.is_dir():
                raise SettingsError("UNIFAI_SECRETS_DIR must be an existing absolute directory")
            file_secret_settings = SecretsSettingsSource(settings_cls, secrets_dir=path)
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    @model_validator(mode="after")
    def validate_retention(self) -> Self:
        if self.interaction_ttl <= self.approval_timeout:
            raise ValueError("Interaction retention must exceed the approval timeout")
        return self
