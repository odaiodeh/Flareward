"""Real subprocesses verify the Codex adapter protocol and owned cancellation."""

import asyncio
import os
import sys
from pathlib import Path

import pytest
from mas.application.coding.contracts import CodingAgentError, CodingRequest
from mas.elements.nodes.codex_agent.codex_cli import CodexCodingAgent
from mas.elements.nodes.codex_agent.config import CodexAgentNodeConfig
from mas.elements.nodes.codex_agent.identifiers import CodexSandboxMode
from pydantic import SecretStr


@pytest.fixture
def cli(tmp_path):
    executable = tmp_path / "codex"
    executable.write_text(
        f"#!{sys.executable}\n"
        + """
import json
import os
import subprocess
import sys
import time
from pathlib import Path

prompt = sys.stdin.read()
workspace = Path(sys.argv[sys.argv.index('--cd') + 1])
(workspace / 'sandbox').write_text(sys.argv[sys.argv.index('--sandbox') + 1])
(workspace / 'home').write_text(os.environ['CODEX_HOME'])
assert 'OPENAI_API_KEY' not in os.environ
assert os.environ['CODEX_API_KEY'] == 'private-test-token'
assert '--json' in sys.argv and '--ephemeral' in sys.argv
assert 'shell_environment_policy.inherit="none"' in sys.argv
if prompt == 'hang':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
    (workspace / 'child').write_text(str(child.pid))
# Publish readiness atomically, after setup and any descendant acquisition.
(workspace / 'starting').write_text(str(os.getpid()))
(workspace / 'starting').replace(workspace / 'started')
if prompt == 'hang':
    time.sleep(120)
if prompt == 'failure':
    print('private-test-token', file=sys.stderr)
    print(json.dumps({'type':'turn.failed', 'error':{'message':'private-test-token'}}))
    sys.exit(1)
if prompt == 'commands':
    for _ in range(3):
        print(json.dumps({'type':'item.started','item':{'type':'command_execution'}}), flush=True)
    time.sleep(120)
if prompt == 'overflow':
    print('x' * 2048)
    sys.exit(0)
if prompt == 'incomplete':
    sys.exit(0)
(workspace / 'answer.txt').write_text(prompt)
print(json.dumps({'type':'item.started','item':{'type':'command_execution'}}))
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'done'}}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':12,'output_tokens':2}}))
"""
    )
    executable.chmod(0o700)
    return executable


def agent(cli, tmp_path, **options):
    return CodexCodingAgent(
        CodexAgentNodeConfig(
            api_key=SecretStr("private-test-token"), model="explicit-test", **options
        ),
        workspace_root=tmp_path / "workspaces",
        executable=str(cli),
    )


async def test_protocol_edits_workspace_and_cleans_private_home(cli, tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-host-key")
    implementation = agent(cli, tmp_path)
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
async def test_failure_is_sanitized_and_reaped(cli, tmp_path, prompt):
    with pytest.raises(CodingAgentError) as caught:
        await agent(cli, tmp_path, max_output_bytes=1024, max_commands=1).execute(
            CodingRequest(prompt=prompt, workspace="run/work")
        )
    assert "private-test-token" not in str(caught.value)
    pid = int((tmp_path / "workspaces/run/work/started").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.parametrize("cancel", [False, True], ids=["timeout", "cancelled"])
async def test_timeout_and_cancellation_kill_process_group(cli, tmp_path, cancel):
    task = asyncio.create_task(
        agent(cli, tmp_path, timeout_seconds=30 if cancel else 5).execute(
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
async def test_workspace_cannot_escape_operator_root(cli, tmp_path, workspace):
    with pytest.raises(CodingAgentError):
        await agent(cli, tmp_path).execute(CodingRequest(prompt="write", workspace=workspace))


async def test_workspace_symlink_cannot_escape_root(cli, tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "redirect").symlink_to(outside, target_is_directory=True)
    with pytest.raises(CodingAgentError):
        await agent(cli, tmp_path).execute(CodingRequest(prompt="write", workspace="redirect/work"))
    assert not (outside / "work").exists()


async def test_operator_private_file_supplies_key_without_resource_credential(
    cli, tmp_path, monkeypatch
):
    credential = tmp_path / "private-key"
    credential.write_text("private-test-token")
    credential.chmod(0o600)
    monkeypatch.setenv("UNIFAI_CODEX_API_KEY_FILE", str(credential))
    implementation = CodexCodingAgent(
        CodexAgentNodeConfig(model="explicit-test"),
        workspace_root=tmp_path / "workspaces",
        executable=str(cli),
    )
    result = await implementation.execute(CodingRequest(prompt="write", workspace="run/work"))
    assert result.content == "done"
    assert "private-test-token" not in result.model_dump_json()


async def test_missing_credential_fails_before_starting_cli(cli, tmp_path, monkeypatch):
    monkeypatch.delenv("UNIFAI_CODEX_API_KEY_FILE", raising=False)
    implementation = CodexCodingAgent(
        CodexAgentNodeConfig(model="explicit-test"),
        workspace_root=tmp_path / "workspaces",
        executable=str(cli),
    )
    with pytest.raises(CodingAgentError, match="credential is unavailable"):
        await implementation.execute(CodingRequest(prompt="write", workspace="run/work"))
    assert not (tmp_path / "workspaces").exists()


async def test_external_isolation_requires_explicit_operator_composition(cli, tmp_path):
    implementation = CodexCodingAgent(
        CodexAgentNodeConfig(model="explicit-test", api_key=SecretStr("private-test-token")),
        workspace_root=tmp_path / "workspaces",
        executable=str(cli),
        sandbox_mode=CodexSandboxMode.EXTERNAL,
    )
    await implementation.execute(CodingRequest(prompt="write", workspace="run/work"))
    assert (tmp_path / "workspaces/run/work/sandbox").read_text() == "danger-full-access"
