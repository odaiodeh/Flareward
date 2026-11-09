"""Real Git source handoff, admission, workspace protection and private failures."""

import asyncio
import os
import shutil
import sys
from dataclasses import dataclass

import pytest
from pydantic import ValidationError
from support.repositories import LocalRepository

from flareward.executions.domain.context import ExecutionContext
from flareward.services.identity.domain import Identity
from flareward.services.workspaces.domain.files import WorkspaceLayout, WorkspaceMode
from plugins.git.domain.repositories import GitFile
from plugins.git.elements.adapter import GitCLIRepository
from plugins.git.elements.config import GitBinding, GitObjectFormat, GitSettings
from plugins.git.ports import RepositoryConflict, RepositoryError


@dataclass(frozen=True)
class GitCase:
    adapter: GitCLIRepository
    context: ExecutionContext
    workspace: str
    settings: GitSettings


@pytest.fixture
def git_case(local_repository, tmp_path):
    owner = Identity.user("owner")
    settings = GitSettings(workspace_root=tmp_path / "compute")
    adapter = GitCLIRepository(
        "source", GitBinding(location=str(local_repository.path), owners=(owner,)), owner, settings
    )
    context = ExecutionContext(identity=owner, execution_id="call", root_execution_id="root")
    workspace = WorkspaceLayout.binding("root", "call", "checkout", "work", WorkspaceMode.ISOLATED)
    return GitCase(adapter, context, workspace, settings)


async def test_branch_is_resolved_then_exact_candidate_survives_branch_movement(
    local_repository, git_case
):
    adapter, context, workspace = git_case.adapter, git_case.context, git_case.workspace
    original = await adapter.resolve("refs/heads/main")
    changed = await local_repository.commit("second candidate")
    assert changed != original.commit
    assert (await adapter.resolve("HEAD")).commit == changed
    await adapter.checkout(original, workspace, context)
    destination = git_case.settings.workspace_root / workspace
    assert (destination / "answer.txt").read_text() == "first candidate"
    materialized = LocalRepository(destination)
    assert await materialized.git("rev-parse", "HEAD") == original.commit
    assert await materialized.git("status", "--porcelain") == ""
    assert not (destination / ".git/FETCH_HEAD").exists()
    assert str(local_repository.path) not in (destination / ".git/config").read_text()
    assert not list(git_case.settings.workspace_root.glob(".git-stage-*"))
    await asyncio.to_thread(shutil.rmtree, git_case.settings.workspace_root)
    await adapter.checkout(original, workspace, context)
    assert (destination / "answer.txt").read_text() == "first candidate"
    assert await materialized.git("rev-parse", "HEAD") == original.commit


async def test_annotated_tag_resolves_to_commit_not_tag_object(local_repository, git_case):
    commit = await local_repository.git("rev-parse", "HEAD")
    await local_repository.git("tag", "-a", "v1", "-m", "Candidate")
    assert await local_repository.git("rev-parse", "refs/tags/v1") != commit
    assert (await git_case.adapter.resolve("refs/tags/v1")).commit == commit


async def test_read_exact_regular_file_ignores_later_branch_movement(local_repository, git_case):
    revision = await git_case.adapter.resolve("HEAD")
    await local_repository.commit("different source")
    source = await git_case.adapter.read(
        GitFile(revision=revision, path="answer.txt"), max_bytes=64
    )
    assert source.revision == revision and source.content.decoded() == b"first candidate"
    assert not list(git_case.settings.workspace_root.glob(".git-stage-*"))


@pytest.mark.parametrize("problem", ["symlink", "missing", "large"])
async def test_git_file_read_refuses_links_missing_or_excessive_content(
    local_repository, git_case, tmp_path, problem
):
    path = "answer.txt"
    maximum = 64
    if problem == "symlink":
        path = "linked.txt"
        (local_repository.path / path).symlink_to(tmp_path / "private-target")
        await local_repository.git("add", path)
        await local_repository.git("commit", "--quiet", "-m", "Link")
    elif problem == "missing":
        path = "missing.txt"
    else:
        maximum = 1
    revision = await git_case.adapter.resolve("HEAD")
    with pytest.raises(RepositoryError) as error:
        await git_case.adapter.read(GitFile(revision=revision, path=path), max_bytes=maximum)
    assert "private" not in str(error.value)
    assert not list(git_case.settings.workspace_root.glob(".git-stage-*"))


