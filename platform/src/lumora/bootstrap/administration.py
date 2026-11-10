"""Compose retained administrator/model settings without a separate admin application."""

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from lumora.services.administration.contracts import SettingsSection


class Administrators(BaseModel):
    model_config = ConfigDict(extra="forbid")
    admin_usernames: tuple[str, ...] = Field(max_length=10_000, title="Admin usernames")


class ModelCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capabilities: dict[str, dict[str, JsonValue]] = Field(title="Model capabilities")


def settings_sections(users: tuple[str, ...]) -> tuple[SettingsSection, ...]:
    return (
        SettingsSection(
            "admin_users",
            "administrators",
            "Administrators",
            Administrators,
            {"admin_usernames": list(users)},
        ),
        SettingsSection(
            "openai_model_capabilities",
            "model_capabilities",
            "Model capabilities",
            ModelCapabilities,
            {"capabilities": {}},
        ),
    )
