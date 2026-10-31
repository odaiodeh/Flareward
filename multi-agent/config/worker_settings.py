"""Durable worker settings share receiver configuration without HTTP authentication settings."""

from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from runengine.adapters.coordination.config import TemporalHostConfig

from config.receiver_settings import ReceiverSettings


class WorkerSettings(ReceiverSettings):
    host: TemporalHostConfig = Field(
        default_factory=lambda: TemporalHostConfig(task_queue="unifai-programs-v2")
    )
    application_modules: tuple[str, ...] = ()
    receiver_module: str = ""
    environment_sqlite: Path | None = None
    environment_postgres: SecretStr | None = None
    environment_reconciliation_interval: float = Field(default=5, gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_journal(self) -> Self:
        if self.environment_sqlite is not None and self.environment_postgres is not None:
            raise ValueError("Choose one Run Engine environment journal")
        return self
