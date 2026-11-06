"""One public authoring lifecycle contract across memory and native HTTP storage."""

from httpx import AsyncClient
from mas.core.identity import Identity
from mas.domain.programs.models import GraphDefinition, ProgramDefinition, ProgramRef

from support.http_programs import execute_program
from support.operations import operation_graph


async def assert_unfinished_program_lifecycle(
    http: AsyncClient, owner: Identity, *, profile: str
) -> None:
    definition = ProgramDefinition(
        program_id="unfinished",
        name="Work in progress",
        owner=owner,
        implementation=GraphDefinition(steps=()),
    )
    saved = await http.put(
        "/api/programs/unfinished",
        json={"definition": definition.model_dump(mode="json"), "expected_version": 0},
    )
    assert saved.status_code == 200, saved.text
    assert (await http.get("/api/programs/unfinished")).json() == saved.json()
    validation = await http.post(
        "/api/programs/unfinished/validation", json={"expected_version": 1}
    )
    assert validation.status_code == 200, validation.text
    assert validation.json() == {
        "version": 1,
        "valid": False,
        "issues": [
            {
                "code": "INVALID_TOPOLOGY",
                "message": "Graph entry and exit must identify existing steps",
                "path": ["implementation"],
                "severity": "error",
            }
        ],
    }
    rejected = await http.post("/api/programs/unfinished/revisions", json={"expected_version": 1})
    assert rejected.status_code == 422, rejected.text
    assert not (await http.get("/api/programs/unfinished/revisions")).json()["revisions"]
    refused = await http.post(
        "/api/executions",
        json={
            "execution_id": "refused",
            "program": {"program_id": "unfinished", "revision": 1},
            "inputs": {},
        },
    )
    assert refused.status_code == 404, refused.text
    completed = definition.model_copy(update={"implementation": operation_graph(profile)})
    edited = await http.put(
        "/api/programs/unfinished",
        json={"definition": completed.model_dump(mode="json"), "expected_version": 1},
    )
    assert edited.status_code == 200, edited.text
    stale = await http.post("/api/programs/unfinished/validation", json={"expected_version": 1})
    assert stale.status_code == 409, stale.text
    ready = await http.post("/api/programs/unfinished/validation", json={"expected_version": 2})
    assert ready.status_code == 200 and ready.json() == {"version": 2, "issues": [], "valid": True}
    # Validation does not persist defaults, allocate revisions, or replace the draft.
    assert (await http.get("/api/programs/unfinished")).json() == edited.json()
    published = await http.post("/api/programs/unfinished/revisions", json={"expected_version": 2})
    assert published.status_code == 201, published.text
    reference = ProgramRef(program_id="unfinished", revision=published.json()["revision"])
    result = await execute_program(http, reference, "completed-draft", {"name": "ready"})
    assert result["result"] == {"answer": "typed:middle:ready"}
    reverted = await http.put(
        "/api/programs/unfinished",
        json={"definition": definition.model_dump(mode="json"), "expected_version": 2},
    )
    assert reverted.status_code == 200, reverted.text
    assert (
        await http.post("/api/programs/unfinished/revisions", json={"expected_version": 3})
    ).status_code == 422
    retry = await http.post("/api/programs/unfinished/revisions", json={"expected_version": 2})
    assert retry.json() == published.json()
    pinned = await execute_program(http, reference, "pinned-after-edit", {"name": "pinned"})
    assert pinned["result"] == {"answer": "typed:middle:pinned"}
