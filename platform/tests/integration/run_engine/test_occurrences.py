"""Real native calls and graph retries produce authorized payload-free observations."""

import httpx
import pytest
from support.operations import operation_bundle, operation_graph
from support.scenarios import publish, run

from lumora.api.app import create_app
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import CustomCoordinatorDefinition, OperationStep
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("custom", [False, True])
async def test_graph_and_custom_operation_occurrences_are_safe_and_authorized(
    platform, application, profile, custom
):
    definition = (
        CustomCoordinatorDefinition(
            implementation="typed_operation",
            version="1",
            config={"bundle": operation_bundle(application.elements).model_dump(mode="json")},
        )
        if custom
        else operation_graph(profile)
    )
    revision = await publish(platform, "observed", definition)
    result = await run(platform, revision, {"name": "private-work-value"})
    assert result.phase == "completed", result.failure

    async def authenticate(request):
        return (
            Identity.user("other") if request.headers.get("x-owner") == "other" else platform.owner
        )

    app = create_app(platform.programs, platform.executions, authenticate)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        response = await http.get(
            f"/api/executions/{result.execution_id}/occurrences", params={"limit": 1}
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "private, no-store"
        page = response.json()
        assert "private-work-value" not in response.text
        assert page["total"] == 1 and not page["truncated"]
        call = page["occurrences"][0]
        assert call["call_site"] == "typed-work" and call["kind"] == "operation"
        assert call["status"] == "completed" and call["attempt"] == 1
        denied = await http.get(
            f"/api/executions/{result.execution_id}/occurrences", headers={"x-owner": "other"}
        )
        assert denied.status_code == 403
        assert (
            await http.get(
                f"/api/executions/{result.execution_id}/occurrences", params={"limit": 101}
            )
        ).status_code == 422


async def test_graph_retries_are_distinct_recorded_attempts(platform):
    graph = operation_graph()
    step = OperationStep.model_validate(
        {
            **graph.steps[0].model_dump(mode="json"),
            "max_attempts": 2,
        }
    )
    revision = await publish(
        platform,
        "retry",
        graph.model_copy(
            update={
                "steps": (step,),
                "resources": tuple(
                    resource.model_copy(update={"config": {**resource.config, "fail": True}})
                    if resource.key.rid == "middle"
                    else resource
                    for resource in graph.resources
                ),
            }
        ),
    )
    result = await run(platform, revision, {"name": "private-work-value"})
    assert result.phase == "failed"
    page = await platform.executions.observation(result.execution_id, platform.owner, limit=1)
    assert page.total == 2 and page.next_cursor == 2
    assert page.occurrences[0].attempt == 2 and page.occurrences[0].status == "failed"
    previous = await platform.executions.observation(
        result.execution_id, platform.owner, before=page.next_cursor
    )
    assert [call.attempt for call in previous.occurrences] == [1]
    assert "private" not in page.model_dump_json()


async def test_contract_failure_is_observed_without_inventing_a_retry(platform):
    graph = operation_graph()
    step = graph.steps[0].model_copy(
        update={"inputs": {"text": PathBinding(path=("input", "text"))}, "max_attempts": 2}
    )
    revision = await publish(
        platform, "contract-failure", graph.model_copy(update={"steps": (step,)})
    )
    result = await run(platform, revision, {"text": {"private": "invalid"}})
    assert result.phase == "failed"
    page = await platform.executions.observation(result.execution_id, platform.owner)
    assert page.total == 1
    assert page.occurrences[0].status == "failed" and page.occurrences[0].attempt == 1
