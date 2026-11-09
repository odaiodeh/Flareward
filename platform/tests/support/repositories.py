"""Owned local Git fixtures shared by repository adapter and program scenarios."""

import asyncio
import os
import subprocess
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import pytest

from flareward.async_work import await_owned


@dataclass(frozen=True)
class LocalRepository:
    path: Path

    async def git(self, *arguments: str) -> str:
        result = await await_owned(
            asyncio.to_thread(
                partial(
                    subprocess.run,
                    (
                        "git",
                        "-c",
                        "user.name=Platform Test",
                        "-c",
                        "user.email=test@example.test",
                        "-c",
                        "core.hooksPath=" + os.devnull,
                        *arguments,
                    ),
                    cwd=self.path,
                    env={
                        "PATH": os.environ.get("PATH", ""),
                        "GIT_CONFIG_NOSYSTEM": "1",
                        "GIT_CONFIG_GLOBAL": os.devnull,
                    },
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
            )
        )
        return result.stdout.strip()

    async def commit(self, content: str) -> str:
        await asyncio.to_thread((self.path / "answer.txt").write_text, content)
        await self.git("add", "answer.txt")
        await self.git("commit", "--quiet", "-m", "Source candidate")
        return await self.git("rev-parse", "HEAD")


@pytest.fixture
async def local_repository(tmp_path):
    path = tmp_path / "origin"
    path.mkdir()
    repository = LocalRepository(path)
    await repository.git("init", "--quiet", "--initial-branch=main")
    await repository.commit("first candidate")
    return repository
