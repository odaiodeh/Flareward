"""Concrete vendor node; reusable workflow behavior belongs to the application."""

from pathlib import Path

from mas.application.coding.node import CodingAgentNode
from mas.core.execution_context import ExecutionContextHolder

from .codex_cli import CodexCodingAgent
from .config import CodexAgentNodeConfig
from .identifiers import CodexSandboxMode


class CodexAgentNode(CodingAgentNode):
    def __init__(
        self,
        *,
        configuration: CodexAgentNodeConfig,
        execution_holder: ExecutionContextHolder,
        workspace_root: Path,
        sandbox_mode: CodexSandboxMode = CodexSandboxMode.WORKSPACE_WRITE,
    ) -> None:
        super().__init__(
            CodexCodingAgent(
                configuration, workspace_root=workspace_root, sandbox_mode=sandbox_mode
            ),
            execution_holder,
            configuration.workspace,
            configuration.instructions,
        )
