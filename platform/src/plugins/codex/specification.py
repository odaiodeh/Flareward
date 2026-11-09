"""Register the Codex integration through normal element contracts."""

import os
from pathlib import Path
from typing import Any

from flareward.elements.coding.contracts import CodingInput, CodingOutcome
from flareward.elements.coding.operation import CodingOperation
from flareward.elements.factory import BaseFactory
from flareward.elements.specification import BaseElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.codex.adapter import CodexCodingAgent
from plugins.codex.config import CodexConfig
from plugins.codex.identifiers import TYPE_KEY, CodexSandboxMode


class CodexFactory(BaseFactory[CodexConfig, CodingOperation]):
    def accepts(self, cfg: CodexConfig, element_type: str) -> bool:
        return element_type == TYPE_KEY

    def create(self, cfg: CodexConfig, **dependencies: Any) -> CodingOperation:
        agent = CodexCodingAgent(
            cfg,
            workspace_root=Path(
                os.environ.get("FLAREWARD_WORKSPACE_ROOT", "/tmp/flareward-workspaces")
            ),
            sandbox_mode=CodexSandboxMode(
                os.environ.get("FLAREWARD_CODEX_SANDBOX_MODE", CodexSandboxMode.WORKSPACE_WRITE)
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
