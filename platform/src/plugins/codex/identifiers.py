"""Provider identity and receiver-controlled isolation policy."""

from enum import StrEnum

TYPE_KEY = "codex_coding"


class CodexSandboxMode(StrEnum):
    WORKSPACE_WRITE = "workspace-write"
    EXTERNAL = "danger-full-access"
