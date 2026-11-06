"""Explicit server settings; secrets never enter portable program definitions."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Self

from mas.application.verification.program_checks import ProgramCheckConfiguration
from mas.core.identity import Identity
from mas.domain.execution.budgets import WorkLimits
from mas.domain.execution.profile_access import ProfileAccessPolicy
from mas.domain.verification import VerifierId
from mas_plugins.ci.github_config import GitHubCheckConfiguration
from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)
from pydantic_settings import SettingsConfigDict
from runengine.adapters.coordination.config import LocalHostConfig, TemporalHostConfig
from runengine.invocation.config import (
    CeleryRunnerConfig,
    K8sRunnerConfig,
    OpenShellRunnerConfig,
    ProcessRunnerConfig,
    ThreadRunnerConfig,
)

from config.workflow_access_settings import WorkflowAccessSettings


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


class VerificationAuthorityConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    credential_sha256: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)
    owners: tuple[Identity, ...] = Field(min_length=1, max_length=128)


class PlatformSettings(WorkflowAccessSettings):
    model_config = SettingsConfigDict(
        env_prefix="UNIFAI_", extra="ignore", populate_by_name=True, hide_input_in_errors=True
    )
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
    profile_access: ProfileAccessPolicy | None = None
    application_modules: tuple[str, ...] = ()
    receiver_module: str = ""
    reconcile_interval: float = Field(default=2, ge=0.05)
    submission_timeout_seconds: float = Field(default=30, ge=0.1, le=300, allow_inf_nan=False)
    work_limits: WorkLimits | None = None
    event_sources_enabled: bool = False
    http_timeout: float = Field(default=10, gt=0)
    frontend_url: str = "http://localhost:5000"
    library: bool = False
    artifact_directory: Path | None = None
    verification_authorities: dict[VerifierId, VerificationAuthorityConfig] = Field(
        default_factory=dict, max_length=32
    )
    github_checks: dict[str, GitHubCheckConfiguration] = Field(default_factory=dict, max_length=32)
    program_checks: dict[str, ProgramCheckConfiguration] = Field(
        default_factory=dict, max_length=32
    )
    edit_locks: bool = False
    edit_lock_ttl: int = Field(default=180, ge=1, le=3600)
    blueprints_collection: str = "blueprints"
    resources_collection: str = "resources"
    shares_collection: str = "shares"
    builtin_descriptors_collection: str = "builtin_resource_descriptors"
    builtin_user_configs_collection: str = "builtin_user_configs"
    admin_config_database: str = "config"
    admin_config_collection: str = "admin_config"
    admin_allowed_users: tuple[str, ...] = Field(default=(), max_length=128)
    rag_base_url: AnyHttpUrl = AnyHttpUrl("http://unifai-rag-server:13456")

    @model_validator(mode="after")
    def validate_deployment(self) -> Self:
        if self.artifact_workflow_enabled and (
            self.artifact_directory is None or not self.recoverable_credential_issuance
        ):
            raise ValueError(
                "Managed artifact access requires artifact storage and recoverable issuance"
            )
        if self.event_sources_enabled and self.storage != StorageKind.MONGO:
            raise ValueError("Program event sources require durable Mongo storage")
        if (
            self.workflow_credential_directory is not None
            and not self.recoverable_credential_issuance
        ):
            raise ValueError("Managed delivery requires recoverable credential issuance")
        if self.recoverable_credential_issuance:
            if self.storage != StorageKind.MONGO or not (
                self.reviews_enabled or self.verification_enabled or self.artifact_workflow_enabled
            ):
                raise ValueError(
                    "Recoverable credential issuance requires Mongo workflow access services"
                )
            self.validate_workflow_key()
        if self.work_limits is not None and self.storage != StorageKind.MONGO:
            raise ValueError("Execution-tree work limits require durable Mongo storage")
        if self.review_policies and not self.reviews_enabled:
            raise ValueError("Review policies require Human Review services")
        if self.reviews_enabled and self.storage != StorageKind.MONGO:
            raise ValueError("Human Review requires durable Mongo records")
        if not self.verification_enabled:
            if (
                self.verification_policies
                or self.verification_authorities
                or self.github_checks
                or self.program_checks
            ):
                raise ValueError("Verification policies/authorities require verification services")
        elif self.storage != StorageKind.MONGO:
            raise ValueError("Verification requires durable Mongo application records")
        if self.github_checks.keys() & self.program_checks.keys():
            raise ValueError("Check runner names must be unique across installed adapters")
        bindings = [
            (binding.policy, bool(binding.report_names)) for binding in self.github_checks.values()
        ] + [(binding.policy, True) for binding in self.program_checks.values()]
        internal_verifiers = {policy.verifier for policy, _ in bindings}
        if internal_verifiers & self.verification_authorities.keys():
            raise ValueError(
                "A check verifier must use either internal dispatch or external credentials"
            )
        if any(
            not check.verifiers.issubset(self.verification_authorities.keys() | internal_verifiers)
            for policy in self.verification_policies.values()
            for check in policy.requirements
        ):
            raise ValueError("Verification policy requires configured verifier authorities")
        for runner_policy, has_reports in bindings:
            if has_reports and self.artifact_directory is None:
                raise ValueError("Configured check reports require durable artifact storage")
            for name in runner_policy.policies:
                policy = self.verification_policies.get(name)
                requirement = (
                    next(
                        (item for item in policy.requirements if item.check == runner_policy.check),
                        None,
                    )
                    if policy is not None
                    else None
                )
                if (
                    policy is None
                    or requirement is None
                    or runner_policy.verifier not in requirement.verifiers
                    or policy.subject_kind != runner_policy.subject_kind
                ):
                    raise ValueError("Check runner requires a compatible verification policy")
                if requirement.requires_reports and not has_reports:
                    raise ValueError("Check runner must supply the policy's required reports")
        if self.artifact_directory is not None and not self.artifact_directory.is_absolute():
            raise ValueError("Artifact storage requires an absolute directory")
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
        private_names = {"UNIFAI_GITHUB_CHECKS", "UNIFAI_PROGRAM_CHECKS"}
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
