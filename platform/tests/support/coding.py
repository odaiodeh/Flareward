"""Read physical workspace evidence after actual typed coding invocations."""

import asyncio
import hashlib
import os
import platform
import socket
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from lumora.elements.factory import BaseFactory
from lumora.elements.operation import BaseOperation, OperationContext
from lumora.elements.specification import BaseElementSpec
from lumora.resources.domain.categories import ResourceCategory


class EvidenceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace: str


class EvidenceRecord(BaseModel):
    source: str
    verified: str
    system: str
    hostname: str
    namespace: str | None
    image_marker: str


class EvidenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: EvidenceRecord


def read_evidence(workspace: Path) -> EvidenceRecord:
    namespace = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
    return EvidenceRecord(
        source=(workspace / "calculation.py").read_text(),
        verified=(workspace / "verified.txt").read_text().strip(),
        system=platform.system(),
        hostname=socket.gethostname(),
        namespace=namespace.read_text() if namespace.is_file() else None,
        image_marker=Path("/opt/lumora-e2e-receiver").read_text(),
    )


class EvidenceOperation(BaseOperation[EvidenceInput, EvidenceResult]):
    async def execute(self, request: EvidenceInput, context: OperationContext) -> EvidenceResult:
        namespace = hashlib.sha256(context.execution.root_execution_id.encode()).hexdigest()
        directory = Path(
            os.environ.get("LUMORA_WORKSPACE_ROOT", "/tmp/lumora-workspaces")
        ).resolve()
        workspace = (directory / request.workspace).resolve()
        if not workspace.is_relative_to(directory / namespace):
            raise ValueError("Evidence workspace does not belong to this execution")
        return EvidenceResult(evidence=await asyncio.to_thread(read_evidence, workspace))


class EvidenceFactory(BaseFactory[EvidenceConfig, EvidenceOperation]):
    def accepts(self, cfg: EvidenceConfig, element_type: str) -> bool:
        return element_type == "coding_evidence"

    def create(self, cfg: EvidenceConfig, **dependencies: Any) -> EvidenceOperation:
        return EvidenceOperation()


class EvidenceSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "coding_evidence"
    name = "Coding workspace evidence"
    description = "Read files written by coding operations in the selected environment"
    config_schema = EvidenceConfig
    factory_cls = EvidenceFactory
    input_schema = EvidenceInput
    result_schema = EvidenceResult


ELEMENT_SPECIFICATIONS = (EvidenceSpec,)
