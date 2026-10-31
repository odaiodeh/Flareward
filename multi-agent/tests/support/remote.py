"""Installed domain elements expose physical receiver evidence without an SDK dependency."""

import hashlib
import json
import os
import platform
import socket
from pathlib import Path

from mas.application.elements.factory import BaseFactory
from mas.application.elements.node import BaseNode
from mas.application.elements.specification import BaseElementSpec
from mas.core.element_deps import ElementBuildContext
from mas.core.enums import ResourceCategory
from mas.core.ref.models import ToolRef
from mas.graph.state.state_view import StateView
from pydantic import BaseModel, ConfigDict

from support.approval import ApprovalSpec
from support.elements import DependencySpec, TextResource
from support.network_probe import NetworkProbeSpec

__runengine_contract__ = "unifai-test-remote-v1"


class RemoteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dependency: ToolRef
    fail: bool = False


class RemoteNode(BaseNode):
    READS = {"user_prompt", "nodes_output"}
    WRITES = {"nodes_output", "output"}

    def __init__(self, dependency: TextResource, deps: ElementBuildContext, fail: bool) -> None:
        super().__init__()
        self._dependency, self._holder, self._fail = dependency, deps.execution_ctx, fail

    async def run(self, state: StateView) -> StateView:
        if self._fail:
            raise ValueError("Deterministic remote application failure")
        dependency, values = self._dependency, []
        while dependency is not None:
            values.append(dependency.value)
            dependency = dependency.dependency
        namespace = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
        marker = Path("/opt/unifai-e2e-receiver")
        # Sequential scenario evidence: compute reuse also preserves receiver-local files.
        root = self._holder.context.root_execution_id
        reuse_file = Path("/tmp") / ("unifai-reuse-" + hashlib.sha256(root.encode()).hexdigest())
        reused = reuse_file.exists()
        if not reused:
            reuse_file.write_text(self.uid)
        proof = {
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "system": platform.system(),
            "namespace": namespace.read_text() if namespace.exists() else None,
            "image_marker": marker.read_text() if marker.exists() else None,
            "dependencies": values,
            "environment_reused": reused,
            "environment_first_step": reuse_file.read_text(),
            "prompt": state["user_prompt"],
            "context": self._holder.context.model_dump(mode="json"),
        }
        encoded = json.dumps(proof)
        state["nodes_output"][self.uid] = encoded
        state["output"] = encoded
        return state


class RemoteFactory(BaseFactory):
    def accepts(self, cfg: RemoteConfig, element_type: str) -> bool:
        return element_type == "platform_remote"

    def create(self, cfg: RemoteConfig, **dependencies) -> RemoteNode:
        return RemoteNode(dependencies["dependency"], dependencies["deps"], cfg.fail)


class RemoteSpec(BaseElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_remote"
    name = "Remote receiver proof"
    description = "Prove physical placement through the actual element construction path"
    config_schema = RemoteConfig
    factory_cls = RemoteFactory
    reads = RemoteNode.total_reads()
    writes = RemoteNode.total_writes()


ELEMENT_SPECIFICATIONS = (RemoteSpec, DependencySpec, ApprovalSpec, NetworkProbeSpec)
