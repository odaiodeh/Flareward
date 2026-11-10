# Tool execution

Tools implement one public `async run(**arguments)` operation. The executor
awaits it directly; `run`/`arun` pairs and synchronous event-loop bridges are no
longer part of the tool contract. Pure schema conversion and registration remain
synchronous. Factories create the configured adapter; resource acquisition that
performs I/O belongs to its async operation.

`ToolExecutorManager.execute_requests_async` accepts `ToolExecutionRequest`
objects, validates arguments, applies the configured execution strategy, and
returns responses keyed by the original call IDs. Agent action execution retains
input order, including missing-tool failures. The executor owns each tool trace
context through completion, error, and cancellation.

```python
from typing import Protocol

from pydantic import BaseModel

from lumora.elements.ports.tool import BaseTool


class EvidenceArguments(BaseModel):
    key: str


class EvidenceReader(Protocol):
    async def read(self, key: str) -> str: ...


class ReadEvidenceTool(BaseTool):
    name = "read_evidence"
    description = "Read evidence through an injected application port."
    args_schema = EvidenceArguments

    def __init__(self, reader: EvidenceReader) -> None:
        self._reader = reader

    async def run(self, key: str) -> str:
        return await self._reader.read(key)
```

Use native async provider APIs where available. A blocking SDK stays inside its
adapter and uses owned offloading: cancellation drains the operation before its
connection or other resources close. The SSH adapter connects lazily, serializes
access to its connection, and does not repeat an uncertain command. Configured
dependencies belong to their builder/caller. OpenShell is an execution backend;
its retired tool-routing integration is not part of this contract.

Declare `ToolAccessMode.WRITE` or `DESTRUCTIVE` for operations with effects. The
generic retry policy retries reads only. Writes require an application-specific
policy that knows the operation's idempotency contract. Approval policies use the
same access metadata and await the application's approval gate.

Native contract tests live in `tests/application/test_agent_execution.py` and the
SSH, retrieval, and approval adapter/integration cases. SDK doubles
verify adapter ownership and cancellation; actual remote deployment tests provide
separate evidence for backend behavior.
