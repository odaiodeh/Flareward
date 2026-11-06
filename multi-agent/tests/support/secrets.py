"""Deterministic secret-consuming resources and a port double; no execution or storage SDKs."""

import hashlib
from uuid import uuid4

from mas.application.elements.factory import BaseFactory
from mas.application.elements.node import BaseNode
from mas.application.elements.specification import BaseElementSpec
from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory
from mas.core.field_hints import SecretHint
from mas.core.identity import Identity
from mas.core.ref.models import ToolRef
from mas.core.secrets import SECRET_PREFIX
from mas.domain.element_bundles import ResourceDefinition, ResourceKey
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import ElementStep, GraphDefinition, PathBinding, ProgramDefinition
from mas.graph.state.state_view import StateView
from pydantic import BaseModel, ConfigDict, Field, SecretStr

__runengine_contract__ = "unifai-test-secrets-v1"


class MemorySecretStore:
    def __init__(self) -> None:
        self._values: dict[str, tuple[Identity, SecretStr]] = {}

    async def put(self, owner: Identity, value: SecretStr) -> str:
        reference = SECRET_PREFIX + uuid4().hex
        self._values[reference] = (owner.model_copy(deep=True), value)
        return reference

    async def get(self, owner: Identity, reference: str) -> SecretStr:
        stored = self._values.get(reference)
        if stored is None or not owner.owns(stored[0]):
            raise PermissionError("Configuration secret is unavailable to this owner")
        return stored[1]


class MemoryCipher:
    """Per-test reversible port double; actual encryption is checked at adapter boundaries."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def encrypt(self, value: str | None) -> str | None:
        if not value:
            return value
        token = "encrypted:" + uuid4().hex
        self._values[token] = value
        return token

    def decrypt(self, value: str | None) -> str | None:
        return self._values.get(value, value)


class SecretToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str = Field(json_schema_extra=SecretHint().to_hints())
    fail: bool = False
    fail_on_run: bool = False


class SecretTool:
    def __init__(self, token: str, fail_on_run: bool) -> None:
        self.digest = hashlib.sha256(token.encode()).hexdigest()
        self._token, self.fail_on_run = token, fail_on_run

    def read(self) -> str:
        if self.fail_on_run:
            raise ValueError("Provider failed while using " + self._token)
        return self.digest


class SecretToolFactory(BaseFactory):
    def accepts(self, cfg: SecretToolConfig, element_type: str) -> bool:
        return element_type == "platform_secret_tool"

    def create(self, cfg: SecretToolConfig, **dependencies) -> SecretTool:
        if cfg.fail:
            raise ValueError("Provider failed while using " + cfg.api_key)
        return SecretTool(cfg.api_key, cfg.fail_on_run)


class SecretToolSpec(BaseElementSpec):
    category = ResourceCategory.TOOL
    type_key = "platform_secret_tool"
    name = "Secret-consuming tool"
    description = "A private credential reaches construction without entering portable payloads"
    config_schema = SecretToolConfig
    factory_cls = SecretToolFactory


class SecretNodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool: ToolRef


class SecretNode(BaseNode):
    READS = set()
    WRITES = {"output"}

    def __init__(self, tool: SecretTool) -> None:
        super().__init__()
        self._tool = tool

    async def run(self, state: StateView) -> StateView:
        state["output"] = self._tool.read()
        return state


class SecretNodeFactory(BaseFactory):
    def accepts(self, cfg: SecretNodeConfig, element_type: str) -> bool:
        return element_type == "platform_secret_node"

    def create(self, cfg: SecretNodeConfig, **dependencies) -> SecretNode:
        return SecretNode(dependencies["tool"])


class SecretNodeSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_secret_node"
    name = "Secret node"
    description = "Return a digest through a normal typed dependency and node factory"
    config_schema = SecretNodeConfig
    factory_cls = SecretNodeFactory
    reads = SecretNode.total_reads()
    writes = SecretNode.total_writes()


def secret_definition(profile, token, *, fail=False, fail_on_run=False):
    node = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.NODE, rid="node"),
        type_key="platform_secret_node",
        config={"tool": "$ref:private"},
    )
    tool = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.TOOL, rid="private"),
        type_key="platform_secret_tool",
        config={"api_key": token, "fail": fail, "fail_on_run": fail_on_run},
    )
    return ProgramDefinition(
        program_id="private-program",
        name="Private configuration",
        owner=Identity.user("owner"),
        implementation=GraphDefinition(
            steps=(
                ElementStep(
                    uid="node", element=node.key, execution=ExecutionSelection(profile=profile)
                ),
            ),
            resources=(node, tool),
            entry="node",
            exit="node",
            outputs={"digest": PathBinding(path=("output",))},
        ),
    )
