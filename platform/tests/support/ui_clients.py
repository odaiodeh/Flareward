"""One owned Vite/Node process for production TypeScript client contract journeys."""

import asyncio
import subprocess
from pathlib import Path

from lumora.async_work import await_owned

ROOT = Path(__file__).resolve().parents[3]


async def run_contracts(node: str, suite: str, environment: dict[str, str] | None = None) -> str:
    result = await await_owned(
        asyncio.to_thread(
            subprocess.run,
            [node, "tests/run-api-contracts.mjs", suite],
            cwd=ROOT / "ui",
            env=environment,
            text=True,
            capture_output=True,
            timeout=60,
        )
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout
