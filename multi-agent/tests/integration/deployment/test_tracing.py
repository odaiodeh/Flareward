"""Actual API/worker processes export receiver observations over OTLP HTTP."""

import asyncio
import os
from contextlib import AsyncExitStack
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import (
    ApplicationDefinition,
    ElementStep,
    GraphDefinition,
    PathBinding,
    ProgramDefinition,
)
from pydantic import SecretStr
from runengine.adapters.coordination.config import LocalHostConfig, TemporalHostConfig
from support.http_programs import publish_program
from support.scenarios import resource
from support.server import api_process
from support.telemetry import span_attributes, trace_collector
from support.temporal import replay, worker_process
from temporalio.client import Client

from config.platform_settings import PlatformSettings
from config.worker_settings import WorkerSettings


@pytest.fixture
async def traced_deployment(deployment_host, secret_settings, tmp_path):
    endpoint = os.environ.get("UNIFAI_TEST_TEMPORAL_ENDPOINT")
    if deployment_host == "temporal" and not endpoint:
        pytest.skip("Set the Temporal endpoint for durable tracing deployment contracts")
    async with trace_collector() as collector, AsyncExitStack() as owned:
        settings = PlatformSettings.model_validate(
            {
                **secret_settings.model_dump(mode="python"),
                "host": LocalHostConfig()
                if deployment_host == "local"
                else TemporalHostConfig(
                    endpoint=endpoint,
                    task_queue="unifai-tracing-" + uuid4().hex,
                ),
                "tracing": "langfuse",
                "langfuse_base_url": collector.base_url,
                "langfuse_public_key": SecretStr("trace-public"),
                "langfuse_secret_key": SecretStr("trace-private"),
                "tracing_timeout": 1,
                "element_modules": ("support.tracing_elements",),
                "application_modules": ("support.programs",),
            }
        )
        native, worker = None, None
        if deployment_host == "temporal":
            worker = WorkerSettings.model_validate(settings.model_dump(mode="python"))
            await owned.enter_async_context(worker_process(worker, tmp_path / "worker.log"))
            native = await Client.connect(endpoint)
        http = await owned.enter_async_context(api_process(settings, tmp_path / "api.log"))
        yield SimpleNamespace(http=http, collector=collector, native=native, worker=worker)


def traced_graph(profile, *, fail=False):
    node = resource(
        "traced", category=ResourceCategory.NODE, type_key="platform_trace", config={"fail": fail}
    )
    return GraphDefinition(
        steps=(
            ElementStep(
                uid="traced", element=node.key, execution=ExecutionSelection(profile=profile)
            ),
        ),
        resources=(node,),
        entry="traced",
        exit="traced",
        inputs={"user_prompt": PathBinding(path=("name",))},
        outputs={"answer": PathBinding(path=("output",))},
    )


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_composed_concurrent_executions_export_correct_session_and_child_identity(
    traced_deployment, profile
):
    deployment = traced_deployment
    leaf = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="traced-leaf",
            name="Traced leaf",
            owner=Identity.user("owner"),
            implementation=traced_graph(profile),
        ),
    )
    parent = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="traced-parent",
            name="Traced application",
            owner=Identity.user("owner"),
            implementation=ApplicationDefinition(
                implementation="composed", version="1", children={"greet": leaf}
            ),
        ),
    )

    async def execute(name):
        response = await deployment.http.post(
            "/api/executions",
            json={
                "program": parent.model_dump(mode="json"),
                "execution_id": name,
                "session_id": "session-" + name,
                "inputs": {"name": name},
            },
        )
        assert response.status_code == 202, response.text
        result = await deployment.http.get(f"/api/executions/{name}/result", timeout=30)
        assert result.status_code == 200 and result.json()["result"] == {"answer": name}, (
            result.text
        )
        children = await deployment.http.get(f"/api/executions/{name}/children")
        child = children.json()[0]
        if deployment.native:
            await replay(
                deployment.native, deployment.worker, result.json()["context"]["engine_handle"]
            )
            await replay(deployment.native, deployment.worker, child["context"]["engine_handle"])
        return name, child["execution_id"]

    executions = dict(await asyncio.gather(execute("one"), execute("two")))
    spans = deployment.collector.spans
    assert len(spans) == 10
    for name, child_id in executions.items():
        own = [span for span in spans if span_attributes(span)["session.id"] == "session-" + name]
        assert len(own) == 5
        assert {span_attributes(span)["langfuse.trace.metadata.execution_id"] for span in own} == {
            child_id
        }
        assert {
            span_attributes(span)["langfuse.trace.metadata.root_execution_id"] for span in own
        } == {name}
        assert {
            span_attributes(span)["langfuse.trace.metadata.parent_execution_id"] for span in own
        } == {name}
        assert {span_attributes(span)["user.id"] for span in own} == {"owner"}
        assert {span.trace_id.hex() for span in own} == {
            sha256(("session-" + name).encode()).hexdigest()[:32]
        }
        root = next(span for span in own if span.name == "session:session-" + name)
        assert not root.parent_span_id
        node = next(span for span in own if span.name == "traced")
        assert node.parent_span_id == root.span_id
    assert all(b"trace-private" not in span.SerializeToString() for span in spans)


async def test_failed_element_exports_classified_error_without_exception_secret(traced_deployment):
    deployment = traced_deployment
    reference = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="trace-failure",
            name="Trace failure",
            owner=Identity.user("owner"),
            implementation=traced_graph("thread", fail=True),
        ),
    )
    response = await deployment.http.post(
        "/api/executions",
        json={
            "program": reference.model_dump(mode="json"),
            "execution_id": "failed-trace",
            "inputs": {"name": "failure"},
        },
    )
    assert response.status_code == 202, response.text
    result = await deployment.http.get("/api/executions/failed-trace/result", timeout=30)
    assert result.json()["phase"] == "failed" and result.json()["failure"]["kind"] == "application"
    spans = deployment.collector.spans
    assert len(spans) == 5
    errors = [span for span in spans if span.status.code == 2]
    assert len(errors) == 4
    assert all(b"must-not-appear-in-trace" not in span.SerializeToString() for span in spans)
    assert all(not span.events for span in spans)


async def test_unavailable_collector_does_not_change_a_successful_program_result(traced_deployment):
    deployment = traced_deployment
    deployment.collector.response_status = 503
    reference = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="trace-outage",
            name="Collector outage",
            owner=Identity.user("owner"),
            implementation=traced_graph("thread"),
        ),
    )
    submitted = await deployment.http.post(
        "/api/executions",
        json={
            "program": reference.model_dump(mode="json"),
            "execution_id": "collector-outage",
            "inputs": {"name": "completed despite telemetry failure"},
        },
    )
    assert submitted.status_code == 202, submitted.text
    result = await deployment.http.get("/api/executions/collector-outage/result", timeout=30)
    assert result.status_code == 200 and result.json()["phase"] == "completed", result.text
    assert result.json()["result"] == {"answer": "completed despite telemetry failure"}
    assert deployment.collector.batches
