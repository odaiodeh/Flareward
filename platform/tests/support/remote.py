"""Installed domain elements expose physical receiver evidence without an SDK dependency."""

import hashlib
import json
import os
import platform
import socket
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue

from flareward.elements.construction.context import ElementBuildContext
from flareward.elements.factory import BaseFactory
from flareward.elements.node import BaseNode
from flareward.elements.operation import BaseOperation, OperationContext
from flareward.elements.specification import BaseElementSpec
from flareward.executions.domain.context import ExecutionContext
from flareward.programs.graph.state.state_view import StateView
from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.domain.references import ToolRef
from support.approval import ApprovalSpec
from support.elements import DependencySpec, TextResource
from support.network_probe import NetworkProbeSpec

__runengine_contract__ = "flareward-test-remote-v1"


class RemoteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dependency: ToolRef
    fail: bool = False


class ReceiverProbe:
    def __init__(self, dependency: TextResource, fail: bool) -> None:
        self._dependency, self._fail = dependency, fail

    def capture(self, context: ExecutionContext, key: str, prompt: str) -> dict[str, JsonValue]:
        if self._fail:
            raise ValueError("Deterministic remote application failure")
        dependency, values = self._dependency, []
        while dependency is not None:
            values.append(dependency.value)
            dependency = dependency.dependency
        marker = Path("/opt/flareward-e2e-receiver")
        root = context.root_execution_id
        reuse_file = Path("/tmp") / ("flareward-reuse-" + hashlib.sha256(root.encode()).hexdigest())
        reused = reuse_file.exists()
        if not reused:
            reuse_file.write_text(key)
        return {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "system": platform.system(),
            # Descriptive fixture context, not authorization or physical attestation.
            "namespace": os.environ.get("FLAREWARD_TEST_NAMESPACE"),
            "image_marker": marker.read_text() if marker.exists() else None,
            "dependencies": values,
            "environment_reused": reused,
            "environment_first_step": reuse_file.read_text(),
            "prompt": prompt,
            "context": context.model_dump(mode="json"),
        }


class RemoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class RemoteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proof: dict[str, JsonValue]


class RemoteOperation(BaseOperation[RemoteInput, RemoteResult]):
    def __init__(self, dependency: TextResource, fail: bool) -> None:
        self._probe = ReceiverProbe(dependency, fail)

    async def execute(self, request: RemoteInput, context: OperationContext) -> RemoteResult:
        return RemoteResult(proof=self._probe.capture(context.execution, context.key, request.text))


class RemoteOperationFactory(BaseFactory):
    def accepts(self, cfg: RemoteConfig, element_type: str) -> bool:
        return element_type == "platform_remote_operation"

    def create(self, cfg: RemoteConfig, **dependencies) -> RemoteOperation:
        return RemoteOperation(dependencies["dependency"], cfg.fail)


class RemoteOperationSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "platform_remote_operation"
    name = "Remote operation proof"
    description = "Prove typed invocation placement and environment ownership"
    config_schema = RemoteConfig
    factory_cls = RemoteOperationFactory
    input_schema = RemoteInput
    result_schema = RemoteResult


class RemoteNode(BaseNode):
    READS = {"user_prompt", "nodes_output"}
    WRITES = {"nodes_output", "output"}

    def __init__(self, dependency: TextResource, deps: ElementBuildContext, fail: bool) -> None:
        super().__init__()
        self._probe, self._holder = ReceiverProbe(dependency, fail), deps.execution_ctx

    async def run(self, state: StateView) -> StateView:
        proof = self._probe.capture(self._holder.context, self.uid, state["user_prompt"])
        encoded = json.dumps(proof)
        state["nodes_output"][self.uid] = encoded
        state["output"] = encoded
        return state


class RemoteFactory(BaseFactory):
    def accepts(self, cfg: RemoteConfig, element_type: str) -> bool:
        return element_type == "platform_remote"

    def create(self, cfg: RemoteConfig, **dependencies) -> RemoteNode:
        return RemoteNode(dependencies["dependency"], dependencies["deps"], cfg.fail)


class RemoteSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_remote"
    name = "Remote receiver proof"
    description = "Prove physical placement through the actual element construction path"
    config_schema = RemoteConfig
    factory_cls = RemoteFactory
    reads = RemoteNode.total_reads()
    writes = RemoteNode.total_writes()


ELEMENT_SPECIFICATIONS = (
    RemoteSpec,
    RemoteOperationSpec,
    DependencySpec,
    ApprovalSpec,
    NetworkProbeSpec,
)