async def test_host_git_configuration_and_templates_do_not_execute_in_the_checkout(
    git_case, tmp_path, monkeypatch
):
    hooks = tmp_path / "host-hooks"
    hooks.mkdir()
    marker = tmp_path / "host-hook-executed"
    hook = hooks / "post-checkout"
    hook.write_text(
        f"#!{sys.executable}\nfrom pathlib import Path\nPath({str(marker)!r}).touch()\n"
    )
    hook.chmod(0o700)
    config = tmp_path / "host.gitconfig"
    config.write_text(f'[core]\n hooksPath = "{hooks}"\n[init]\n templateDir = "{hooks}"\n')
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_TEMPLATE_DIR", str(hooks))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.hooksPath")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(hooks))
    revision = await git_case.adapter.resolve("HEAD")
    await git_case.adapter.checkout(revision, git_case.workspace, git_case.context)
    assert not marker.exists()
    destination = git_case.settings.workspace_root / git_case.workspace
    assert not (destination / ".git/hooks/post-checkout").exists()


async def test_git_preserves_only_approved_transport_and_its_owned_environment(
    git_case, monkeypatch
):
    monkeypatch.setenv("HTTPS_PROXY", "http://receiver-proxy.invalid:3128")
    monkeypatch.setenv("FLAREWARD_PRIVATE_MATERIAL", "private-test-material")
    monkeypatch.setenv("CODEX_API_KEY", "private-provider-key")
    spawn = asyncio.create_subprocess_exec
    captured = []

    async def inspect(*arguments, **options):
        environment = options["env"]
        assert environment["HTTPS_PROXY"] == "http://receiver-proxy.invalid:3128"
        assert (
            "FLAREWARD_PRIVATE_MATERIAL" not in environment and "CODEX_API_KEY" not in environment
        )
        captured.append(True)
        return await spawn(*arguments, **options)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", inspect)
    await git_case.adapter.resolve("HEAD")
    assert captured


async def test_sha256_repository_materializes_the_same_full_identity(tmp_path):
    origin = tmp_path / "sha256"
    origin.mkdir()
    source = LocalRepository(origin)
    await source.git("init", "--quiet", "--object-format=sha256", "--initial-branch=main")
    commit = await source.commit("sha256 candidate")
    owner = Identity.user("owner")
    settings = GitSettings(workspace_root=tmp_path / "compute")
    adapter = GitCLIRepository(
        "sha256",
        GitBinding(location=str(origin), owners=(owner,), object_format=GitObjectFormat.SHA256),
        owner,
        settings,
    )
    context = ExecutionContext(identity=owner, root_execution_id="root", execution_id="call")
    revision = await adapter.resolve("HEAD")
    assert revision.commit == commit and len(commit) == 64
    workspace = WorkspaceLayout.binding("root", "call", "key", "work", WorkspaceMode.ISOLATED)
    await adapter.checkout(revision, workspace, context)
    assert (settings.workspace_root / workspace / "answer.txt").read_text() == "sha256 candidate"


async def test_checkout_never_replaces_existing_work_or_follows_a_destination_symlink(git_case):
    revision = await git_case.adapter.resolve("HEAD")
    destination = git_case.settings.workspace_root / git_case.workspace
    destination.mkdir(parents=True)
    (destination / "answer.txt").write_text("uncommitted work")
    with pytest.raises(RepositoryConflict):
        await git_case.adapter.checkout(revision, git_case.workspace, git_case.context)
    assert (destination / "answer.txt").read_text() == "uncommitted work"
    linked = destination.with_name("linked")
    linked.symlink_to(destination, target_is_directory=True)
    with pytest.raises(RepositoryConflict):
        await git_case.adapter.checkout(
            revision, str(linked.relative_to(git_case.settings.workspace_root)), git_case.context
        )
    assert not list(git_case.settings.workspace_root.glob(".git-stage-*"))


async def test_checkout_refuses_a_symlink_parent_without_writing_outside_compute(
    git_case, tmp_path
):
    revision = await git_case.adapter.resolve("HEAD")
    outside = tmp_path / "outside"
    outside.mkdir()
    destination = git_case.settings.workspace_root / git_case.workspace
    destination.parent.parent.mkdir(parents=True)
    destination.parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(PermissionError):
        await git_case.adapter.checkout(revision, git_case.workspace, git_case.context)
    assert list(outside.iterdir()) == []
    assert not list(git_case.settings.workspace_root.glob(".git-stage-*"))


