"""Frozen source preparation binds new occurrences without recompiling pinned work."""

import pytest
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig
from support.scenarios import echo_graph, publish

from flareward.executions.adapters.run_engine.outbound.compiler import ProgramCompiler
from flareward.executions.adapters.run_engine.outbound.gateway import RunEngineGateway
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.models import PreparedExecution, StartExecution
from flareward.programs.domain.models import ApplicationDefinition
from flareward.services.identity.domain import Identity


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_frozen_graph_accepts_distinct_inputs_without_adopting_new_revision(
    platform, profile
):
    revision = await publish(platform, "template", echo_graph(profile))
    template = await platform.gateway.prepare(
        revision, {}, ExecutionContext(identity=platform.owner), ""
    )
    await publish(
        platform, "template", ApplicationDefinition(implementation="greeting", version="1")
    )
    for name in ("first", "second"):
        record = await platform.executions.start(
            StartExecution(program=revision.reference, inputs={"name": name}),
            platform.owner,
            prepared_template=template,
        )
        result = await platform.executions.result(record.execution_id, platform.owner)
        assert result.phase == "completed", result.failure
        assert result.result == {"answer": "greeting:" + name}
        assert result.program == revision.reference


async def test_frozen_template_refuses_other_owner_or_changed_profile_policy(platform, application):
    revision = await publish(platform, "template", echo_graph())
    template = await platform.gateway.prepare(
        revision, {}, ExecutionContext(identity=platform.owner), ""
    )
    with pytest.raises(PermissionError):
        await platform.gateway.bind(
            template,
            revision,
            {"name": "forged"},
            ExecutionContext(identity=Identity.user("foreign")),
            "native",
        )
    changed = RunEngineGateway(
        platform.host,
        ProgramCompiler(
            application.programs,
            application.elements,
            application.applications,
            {"thread": ThreadRunnerConfig(), "process": ProcessRunnerConfig(max_workers=2)},
            "thread",
        ),
        location=platform.gateway.location,
    )
    with pytest.raises(PermissionError, match="no longer permitted"):
        await changed.bind(
            template,
            revision,
            {"name": "changed"},
            ExecutionContext(identity=platform.owner),
            "native",
        )


async def test_invalid_private_snapshot_does_not_expose_adapter_data(platform):
    revision = await publish(platform, "invalid-template", echo_graph())
    template = await platform.gateway.prepare(
        revision, {}, ExecutionContext(identity=platform.owner), ""
    )
    marker = "private-execution-configuration"
    malformed = template.model_copy(
        update={"payload_json": '{"invalid":"' + marker + '"}', "content_digest": ""}
    )
    with pytest.raises(ValueError, match="snapshot is invalid") as error:
        await platform.gateway.bind(
            malformed, revision, {}, ExecutionContext(identity=platform.owner), "native"
        )
    assert marker not in str(error.value)


async def test_frozen_summary_tracks_compiled_graph_and_rejects_tampering(platform):
    revision = await publish(platform, "placement-template", echo_graph("process"))
    context = ExecutionContext(identity=platform.owner)
    template = await platform.gateway.prepare(revision, {}, context, "")
    summary = template.placement
    assert summary.program == revision.reference
    assert not summary.dynamic_invocations
    assert summary.invocations[0].step_uid == "echo"
    assert summary.invocations[0].profile == "process"
    await publish(platform, "placement-template", echo_graph("thread"))
    bound = await platform.gateway.bind(template, revision, {"name": "first"}, context, "root")
    assert bound.placement == summary
    data = template.model_dump(mode="json")
    data["placement"]["invocations"][0]["profile"] = "thread"
    data["content_digest"] = ""
    forged = PreparedExecution.model_validate(data)
    with pytest.raises(ValueError, match="placement differs"):
        await platform.gateway.bind(forged, revision, {}, context, "root")
