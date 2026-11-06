"""Shared public API operations for deployment scenarios."""

import httpx
from mas.domain.programs.models import ProgramDefinition, ProgramRef


async def publish_program(
    http: httpx.AsyncClient, definition: ProgramDefinition, *, headers: dict[str, str] | None = None
) -> ProgramRef:
    previous = await http.get(f"/api/programs/{definition.program_id}", headers=headers)
    assert previous.status_code in {200, 404}, previous.text
    version = previous.json()["version"] if previous.status_code == 200 else 0
    saved = await http.put(
        f"/api/programs/{definition.program_id}",
        json={"definition": definition.model_dump(mode="json"), "expected_version": version},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    published = await http.post(
        f"/api/programs/{definition.program_id}/revisions",
        json={"expected_version": saved.json()["version"]},
        headers=headers,
    )
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
