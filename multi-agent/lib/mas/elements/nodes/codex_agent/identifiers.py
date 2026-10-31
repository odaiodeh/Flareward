"""Codex node identity and catalog metadata, following the node convention."""

from dataclasses import dataclass
from enum import StrEnum


class Identifier(StrEnum):
    TYPE = "codex_agent_node"


class CodexSandboxMode(StrEnum):
    WORKSPACE_WRITE = "workspace-write"
    EXTERNAL = "danger-full-access"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: list[str]


META = Meta(
    name="Codex Agent Node",
    description="Run installed Codex CLI in the selected workflow environment",
    tags=["agent", "node", "coding", "codex"],
)
