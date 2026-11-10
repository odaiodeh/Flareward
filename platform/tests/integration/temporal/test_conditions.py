"""Real condition factories and conditional rejoins run on durable workers and replay."""

import asyncio

import pytest
from support.condition_scenarios import routing_graph
from support.scenarios import publish
from support.temporal import replay, worker_process

from lumora.executions.domain.models import ExecutionPhase
from lumora.executions.models import StartExecution


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize(
    ("type_key", "config", "value", "recipients", "branches", "selected"),
    [
        (
            "threshold",
            {"input_path": ["nodes_output", "score"], "threshold": 0.5},
            "0.75",
            (),
            None,
            {"yes"},
        ),
        ("threshold", {"input_path": ["output"], "threshold": 0.5}, "0.25", (), None, {"no"}),
        (
            "router_direct",
            {},
            "0",
            ("yes", "no"),
            {"yes": "yes", "no": "no", "END": "finish"},
            {"yes", "no"},
        ),
    ],
    ids=["exclusive-yes", "exclusive-no", "selected-fanout"],
)
async def test_conditional_rejoins_on_separate_worker_and_replay(
    durable,
    application,
    condition_elements,
    tmp_path,
    profile,
    type_key,
    config,
    value,
    recipients,
    branches,
    selected,
):
    revision = await publish(
        application,
        "durable-condition",
        routing_graph(
            type_key, config, profile=profile, value=value, recipients=recipients, branches=branches
        ),
    )
    settings = durable.settings.model_copy(update={"element_modules": ("support.conditions",)})
    async with worker_process(settings, tmp_path / "condition-worker.log"):
        record = await durable.executions.start(
            StartExecution(program=revision.reference, inputs={}), application.owner
        )
        async with asyncio.timeout(30):
            result = await durable.executions.result(record.execution_id, application.owner)
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        assert set(result.result["steps"]) == {"score", "finish", *selected}
        visits = [message["content"] for message in result.result["visits"]]
        assert visits[0] == "score" and visits[-1] == "finish"
        assert len(visits) == len(set(visits)) == len(selected) + 2
    # Replay outside the original worker lifetime, using the same preload/namespace.
    await replay(durable.client, settings, record.engine_handle)
