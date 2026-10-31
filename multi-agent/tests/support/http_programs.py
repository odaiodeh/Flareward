"""Shared public API operations for deployment scenarios."""

import httpx
from mas.programs.models import ProgramDefinition, ProgramRef


async def publish_program(http: httpx.AsyncClient, definition: ProgramDefinition) -> ProgramRef:
    saved = await http.put(
        f"/api/programs/{definition.program_id}", json=definition.model_dump(mode="json")
    )
    assert saved.status_code == 200, saved.text
    published = await http.post(f"/api/programs/{definition.program_id}/revisions")
    assert published.status_code == 201, published.text
    return ProgramRef(program_id=definition.program_id, revision=published.json()["revision"])


async def execute_program(http, reference: ProgramRef, execution_id: str, inputs=None):
    submitted = await http.post(
        "/api/executions",
        json={
            "program": reference.model_dump(mode="json"),
            "execution_id": execution_id,
            "inputs": inputs or {},
        },
    )
    assert submitted.status_code == 202, submitted.text
    result = await http.get(f"/api/executions/{execution_id}/result", timeout=180)
    assert result.status_code == 200, result.text
    return result.json()
