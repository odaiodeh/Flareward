"""Compose the coding adapter with receiver-local filesystem policy."""

import os
from pathlib import Path

from mas.application.elements.factory import BaseFactory
from mas.core.element_deps import ElementBuildContext

from .codex_agent_node import CodexAgentNode
from .config import CodexAgentNodeConfig
from .identifiers import CodexSandboxMode, Identifier


class CodexAgentNodeFactory(BaseFactory[CodexAgentNodeConfig, CodexAgentNode]):
    def accepts(self, cfg: CodexAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: CodexAgentNodeConfig, **dependencies) -> CodexAgentNode:
        build: ElementBuildContext = dependencies["deps"]
        if build.execution_ctx is None:
            raise ValueError("Coding agent requires an execution context")
        return CodexAgentNode(
            configuration=cfg,
            execution_holder=build.execution_ctx,
            sandbox_mode=CodexSandboxMode(
                os.environ.get("UNIFAI_CODEX_SANDBOX_MODE", CodexSandboxMode.WORKSPACE_WRITE)
            ),
            workspace_root=Path(
                os.environ.get("UNIFAI_CODING_WORKSPACE_ROOT", "/tmp/unifai-coding")
            ),
        )