async def test_candidates_and_workspaces_cannot_widen_repository_or_owner_access(git_case):
    revision = await git_case.adapter.resolve("HEAD")
    with pytest.raises(ValueError, match="different repository"):
        await git_case.adapter.checkout(
            revision.model_copy(update={"repository": "foreign"}),
            git_case.workspace,
            git_case.context,
        )
    with pytest.raises(PermissionError):
        await git_case.adapter.checkout(
            revision,
            git_case.workspace,
            git_case.context.model_copy(update={"identity": Identity.team("owner")}),
        )
    with pytest.raises(PermissionError):
        await git_case.adapter.checkout(revision, "0" * 64 + "/work", git_case.context)
    assert not list(git_case.settings.workspace_root.glob(".git-stage-*"))


def test_operator_binding_requires_an_explicit_type_scoped_owner(local_repository, tmp_path):
    with pytest.raises(PermissionError):
        GitCLIRepository(
            "source",
            GitBinding(location=str(local_repository.path), owners=(Identity.team("owner"),)),
            Identity.user("owner"),
            GitSettings(workspace_root=tmp_path / "work"),
        )
    with pytest.raises(ValidationError):
        GitBinding(location=str(local_repository.path), owners=())


@pytest.mark.parametrize(
    "location",
    [
        "http://example.test/repo",
        "https://secret@example.test/repo",
        "https://example.test/repo?token=secret",
        "ssh://example.test/repo",
        "ext::anything",
        "relative/repo",
        "/tmp/repo\n",
    ],
)
def test_transport_binding_rejects_credentials_and_unadmitted_protocols(location):
    with pytest.raises(ValidationError):
        GitBinding(location=location, owners=(Identity.user("owner"),))


async def test_git_diagnostics_never_include_source_paths_or_raw_errors(git_case, tmp_path):
    missing = tmp_path / "private-repository-name"
    adapter = GitCLIRepository(
        "source",
        GitBinding(location=str(missing), owners=(git_case.context.identity,)),
        git_case.context.identity,
        git_case.settings,
    )
    with pytest.raises(RepositoryError) as error:
        await adapter.resolve("HEAD")
    assert "private-repository-name" not in str(error.value)
    assert str(tmp_path) not in str(error.value)
    assert not list(git_case.settings.workspace_root.glob(".git-stage-*"))


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_stop_drains_git_before_removing_its_staging_directory(
    git_case, tmp_path, monkeypatch, stop
):
    started, executable = tmp_path / "started", tmp_path / "slow-git"
    executable.write_text(
        f"#!{sys.executable}\nimport os, time\nfrom pathlib import Path\n"
        f"Path({str(started)!r}).write_text(str(os.getpid()))\ntime.sleep(120)\n"
    )
    executable.chmod(0o700)
    acquired = []
    original = asyncio.create_subprocess_exec

    async def spawn(*arguments, **options):
        process = await original(*arguments, **options)
        acquired.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    adapter = GitCLIRepository(
        "source",
        GitBinding(location=str(tmp_path / "source"), owners=(git_case.context.identity,)),
        git_case.context.identity,
        git_case.settings.model_copy(update={"timeout_seconds": 30 if stop == "cancel" else 1}),
        executable=str(executable),
    )
    task = asyncio.create_task(adapter.resolve("HEAD"))
    try:
        if stop == "cancel":
            # Cancellation needs a live process; timeout may legally expire during startup.
            async with asyncio.timeout(5):
                while not started.exists():
                    if task.done():
                        await task
                    await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(RepositoryError, match="time limit"):
                await task
        assert not list(git_case.settings.workspace_root.glob(".git-stage-*"))
        for process in acquired:
            assert process.returncode is not None
            with pytest.raises(ProcessLookupError):
                os.kill(process.pid, 0)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_unbounded_cli_output_fails_privately_and_cleans_staging(git_case, tmp_path):
    executable = tmp_path / "noisy-git"
    executable.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stdout.write('private-output' * 10000)\n"
    )
    executable.chmod(0o700)
    adapter = GitCLIRepository(
        "source",
        GitBinding(location=str(tmp_path), owners=(git_case.context.identity,)),
        git_case.context.identity,
        git_case.settings,
        executable=str(executable),
    )
    with pytest.raises(RepositoryError) as error:
        await adapter.resolve("HEAD")
    assert "private-output" not in str(error.value)
    assert not list(git_case.settings.workspace_root.glob(".git-stage-*"))
