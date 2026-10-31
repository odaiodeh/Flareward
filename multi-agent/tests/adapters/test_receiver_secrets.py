"""Receiver-local Pydantic secret files never become execution configuration."""

import pytest
from inbound.run_engine.settings import load_receiver_settings
from pydantic import ValidationError
from pydantic_settings import SettingsError
from runengine.invocation.config import K8sRunnerConfig
from runengine.invocation.errors import InvocationInfrastructureError

from config.interaction_settings import InteractionSettings
from config.platform_settings import PlatformSettings
from config.receiver_settings import ReceiverSettings
from config.worker_settings import WorkerSettings


@pytest.mark.parametrize("settings_class", [ReceiverSettings, WorkerSettings, PlatformSettings])
def test_native_credential_storage_refuses_unencrypted_configuration(settings_class):
    with pytest.raises(ValidationError, match="Mongo credentials require"):
        settings_class(
            secret_key="server-private", credentials="mongo", credential_encryption_key=""
        )


@pytest.fixture
def mounted_secrets(tmp_path, monkeypatch):
    directory = tmp_path / "receiver-secrets"
    directory.mkdir(mode=0o700)
    values = {
        "UNIFAI_TRACING": "langfuse",
        "UNIFAI_LANGFUSE_PUBLIC_KEY": "file-public",
        "UNIFAI_LANGFUSE_SECRET_KEY": "file-private",
        "UNIFAI_CREDENTIAL_ENCRYPTION_KEY": "file-encryption",
        "UNIFAI_INTERACTIONS": "disabled",
    }
    for name, value in values.items():
        path = directory / name
        path.write_text(value)
        path.chmod(0o600)
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNIFAI_SECRETS_DIR", str(directory))
    return directory


@pytest.mark.parametrize("settings_class", [ReceiverSettings, WorkerSettings, PlatformSettings])
def test_receiver_worker_and_server_share_the_existing_file_secret_source(
    mounted_secrets, settings_class
):
    settings = settings_class(secret_key="server-private")
    assert settings.langfuse_public_key.get_secret_value() == "file-public"
    assert settings.langfuse_secret_key.get_secret_value() == "file-private"
    assert settings.credential_encryption_key.get_secret_value() == "file-encryption"
    assert settings.tracing == "langfuse" and settings.interactions == "disabled"
    assert "file-private" not in settings.model_dump_json()
    assert "file-encryption" not in repr(settings)
    assert "secrets_dir" not in type(settings).model_fields


def test_normal_precedence_and_per_invocation_rotation_are_preserved(mounted_secrets, monkeypatch):
    original = ReceiverSettings()
    (mounted_secrets / "UNIFAI_LANGFUSE_SECRET_KEY").write_text("rotated-private")
    assert ReceiverSettings().langfuse_secret_key.get_secret_value() == "rotated-private"
    assert original.langfuse_secret_key.get_secret_value() == "file-private"
    monkeypatch.setenv("UNIFAI_LANGFUSE_SECRET_KEY", "environment-private")
    assert ReceiverSettings().langfuse_secret_key.get_secret_value() == "environment-private"
    assert (
        ReceiverSettings(
            langfuse_secret_key="explicit-private"
        ).langfuse_secret_key.get_secret_value()
        == "explicit-private"
    )


@pytest.mark.parametrize("directory", ["missing", "file", "relative", ""])
def test_configured_unavailable_directory_is_refused(tmp_path, monkeypatch, directory):
    path = tmp_path / directory
    if directory == "file":
        path.write_text("must-not-be-logged")
    monkeypatch.setenv(
        "UNIFAI_SECRETS_DIR", directory if directory in {"relative", ""} else str(path)
    )
    with pytest.raises(SettingsError, match="existing absolute directory") as error:
        ReceiverSettings()
    assert "must-not-be-logged" not in str(error.value)


def test_explicit_standard_secrets_directory_keeps_its_precedence(mounted_secrets, tmp_path):
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    (explicit / "UNIFAI_LANGFUSE_SECRET_KEY").write_text("explicit-file-private")
    settings = ReceiverSettings(_secrets_dir=explicit, interactions="disabled")
    assert settings.langfuse_secret_key.get_secret_value() == "explicit-file-private"
    assert settings.tracing == "disabled"


async def test_interaction_effects_share_secret_sources_and_invalid_settings_are_private(
    mounted_secrets,
):
    (mounted_secrets / "UNIFAI_REDIS_URI").write_text("redis://:private-password@redis:6379/0")
    settings = await load_receiver_settings(InteractionSettings)
    assert settings.redis_uri.get_secret_value() == "redis://:private-password@redis:6379/0"
    (mounted_secrets / "UNIFAI_LANGFUSE_BASE_URL").write_text("private-invalid-url")
    with pytest.raises(InvocationInfrastructureError) as error:
        await load_receiver_settings(ReceiverSettings)
    assert not error.value.retryable
    assert "private-invalid-url" not in str(error.value)


@pytest.mark.parametrize(
    "name",
    [
        "UNIFAI_LANGFUSE_SECRET_KEY",
        "unifai_credential_encryption_key",
        "UNIFAI_MONGO_URI",
        "SECRET_KEY",
    ],
)
def test_portable_profile_cannot_carry_declared_private_receiver_values(name):
    with pytest.raises(ValidationError, match="receiver-local secrets") as error:
        PlatformSettings(
            secret_key="server",
            execution_profiles={
                "remote": K8sRunnerConfig(image="receiver", env={name: "must-not-be-serialized"})
            },
            default_execution_profile="remote",
        )
    assert "must-not-be-serialized" not in str(error.value)
