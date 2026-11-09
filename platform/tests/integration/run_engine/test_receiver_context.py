"""Real dispatch binds receiver services and child identity without sending live clients."""

import json
from dataclasses import replace

import pytest
from runengine.core.refs import FunctionRef
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig
from support.receivers import ContextSpec, element_runtime
from support.scenarios import publish, resource

from flareward.executions.adapters.run_engine.outbound.compiler import ProgramCompiler
from flareward.executions.adapters.run_engine.outbound.gateway import RunEngineGateway
from flareward.executions.domain.models import ExecutionPhase
from flareward.executions.domain.preferences import ExecutionSelection
from flareward.executions.models import StartExecution
from flareward.executions.service import ExecutionService
from flareward.programs.domain.models import (
    ApplicationDefinition,
    ElementStep,
    GraphDefinition,
    PathBinding,
    ProgramCallStep,
)
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.identity.domain import Identity


@pytest.fixture
async def receiving(platform, application, monkeypatch, tmp_path):
    audit_file = tmp_path / "receiver.jsonl"
    monkeypatch.setenv("FLAREWARD_TEST_RECEIVER_AUDIT", str(audit_file))
    application.elements.register_spec_class(ContextSpec)
    compiler = ProgramCompiler(
        platform.programs,
        application.elements,
        application.applications,
        {"thread": ThreadRunnerConfig(), "process": ProcessRunnerConfig(max_workers=1)},
        "thread",
        receiver=FunctionRef.from_callable(element_runtime),
    )
    gateway = RunEngineGateway(platform.host, compiler)
    service = ExecutionService(platform.programs, platform.records, gateway)
    yield (
        replace(
            platform,
            compiler=compiler,
            gateway=gateway,
            executions=service,
            owner=Identity.team("team"),
        ),
        audit_file,
    )


def context_graph(profile):
    node = resource("context", category=ResourceCategory.NODE, type_key="receiver_context")
    return GraphDefinition(
        steps=(
            ElementStep(
                uid="context", element=node.key, execution=ExecutionSelection(profile=profile)
            ),
        ),
        resources=(node,),
        entry="context",
        exit="context",
        outputs={"answer": PathBinding(path=("output",))},
    )


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_receiver_constructs_services_with_actual_child_context(receiving, profile):
    platform, audit_file = receiving
    child = await publish(platform, "child-context", context_graph(profile))
    parent = await publish(
        platform,
        "parent-context",
        GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="child",
                    program=child.reference,
                    outputs={"output": PathBinding(path=("answer",))},
                ),
            ),
            entry="child",
            exit="child",
            outputs={"answer": PathBinding(path=("output",))},
        ),
    )
    record = await platform.executions.start(
        StartExecution(
            program=parent.reference,
            execution_id="public-root",
            session_id="session",
        ),
        platform.owner,
        credential_user_id="human-member",
    )
    result = await platform.executions.result(record.execution_id, platform.owner)
    assert result.phase == ExecutionPhase.COMPLETED
    received = json.loads(result.result["answer"])
    context = received["context"]
    assert context["execution_id"] == context["engine_handle"] != record.engine_handle
    assert context["parent_execution_id"] == context["root_execution_id"] == "public-root"
    assert context["session_id"] == "session"
    assert context["identity"]["id"] == "team"
    assert received["credential_user"] == "human-member"
    assert received["storage"] == "/receiver-owned" and received["approved"] is True
    children = await platform.executions.children(record.execution_id, platform.owner)
    assert len(children) == 1
    projected = children[0]
    assert projected.execution_id == context["execution_id"]
    assert projected.program == child.reference and projected.phase == ExecutionPhase.COMPLETED
    assert projected.parent_execution_id == record.execution_id
    assert projected.context.ancestor_execution_ids == (record.execution_id,)
    assert projected.session_id == "session" and projected.result == result.result
    status = await (await platform.host.get_handle(context["engine_handle"])).status()
    assert status.parent_run_id == record.engine_handle
    events = [json.loads(line) for line in audit_file.read_text().splitlines()]
    assert [event["event"] for event in events] == [
        "opened",
        "trace.session",
        "stream.complete",
        "trace.flushed",
        "channel.closed",
        "closed",
    ]
    assert {event["execution_id"] for event in events} == {context["execution_id"]}


async def test_application_child_then_graph_keeps_immediate_parent_and_root(receiving):
    platform, _ = receiving
    leaf = await publish(platform, "leaf", context_graph("thread"))
    middle = await publish(
        platform,
        "middle",
        ApplicationDefinition(
            implementation="composed",
            version="1",
            children={"greet": leaf.reference},
        ),
    )
    root = await publish(
        platform,
        "root",
        ApplicationDefinition(
            implementation="composed",
            version="1",
            children={"greet": middle.reference},
        ),
    )
    record = await platform.executions.start(
        StartExecution(
            program=root.reference,
            execution_id="root-id",
        ),
        platform.owner,
        credential_user_id="member",
    )
    result = await platform.executions.result(record.execution_id, platform.owner)
    context = json.loads(result.result["answer"])["context"]
    assert context["root_execution_id"] == "root-id"
    assert context["parent_execution_id"] not in {"root-id", context["execution_id"]}
    leaf_status = await (await platform.host.get_handle(context["engine_handle"])).status()
    assert leaf_status.parent_run_id == context["parent_execution_id"]
    children = await platform.executions.children(record.execution_id, platform.owner)
    grand = await platform.executions.children(children[0].execution_id, platform.owner)
    assert grand[0].execution_id == context["execution_id"]
    assert grand[0].context.ancestor_execution_ids == ("root-id", children[0].execution_id)
