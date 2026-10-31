"""Read physical workspace evidence after actual coding invocations."""

import asyncio
import hashlib
import json
import os
import platform
import socket
from pathlib import Path

from mas.application.elements.factory import BaseFactory
from mas.application.elements.node import BaseNode
from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.graph.state.state_view import StateView
from pydantic import BaseModel


class EvidenceConfig(BaseModel):
    pass


def read_evidence(workspace: Path) -> dict[str, str | None]:
    namespace = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
    return {
        "source": (workspace / "calculation.py").read_text(),
        "verified": (workspace / "verified.txt").read_text().strip(),
        "system": platform.system(),
        "hostname": socket.gethostname(),
        "namespace": namespace.read_text() if namespace.is_file() else None,
        "image_marker": Path("/opt/unifai-e2e-receiver").read_text(),
    }


class EvidenceNode(BaseNode):
    READS = {"nodes_output"}
    WRITES = {"nodes_output"}

    def __init__(self, holder):
        super().__init__()
        self._holder = holder

    async def run(self, state: StateView) -> StateView:
        namespace = hashlib.sha256(self._holder.context.root_execution_id.encode()).hexdigest()
        directory = Path(os.environ.get("UNIFAI_CODING_WORKSPACE_ROOT", "/tmp/unifai-coding"))
        workspace = directory / namespace / "work"
        state["nodes_output"][self.uid] = json.dumps(
            await asyncio.to_thread(read_evidence, workspace)
        )
        return state


class EvidenceFactory(BaseFactory):
    def accepts(self, cfg, element_type):
        return element_type == "coding_evidence"

    def create(self, cfg, **dependencies):
        return EvidenceNode(dependencies["deps"].execution_ctx)


class EvidenceSpec(BaseElementSpec):
    category = ResourceCategory.NODE
    type_key = "coding_evidence"
    name = "Coding workspace evidence"
    description = "Read files written by the actual coding agent in this environment"
    config_schema = EvidenceConfig
    factory_cls = EvidenceFactory
    reads = EvidenceNode.total_reads()
    writes = EvidenceNode.total_writes()


ELEMENT_SPECIFICATIONS = (EvidenceSpec,)
