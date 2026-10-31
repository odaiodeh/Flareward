"""Public UnifAI API and installed receivers exercise actual remote program lifetimes."""

import asyncio
import base64
import json
from uuid import uuid4

import pytest
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.programs.models import (
    ApplicationDefinition,
    ElementStep,
    ExecutionSelection,
    GraphDefinition,
    PathBinding,
    ProgramCallStep,
    ProgramDefinition,
)
from support.http_programs import execute_program, publish_program
from support.remote_scenarios import borrowing_graph, remote_graph, scoped_environment_graph
from support.scenarios import resource
from support.telemetry import span_attributes
from support.temporal import replay


@pytest.mark.parametrize("retained", [False, True], ids=["invocations", "retained-environment"])
async def test_deployed_graph_constructs_dependencies_and_proves_remote_lifetime(
    deployed_remote, retained
):
    deployment = deployed_remote
    reference = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="remote-lifetime",
            name="Remote lifetime",
            owner=deployment.owner,
            implementation=remote_graph(retained=retained),
        ),
    )
    execution_id = uuid4().hex
    result = await execute_program(
        deployment.http, reference, execution_id, {"name": "remote input"}
    )
    assert result["phase"] == "completed", json.dumps(result, indent=2)
    proofs = [json.loads(value) for value in result["result"]["proofs"].values()]
    assert len(proofs) == 3
    for proof in proofs:
        deployment.backend.verify(proof)
        assert proof["prompt"] == "remote input"
        assert proof["context"]["execution_id"] == execution_id
    assert len({proof["hostname"] for proof in proofs}) == (1 if retained else 3)
    by_step = {step: json.loads(value) for step, value in result["result"]["proofs"].items()}
    for step, proof in by_step.items():
        assert proof["environment_reused"] == (retained and step != "first")
        assert proof["environment_first_step"] == ("first" if retained else step)
    children = await deployment.http.get(f"/api/executions/{execution_id}/children")
    assert children.status_code == 200 and children.json() == [], children.text
    if deployment.replay is not None:
        await deployment.replay(result["context"]["engine_handle"])
    await deployment.backend.assert_clean()


async def test_deployed_graph_calls_application_and_remote_child_graph(deployed_remote):
    deployment = deployed_remote
    leaf = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="remote-leaf",
            name="Remote leaf",
            owner=deployment.owner,
            implementation=remote_graph(),
        ),
    )
    application = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="remote-application",
            name="Application child",
            owner=deployment.owner,
            implementation=ApplicationDefinition(
                implementation="composed", version="1", children={"greet": leaf}
            ),
        ),
    )
    root = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="remote-root",
            name="Graph root",
            owner=deployment.owner,
            implementation=GraphDefinition(
                steps=(
                    ProgramCallStep(
                        uid="application",
                        program=application,
                        inputs={"name": PathBinding(path=("user_prompt",))},
                        outputs={"nodes_output": PathBinding(path=("proofs",))},
                    ),
                ),
                entry="application",
                exit="application",
                inputs={"user_prompt": PathBinding(path=("name",))},
                outputs={"proofs": PathBinding(path=("nodes_output",))},
            ),
        ),
    )
    execution_id = uuid4().hex
    result = await execute_program(deployment.http, root, execution_id, {"name": "composed input"})
    assert result["phase"] == "completed", json.dumps(result, indent=2)
    children = (await deployment.http.get(f"/api/executions/{execution_id}/children")).json()
    assert len(children) == 1 and children[0]["program"] == application.model_dump(mode="json")
    grandchildren = (
        await deployment.http.get(f"/api/executions/{children[0]['execution_id']}/children")
    ).json()
    assert len(grandchildren) == 1 and grandchildren[0]["program"] == leaf.model_dump(mode="json")
    for value in result["result"]["proofs"].values():
        proof = json.loads(value)
        deployment.backend.verify(proof)
        assert proof["context"]["execution_id"] == grandchildren[0]["execution_id"]
        assert proof["context"]["parent_execution_id"] == children[0]["execution_id"]
        assert proof["context"]["root_execution_id"] == execution_id
    if deployment.replay is not None:
        for record in (result, children[0], grandchildren[0]):
            await deployment.replay(record["context"]["engine_handle"])
    await deployment.backend.assert_clean()


async def test_deployed_remote_application_failure_releases_owned_resources(deployed_remote):
    deployment = deployed_remote
    reference = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="remote-failure",
            name="Remote failure",
            owner=deployment.owner,
            implementation=remote_graph(retained=True, fail=True),
        ),
    )
    result = await execute_program(deployment.http, reference, uuid4().hex, {"name": "failure"})
    assert result["phase"] == "failed" and result["failure"]["kind"] == "application", result
    if deployment.replay is not None:
        await deployment.replay(result["context"]["engine_handle"])
    await deployment.backend.assert_clean()


