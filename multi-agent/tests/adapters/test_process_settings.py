"""Worker process settings round-trip through the actual environment parser."""

from pydantic import SecretStr
from support.processes import settings_environment

from config.worker_settings import WorkerSettings


def test_worker_journal_path_survives_process_environment_serialization(tmp_path, monkeypatch):
    settings = WorkerSettings(
        environment_sqlite=tmp_path / "owned journal.sqlite",
        tracing="langfuse",
        langfuse_base_url="http://localhost:4318",
        langfuse_public_key=SecretStr("public"),
        langfuse_secret_key=SecretStr("private"),
    )
    environment = settings_environment(settings)
    for name, value in environment.items():
        if name.startswith("UNIFAI_"):
            monkeypatch.setenv(name, value)
    restored = WorkerSettings()
    assert restored.environment_sqlite == settings.environment_sqlite
    assert restored.host == settings.host
    assert restored.tracing == settings.tracing
    assert restored.langfuse_base_url == settings.langfuse_base_url
    assert restored.langfuse_secret_key == settings.langfuse_secret_key
