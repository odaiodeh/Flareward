"""Explicit server settings; secrets never enter portable program definitions."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict
from runengine.adapters.coordination.config import LocalHostConfig, TemporalHostConfig
from runengine.invocation.config import (
    CeleryRunnerConfig,
    K8sRunnerConfig,
    OpenShellRunnerConfig,
    ProcessRunnerConfig,
    ThreadRunnerConfig,
)

from config.receiver_settings import ReceiverSettings


class StorageKind(StrEnum):
    MONGO = "mongo"
    MEMORY = "memory"


class AuthenticationKind(StrEnum):
    SESSION = "session"
    DEVELOPMENT = "development"


type HostSettings = Annotated[
    LocalHostConfig | TemporalHostConfig, Field(discriminator="runner_type")
]
type RunnerSettings = Annotated[
    ThreadRunnerConfig
    | ProcessRunnerConfig
    | CeleryRunnerConfig
    | K8sRunnerConfig
    | OpenShellRunnerConfig,
    Field(discriminator="runner_type"),
]


def _default_profiles() -> dict[str, RunnerSettings]:
    return {"trusted-worker": ThreadRunnerConfig()}


class PlatformSettings(ReceiverSettings):
    model_config = SettingsConfigDict(env_prefix="UNIFAI_", extra="ignore", populate_by_name=True)
    host: HostSettings = Field(
        default_factory=lambda: TemporalHostConfig(task_queue="unifai-programs-v2")
    )
    storage: StorageKind = StorageKind.MONGO
    authentication: AuthenticationKind = AuthenticationKind.SESSION
    secret_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("UNIFAI_SECRET_KEY", "SECRET_KEY"),
    )
    identity_url: str = "http://localhost:13456"
    internal_auth_token: SecretStr = SecretStr("")
    development_user: str = ""
    execution_profiles: dict[str, RunnerSettings] = Field(default_factory=_default_profiles)
    execution_policy_files: dict[str, Path] = Field(default_factory=dict)
    default_execution_profile: str = "trusted-worker"
    application_modules: tuple[str, ...] = ()
    receiver_module: str = ""
    reconcile_interval: float = Field(default=2, ge=0.05)
    http_timeout: float = Field(default=10, gt=0)
    frontend_url: str = "http://localhost:5000"
    library: bool = False
    edit_locks: bool = False
    edit_lock_ttl: int = Field(default=180, ge=1, le=3600)
    blueprints_collection: str = "blueprints"
    resources_collection: str = "resources"
    shares_collection: str = "shares"
    builtin_descriptors_collection: str = "builtin_resource_descriptors"
    builtin_user_configs_collection: str = "builtin_user_configs"
    admin_config_database: str = "config"
    admin_config_collection: str = "admin_config"
    rag_base_url: AnyHttpUrl = AnyHttpUrl("http://unifai-rag-server:13456")

    @model_validator(mode="after")
    def validate_deployment(self) -> Self:
        if self.edit_locks and not self.library:
            raise ValueError("Team editing leases require library services")
        for name, path in self.execution_policy_files.items():
            profile = self.execution_profiles.get(name)
            if not isinstance(profile, OpenShellRunnerConfig):
                raise ValueError("Execution policy files require a configured OpenShell profile")
            if profile.sandbox_id:
                raise ValueError("A pre-existing sandbox retains its policy; omit the policy file")
            if profile.policy is not None:
                raise ValueError("Choose either an inline execution policy or a policy file")
            if not path.is_absolute():
                raise ValueError("Execution policy files require absolute paths")
        private_names = set()
        for name, field in type(self).model_fields.items():
            if field.annotation is not SecretStr:
                continue
            private_names.add("UNIFAI_" + name.upper())
            aliases = (
                field.validation_alias.choices
                if isinstance(field.validation_alias, AliasChoices)
                else [field.validation_alias]
            )
            private_names.update(alias.upper() for alias in aliases if isinstance(alias, str))
        if any(
            name.upper() in private_names
            for profile in self.execution_profiles.values()
            for name in (getattr(profile, "env", None) or {})
        ):
            raise ValueError("Execution profile environment must use receiver-local secrets")
        if self.default_execution_profile not in self.execution_profiles:
            raise ValueError("Default execution profile is not configured")
        if self.authentication == AuthenticationKind.DEVELOPMENT and not self.development_user:
            raise ValueError("Development authentication requires UNIFAI_DEVELOPMENT_USER")
        if (
            self.authentication == AuthenticationKind.SESSION
            and not self.secret_key.get_secret_value()
        ):
            raise ValueError("Session authentication requires SECRET_KEY or UNIFAI_SECRET_KEY")
        if self.storage == StorageKind.MEMORY and isinstance(self.host, TemporalHostConfig):
            raise ValueError("Durable coordination requires durable application records")
        return self