async def test_child_borrows_parent_environment_and_parent_remains_its_owner(deployed_remote):
    deployment = deployed_remote
    child_graph = remote_graph(retained=True).model_copy(update={"environments": {}})
    child = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="borrowing-child",
            name="Borrowing child",
            owner=deployment.owner,
            implementation=child_graph,
        ),
    )
    root = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="environment-owner",
            name="Environment owner",
            owner=deployment.owner,
            implementation=borrowing_graph(child),
        ),
    )
    execution_id = uuid4().hex
    result = await execute_program(deployment.http, root, execution_id, {"name": "borrowed"})
    assert result["phase"] == "completed", result
    proofs = {key: json.loads(value) for key, value in result["result"]["proofs"].items()}
    assert set(proofs) == {"before", "first", "second", "third", "after"}
    assert len({proof["hostname"] for proof in proofs.values()}) == 1
    children = (await deployment.http.get(f"/api/executions/{execution_id}/children")).json()
    assert len(children) == 1
    for step, proof in proofs.items():
        deployment.backend.verify(proof)
        expected = execution_id if step in {"before", "after"} else children[0]["execution_id"]
        assert proof["context"]["execution_id"] == expected
        assert proof["context"]["root_execution_id"] == execution_id
        assert proof["environment_reused"] == (step != "before")
        assert proof["environment_first_step"] == "before"
    if deployment.replay is not None:
        for record in (result, children[0]):
            await deployment.replay(record["context"]["engine_handle"])
    await deployment.backend.assert_clean()


async def test_receiving_environment_loads_private_settings_outside_execution_payload(
    configured_remote,
):
    deployment = configured_remote
    node = resource("traced", category=ResourceCategory.NODE, type_key="platform_trace")
    graph = GraphDefinition(
        steps=(
            ElementStep(
                uid="traced", element=node.key, execution=ExecutionSelection(profile="remote")
            ),
        ),
        resources=(node,),
        entry="traced",
        exit="traced",
        inputs={"user_prompt": PathBinding(path=("name",))},
        outputs={"answer": PathBinding(path=("output",))},
    )
    reference = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="private-receiver",
            name="Private receiver",
            owner=Identity.user("owner"),
            implementation=graph,
        ),
    )
    encoded_key = base64.b64encode(f"{deployment.public}:{deployment.secret}".encode()).decode()
    assert deployment.secret not in deployment.target.model_dump_json()
    for name in ("first", "second"):
        record = await execute_program(deployment.http, reference, uuid4().hex, {"name": name})
        assert record["phase"] == "completed" and record["result"] == {"answer": name}, json.dumps(
            record.get("failure"), indent=2
        )
        if deployment.native:
            handle = deployment.native.get_workflow_handle(record["context"]["engine_handle"])
            history = await handle.fetch_history()
            assert (
                deployment.secret not in history.to_json() and encoded_key not in history.to_json()
            )
            await replay(deployment.native, deployment.worker, record["context"]["engine_handle"])
    assert len(deployment.collector.spans) == 10
    assert all(
        batch.authorization == "Basic " + encoded_key for batch in deployment.collector.batches
    )
    assert all(
        deployment.secret not in json.dumps(span_attributes(span))
        for span in deployment.collector.spans
    )
    for collection in await deployment.database.list_collection_names():
        async for document in deployment.database[collection].find({}):
            assert deployment.secret not in repr(document) and encoded_key not in repr(document)


async def test_child_owned_environment_is_released_while_parent_continues(deployed_remote):
    deployment = deployed_remote
    references = {}
    for name, implementation in (
        ("scoped-work", remote_graph(retained=True)),
        ("waiting", ApplicationDefinition(implementation="waiting", version="1")),
    ):
        references[name] = await publish_program(
            deployment.http,
            ProgramDefinition(
                program_id=name, name=name, owner=deployment.owner, implementation=implementation
            ),
        )
    root = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="continues-after-scope",
            name="Continues after scope",
            owner=deployment.owner,
            implementation=scoped_environment_graph(
                references["scoped-work"], references["waiting"]
            ),
        ),
    )
    execution_id = uuid4().hex
    submitted = await deployment.http.post(
        "/api/executions",
        json={
            "execution_id": execution_id,
            "program": root.model_dump(mode="json"),
            "inputs": {"name": "scoped"},
        },
    )
    assert submitted.status_code == 202, submitted.text
    try:
        async with asyncio.timeout(90):
            while True:
                response = await deployment.http.get(f"/api/executions/{execution_id}/children")
                assert response.status_code == 200, response.text
                children = response.json()
                waiting = next(
                    (child for child in children if child["program"]["program_id"] == "waiting"),
                    None,
                )
                if waiting is not None:
                    break
                await asyncio.sleep(0.1)
        await deployment.backend.assert_clean()
        parent = await deployment.http.get(f"/api/executions/{execution_id}")
        assert parent.json()["phase"] not in {"completed", "failed", "cancelled"}, parent.text
        delivered = await deployment.http.post(
            f"/api/executions/{waiting['execution_id']}/messages",
            json={"name": "answer", "data": "continued"},
        )
        assert delivered.status_code == 202, delivered.text
        result = await deployment.http.get(f"/api/executions/{execution_id}/result", timeout=180)
        assert result.json()["phase"] == "completed", result.text
        assert result.json()["result"]["answer"] == "continued"
        proofs = [json.loads(value) for value in result.json()["result"]["proofs"].values()]
        assert len(proofs) == 3 and len({proof["hostname"] for proof in proofs}) == 1
        assert sum(proof["environment_reused"] for proof in proofs) == 2
        assert {proof["environment_first_step"] for proof in proofs} == {"first"}
        for proof in proofs:
            deployment.backend.verify(proof)
        if deployment.replay is not None:
            for record in (result.json(), *children):
                await deployment.replay(record["context"]["engine_handle"])
    finally:
        await deployment.http.post(f"/api/executions/{execution_id}/cancel")
    await deployment.backend.assert_clean()
