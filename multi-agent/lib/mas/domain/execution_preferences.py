"""Portable placement preferences, separate from construction and runner SDKs."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mas.core.enums import ResourceCategory


class ResourceExecutionDefaults(BaseModel):
    """A reusable invocation preference; named environments belong to the caller."""

    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")
    profile: str | None = Field(default=None, min_length=1)

    def validate_category(self, category: ResourceCategory) -> None:
        if self.profile is not None and not category.is_plan_category():
            raise ValueError("Execution preferences apply only to nodes, operations and conditions")


class ExecutionSelection(BaseModel):
    """Caller-owned placement for one invocation, independent of runner SDKs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    profile: str | None = Field(default=None, min_length=1)
    environment: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def exclusive_selection(self) -> Self:
        if self.profile is not None and self.environment is not None:
            raise ValueError("Select an execution profile or an environment, not both")
        return self


class ExecutionProfileCatalog(BaseModel):
    """Public deployment-approved names; contains no backend configuration or secrets."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    profiles: tuple[str, ...]
    default_profile: str
    environment_profiles: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_default(self) -> Self:
        if self.default_profile not in self.profiles:
            raise ValueError("Default execution profile must be available")
        if not set(self.environment_profiles) <= set(self.profiles):
            raise ValueError("Environment profiles must be approved execution profiles")
        if any(not name for name in self.profiles) or len(set(self.profiles)) != len(self.profiles):
            raise ValueError("Execution profile names must be nonempty and unique")
        return self
