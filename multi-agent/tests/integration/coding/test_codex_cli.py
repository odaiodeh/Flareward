"""Real subprocesses verify the Codex adapter protocol and owned cancellation."""

import asyncio
import os
from pathlib import Path

import pytest
from mas.application.coding.contracts import CodingAgentError, CodingRequest
from mas_plugins.coding.codex.adapter import CodexCodingAgent
from mas_plugins.coding.codex.config import CodexConfig
from mas_plugins.coding.codex.identifiers import CodexSandboxMode
from pydantic import SecretStr


def agent(codex_cli, tmp_path, **options):
    return CodexCodingAgent(
        CodexConfig(api_key=SecretStr("private-test-token"), model="explicit-test", **options),
        workspace_root=tmp_path / "workspaces",
        executable=str(codex_cli),
    )


async def test_protocol_edits_workspace_and_cleans_private_home(codex_cli, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-host-key")
    implementation = agent(codex_cli, tmp_path)
    result = await implementation.execute(
        CodingRequest(prompt="write evidence", workspace="run/work")
    )
    assert result.content == "done" and result.commands == 1
    assert result.usage.input_tokens == 12 and result.usage.output_tokens == 2
    workspace = tmp_path / "workspaces/run/work"
    assert (workspace / "answer.txt").read_text() == "write evidence"
    assert not Path((workspace / "home").read_text()).exists()
    result = await implementation.execute(CodingRequest(prompt="second step", workspace="run/work"))
    assert result.content == "done"
    assert (workspace / "answer.txt").read_text() == "second step"


@pytest.mark.parametrize("prompt", ["failure", "overflow", "incomplete", "commands"])
async def test_failure_is_sanitized_and_reaped(codex_cli, tmp_path, prompt):
    with pytest.raises(CodingAgentError) as caught:
        await agent(codex_cli, tmp_path, max_output_bytes=1024, max_commands=1).execute(
            CodingRequest(prompt=prompt, workspace="run/work")
        )
    assert "private-test-token" not in str(caught.value)
    pid = int((tmp_path / "workspaces/run/work/started").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.parametrize("cancel", [False, True], ids=["timeout", "cancelled"])
async def test_timeout_and_cancellation_kill_process_group(codex_cli, tmp_path, cancel):
    task = asyncio.create_task(
        agent(codex_cli, tmp_path, timeout_seconds=30 if cancel else 5).execute(
            CodingRequest(prompt="hang", workspace="run/work")
        )
    )
    started = tmp_path / "workspaces/run/work/started"
    try:
        async with asyncio.timeout(10):
            while not started.exists():
                if task.done():
                    await task
                await asyncio.sleep(0.01)
        pid = int(started.read_text())
        child_pid = int((started.parent / "child").read_text())
        os.kill(child_pid, 0)
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else CodingAgentError):
            await task
        # Delivery of termination signals and OS reaping need not be simultaneous.
        async with asyncio.timeout(3):
            while True:
                try:
                    os.killpg(pid, 0)
                except ProcessLookupError:
                    break
                await asyncio.sleep(0.01)
        with pytest.raises(ProcessLookupError):
            os.kill(child_pid, 0)
        assert not Path((started.parent / "home").read_text()).exists()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("workspace", ["../escape", "/tmp/outside", "."])
async def test_workspace_cannot_escape_operator_root(codex_cli, tmp_path, workspace):
    with pytest.raises(CodingAgentError):
        await agent(codex_cli, tmp_path).execute(CodingRequest(prompt="write", workspace=workspace))


async def test_workspace_symlink_cannot_escape_root(codex_cli, tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "redirect").symlink_to(outside, target_is_directory=True)
    with pytest.raises(CodingAgentError):
        await agent(codex_cli, tmp_path).execute(
            CodingRequest(prompt="write", workspace="redirect/work")
        )
    assert not (outside / "work").exists()


async def test_operator_private_file_supplies_key_without_resource_credential(
    codex_cli, tmp_path, monkeypatch
):
    credential = tmp_path / "private-key"
    credential.write_text("private-test-token")
    credential.chmod(0o600)
    monkeypatch.setenv("UNIFAI_CODEX_API_KEY_FILE", str(credential))
    implementation = CodexCodingAgent(
        CodexConfig(model="explicit-test"),
        workspace_root=tmp_path / "workspaces",
        executable=str(codex_cli),
    )
    result = await implementation.execute(CodingRequest(prompt="write", workspace="run/work"))
    assert result.content == "done"
    assert "private-test-token" not in result.model_dump_json()


async def test_missing_credential_fails_before_starting_cli(codex_cli, tmp_path, monkeypatch):
    monkeypatch.delenv("UNIFAI_CODEX_API_KEY_FILE", raising=False)
    implementation = CodexCodingAgent(
        CodexConfig(model="explicit-test"),
        workspace_root=tmp_path / "workspaces",
        executable=str(codex_cli),
    )
    with pytest.raises(CodingAgentError, match="credential is unavailable"):
        await implementation.execute(CodingRequest(prompt="write", workspace="run/work"))
    assert not (tmp_path / "workspaces").exists()


async def test_external_isolation_requires_explicit_operator_composition(codex_cli, tmp_path):
    implementation = CodexCodingAgent(
        CodexConfig(model="explicit-test", api_key=SecretStr("private-test-token")),
        workspace_root=tmp_path / "workspaces",
        executable=str(codex_cli),
        sandbox_mode=CodexSandboxMode.EXTERNAL,
    )
    await implementation.execute(CodingRequest(prompt="write", workspace="run/work"))
    assert (tmp_path / "workspaces/run/work/sandbox").read_text() == "danger-full-access"
