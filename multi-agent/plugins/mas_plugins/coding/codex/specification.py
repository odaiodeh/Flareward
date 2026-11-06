"""Register the Codex integration through normal element contracts."""

import os
from pathlib import Path
from typing import Any

from mas.application.coding.contracts import CodingInput, CodingOutcome
from mas.application.coding.operation import CodingOperation
from mas.application.elements.factory import BaseFactory
from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from .adapter import CodexCodingAgent
from .config import CodexConfig
from .identifiers import TYPE_KEY, CodexSandboxMode


class CodexFactory(BaseFactory[CodexConfig, CodingOperation]):
    def accepts(self, cfg: CodexConfig, element_type: str) -> bool:
        return element_type == TYPE_KEY

    def create(self, cfg: CodexConfig, **dependencies: Any) -> CodingOperation:
        agent = CodexCodingAgent(
            cfg,
            workspace_root=Path(os.environ.get("UNIFAI_WORKSPACE_ROOT", "/tmp/unifai-workspaces")),
            sandbox_mode=CodexSandboxMode(
                os.environ.get("UNIFAI_CODEX_SANDBOX_MODE", CodexSandboxMode.WORKSPACE_WRITE)
            ),
        )
        return CodingOperation(
            agent,
            cfg.workspace,
            cfg.instructions,
            cfg.workspace_mode,
            preparation=dependencies.get("workspace_preparation"),
        )


class CodexSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = TYPE_KEY
    name = "Codex Coding Agent"
    description = "Run installed Codex CLI with typed work and results in the selected environment"
    config_schema = CodexConfig
    factory_cls = CodexFactory
    input_schema = CodingInput
    result_schema = CodingOutcome
    tags = ["agent", "operation", "coding", "codex"]


ELEMENT_SPECIFICATIONS = (CodexSpec,)
