"""Actual Redis + native FastAPI + thread/process receiver integration."""

import asyncio
import json
import os
from uuid import uuid4

import httpx
import pytest
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.invocation.config import ProcessRunnerConfig, ThreadRunnerConfig
from support.elements import element_registry
from support.interaction_http import pending
from support.scenarios import resource

from flareward.api.app import create_app
from flareward.bootstrap.platform import compose_platform
from flareward.bootstrap.settings.platform_settings import PlatformSettings
from flareward.executions.domain.preferences import ExecutionSelection
from flareward.programs.domain.models import (
    ApplicationDefinition,
    ElementStep,
    GraphDefinition,
    PathBinding,
    ProgramCallStep,
    ProgramDefinition,
)
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.connections.adapters.redis import owned_redis
from flareward.services.identity.domain import Identity
from flareward.services.interactions.adapters.redis_store import RedisInteractionStore
from flareward.services.interactions.adapters.wire import root_key
from flareward.services.interactions.rules import ApprovalRuleChange
from flareward.services.interactions.tools.models import ApprovalOverrides


@pytest.fixture
async def interacting(monkeypatch):
    uri = os.environ.get("FLAREWARD_TEST_REDIS_URI")
    if not uri:
        pytest.skip("Set FLAREWARD_TEST_REDIS_URI for actual cross-process interaction contracts")
    monkeypatch.setenv("FLAREWARD_REDIS_URI", uri)
    monkeypatch.setenv("FLAREWARD_APPROVAL_TIMEOUT", "30")
    async with owned_redis(uri, decode_responses=True) as client:
        await client.ping()
        roots = []
        settings = PlatformSettings(
            host=LocalHostConfig(),
            storage="memory",
            authentication="development",
            development_user="owner",
            redis_uri=uri,
            interactions="redis",
            reconcile_interval=0.05,
            application_modules=("support.programs",),
            execution_profiles={
                "thread": ThreadRunnerConfig(),
                "process": ProcessRunnerConfig(max_workers=1),
            },
            default_execution_profile="thread",
        )
        app = create_app(
            services_factory=lambda: compose_platform(settings, elements=element_registry())
        )
        try:
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app), base_url="http://platform"
                ) as http:
                    try:
                        yield http, app.state.platform, roots
                    finally:
                        store = RedisInteractionStore(client)
                        for root in roots:
                            await store.cancel(root)
        finally:
            for root in roots:
                keys = [key async for key in client.scan_iter(match=root_key(root) + ":*")]
                if keys:
                    await client.delete(*keys)


def approval_graph(profile, requests=1, *, request_prefix="probe"):
    node = resource(
        "probe",
        category=ResourceCategory.NODE,
        type_key="platform_approval",
        config={"requests": requests, "request_prefix": request_prefix},
    )
    return GraphDefinition(
        steps=(
            ElementStep(
                uid="probe", element=node.key, execution=ExecutionSelection(profile=profile)
            ),
        ),
        resources=(node,),
        entry="probe",
        exit="probe",
        outputs={"answer": PathBinding(path=("output",))},
    )


async def publish_interaction(case, profile="thread", *, requests=1, child=False):
    http, _, _ = case
    program_id = "program-" + uuid4().hex
    definition = ProgramDefinition(
        program_id=program_id,
        name="Interaction",
        owner=Identity.user("owner"),
        implementation=approval_graph(profile, requests),
    )
    assert (
        await http.put(
            f"/api/programs/{program_id}",
            json={"definition": definition.model_dump(mode="json"), "expected_version": 0},
        )
    ).status_code == 200
    revision = await http.post(
        f"/api/programs/{program_id}/revisions", json={"expected_version": 1}
    )
    reference = {"program_id": program_id, "revision": revision.json()["revision"]}
    if child:
        parent = ProgramDefinition(
            program_id=program_id + "-parent",
            name="Parent",
            owner=Identity.user("owner"),
            implementation=GraphDefinition(
                steps=(
                    ProgramCallStep(
                        uid="child",
                        program=reference,
                        outputs={"output": PathBinding(path=("answer",))},
                    ),
                ),
                entry="child",
                exit="child",
                outputs={"answer": PathBinding(path=("output",))},
            ),
        )
        await http.put(
            f"/api/programs/{parent.program_id}",
            json={"definition": parent.model_dump(mode="json"), "expected_version": 0},
        )
        await http.post(
            f"/api/programs/{parent.program_id}/revisions", json={"expected_version": 1}
        )
        reference = {"program_id": parent.program_id, "revision": 1}
    return reference


async def submit(case, profile="thread", *, requests=1, child=False):
    http, _, roots = case
    reference = await publish_interaction(case, profile, requests=requests, child=child)
    root = "interaction-" + uuid4().hex
    roots.append(root)
    response = await http.post("/api/executions", json={"program": reference, "execution_id": root})
    assert response.status_code == 202, response.text
    return root


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_chat_streams_pin_each_turn_and_approvals_use_native_interactions(
    interacting, profile
):
    http, _, roots = interacting
    reference = await publish_interaction(interacting, profile)
    created = await http.post(
        "/api/sessions",
        json={
            "program": reference,
            "output_bindings": {"output": {"kind": "path", "path": ["answer"]}},
        },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["run_id"]
    root = "chat-stream-" + uuid4().hex
    roots.append(root)
    started = await http.post(
        "/api/sessions/user.session.submit",
        json={"sessionId": session_id, "executionId": root, "inputs": {}},
    )
    assert started.status_code == 202, started.text
    ticket = await pending(http, root)
    missing_execution = await http.post(
        "/api/sessions/session.approval",
        json={
            "sessionId": session_id,
            "requestId": ticket["request"]["request_id"],
            "decision": "approve",
        },
    )
    assert missing_execution.status_code == 422, missing_execution.text
    status = await http.get("/api/sessions/session.stream.status", params={"sessionId": session_id})
    assert status.status_code == 200 and status.json()["is_active"], status.text
    assert status.json()["execution_id"] == root and status.json()["event_count"] is None
    assert (
        await http.delete("/api/sessions/session.delete", params={"sessionId": session_id})
    ).status_code == 409
    approved = await http.post(
        "/api/sessions/session.approval",
        json={
            "sessionId": session_id,
            "executionId": root,
            "requestId": ticket["request"]["request_id"],
            "decision": "approve",
            "modifiedArgs": {},
        },
    )
    assert approved.status_code == 200 and approved.json()["status"] == "submitted", approved.text
    assert (await http.get(f"/api/executions/{root}/result")).json()["phase"] == "completed"
    stream = await http.get(
        "/api/sessions/session.subscribe", params={"sessionId": session_id, "executionId": root}
    )
    assert stream.status_code == 200, stream.text
    events = [json.loads(line) for line in stream.text.splitlines()]
    assert events[-1]["type"] == "stream_end" and events[-1]["execution_id"] == root
    assert {event["type"] for event in events} >= {"approval_required", "fixture_step", "complete"}
    cursors = [event["cursor"] for event in events if "cursor" in event]
    replay = await http.get(
        "/api/sessions/session.subscribe",
        params={"sessionId": session_id, "executionId": root, "after": cursors[-1]},
    )
    assert [json.loads(line)["type"] for line in replay.text.splitlines()] == ["stream_end"]
    second = "chat-stream-" + uuid4().hex
    roots.append(second)
    assert (
        await http.post(
            "/api/sessions/user.session.submit",
            json={"sessionId": session_id, "executionId": second, "inputs": {}},
        )
    ).status_code == 202
    second_ticket = await pending(http, second)
    assert second_ticket["request"]["request_id"] == ticket["request"]["request_id"]
    stale_decision = await http.post(
        "/api/sessions/session.approval",
        json={
            "sessionId": session_id,
            "executionId": root,
            "requestId": ticket["request"]["request_id"],
            "decision": "approve",
        },
    )
    assert stale_decision.status_code == 409, stale_decision.text
    assert (await pending(http, second))["request"] == second_ticket["request"]
    # A stale subscription must not silently follow the new turn.
    stale = await http.get(
        "/api/sessions/session.subscribe", params={"sessionId": session_id, "executionId": root}
    )
    assert stale.status_code == 409, stale.text
    cancel = await http.post("/api/sessions/session.cancel", json={"sessionId": session_id})
    assert cancel.status_code == 202, cancel.text
    async with asyncio.timeout(5):
        result = await http.get(f"/api/executions/{second}/result")
    assert result.json()["phase"] in {"completed", "cancelled"}, result.text
    assert (
        await http.delete("/api/sessions/session.delete", params={"sessionId": session_id})
    ).status_code == 200


async def test_rule_revision_fences_delayed_updates_and_preserves_execution_replacement(
    interacting,
):
    _, _, roots = interacting
    root = "rule-revision-" + uuid4().hex
    roots.append(root)
    baseline = ApprovalOverrides()
    newest = ApprovalRuleChange(action="auto_approve", tool_name="newest").apply(baseline)
    delayed = ApprovalRuleChange(action="auto_reject", tool_name="delayed").apply(baseline)
    per_execution = ApprovalRuleChange(action="auto_reject", node_uid="local").apply(baseline)
    async with owned_redis(os.environ["FLAREWARD_TEST_REDIS_URI"], decode_responses=True) as client:
        store = RedisInteractionStore(client)
        await store.save_rules(root, newest, revision=2)
        await store.save_rules(root, delayed, revision=1)
        assert await store.load_rules(root) == newest
        # Canonical execution-only replacement must survive same-version reconciliation.
        await store.save_rules(root, per_execution)
        await store.save_rules(root, newest, revision=2)
        assert await store.load_rules(root) == per_execution
        await store.save_rules(root, newest, revision=3)
        assert await store.load_rules(root) == newest
        key = root_key(root) + ":rules"
        raw = json.loads(await client.get(key))
        assert raw["global_rules"]["auto_reject_tools"] == []
        assert raw["_session_revision"] == 3
        assert "_session_revision" not in (await store.load_rules(root)).to_dict()
        assert 0 < await client.ttl(key) <= 86400


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_session_rules_survive_turns_and_child_events_keep_root_identity(
    interacting, profile
):
    http, services, roots = interacting
    reference = await publish_interaction(interacting, profile, requests=2, child=True)
    created = await http.post(
        "/api/sessions",
        json={
            "program": reference,
            "output_bindings": {"output": {"kind": "path", "path": ["answer"]}},
        },
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["run_id"]

    async def start_turn():
        root = "session-rules-" + uuid4().hex
        roots.append(root)
        response = await http.post(
            "/api/sessions/user.session.submit",
            json={"sessionId": session_id, "executionId": root, "inputs": {}},
        )
        assert response.status_code == 202, response.text
        return root

    root = await start_turn()
    ticket = await pending(http, root)
    assert ticket["execution_id"] != root
    changed = await http.post(
        "/api/sessions/session.approval.rule",
        json={
            "sessionId": session_id,
            "executionId": root,
            "action": "auto_approve",
            "nodeUid": "probe",
            "toolName": "fixture-write",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["overrides"]["node_rules"]["probe"]["auto_approve_tools"] == [
        "fixture-write"
    ]
    assert (await pending(http, root))["request"] == ticket["request"]
    # Losing the live cache does not erase the durable session default.
    async with owned_redis(os.environ["FLAREWARD_TEST_REDIS_URI"], decode_responses=True) as client:
        await client.delete(root_key(root) + ":rules")
        await services.sessions.reconcile_pending()
        restored = await RedisInteractionStore(client).load_rules(root)
        assert restored.node_rules["probe"].auto_approve_tools == {"fixture-write"}
    approved = await http.post(
        "/api/sessions/session.approval",
        json={
            "sessionId": session_id,
            "executionId": root,
            "requestId": ticket["request"]["request_id"],
            "decision": "approve",
        },
    )
    assert approved.status_code == 200 and approved.json()["executionId"] == root, approved.text
    result = await http.get(f"/api/executions/{root}/result")
    assert result.json()["phase"] == "completed", result.text
    assert json.loads(result.json()["result"]["answer"])["decisions"] == ["approve", "approve"]
    events = await http.get(
        "/api/sessions/session.subscribe", params={"sessionId": session_id, "executionId": root}
    )
    assert events.status_code == 200, events.text
    approvals = [
        event
        for line in events.text.splitlines()
        if (event := json.loads(line))["type"] in {"approval_required", "approval_resolved"}
    ]
    assert {event["type"] for event in approvals} == {"approval_required", "approval_resolved"}
    assert all(event["root_execution_id"] == root for event in approvals)
    assert all(event["execution_id"] == ticket["execution_id"] for event in approvals)
    second = await start_turn()
    inherited = await http.get(f"/api/executions/{second}/result")
    assert inherited.json()["phase"] == "completed", inherited.text
    assert json.loads(inherited.json()["result"]["answer"])["decisions"] == ["approve", "approve"]
    # The metadata editor can clear defaults between executions.
    meta = (await http.get("/api/sessions/session.meta", params={"sessionId": session_id})).json()[
        "meta"
    ]
    meta["hitl_overrides"] = ApprovalOverrides().to_dict()
    cleared = await http.post(
        "/api/sessions/session.meta", json={"sessionId": session_id, "meta": meta}
    )
    assert cleared.status_code == 200, cleared.text
    rules = await http.get("/api/sessions/session.approval.rules", params={"sessionId": session_id})
    assert rules.json()["overrides"] == ApprovalOverrides().to_dict()
    third = await start_turn()
    third_ticket = await pending(http, third)
    rejected = await http.post(
        "/api/sessions/session.approval",
        json={
            "sessionId": session_id,
            "executionId": third,
            "requestId": third_ticket["request"]["request_id"],
            "decision": "reject",
        },
    )
    assert rejected.status_code == 200, rejected.text
    final = await http.get(f"/api/executions/{third}/result")
    assert final.json()["phase"] == "completed", final.text
    assert json.loads(final.json()["result"]["answer"])["decisions"] == ["reject"]


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_approval_and_stream_replay_across_actual_invocation_boundary(interacting, profile):
    http, _, _ = interacting
    root = await submit(interacting, profile, child=True)
    ticket = await pending(http, root)
    assert ticket["execution_id"] != root
    response = {"decision": "approve", "feedback": "reviewed"}
    endpoint = f"/api/executions/{root}/approvals/{ticket['request']['request_id']}"
    assert (await http.post(endpoint, json=response)).status_code == 202
    result = await http.get(f"/api/executions/{root}/result")
    assert result.json()["phase"] == "completed", result.text
    output = json.loads(result.json()["result"]["answer"])
    assert output["decisions"] == ["approve"]
    assert output["execution_id"] == ticket["execution_id"]
    assert output["credential_user"] == "owner"
    assert (await http.post(endpoint, json=response)).status_code == 202
    assert (await http.post(endpoint, json={"decision": "reject"})).status_code == 409
    replay = await http.get(f"/api/executions/{root}/stream")
    assert replay.status_code == 200
    events = [
        json.loads(line[6:]) for line in replay.text.splitlines() if line.startswith("data: ")
    ]
    assert {event["data"]["type"] for event in events} >= {
        "approval_required",
        "fixture_step",
        "complete",
    }
    assert {event["execution_id"] for event in events} == {ticket["execution_id"]}
    after = await http.get(f"/api/executions/{root}/stream", params={"after": events[-1]["cursor"]})
    assert after.text == ""


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_cancel_releases_worker_waiting_for_human_decision(interacting, profile):
    http, _, _ = interacting
    root = await submit(interacting, profile)
    ticket = await pending(http, root)
    assert (await http.post(f"/api/executions/{root}/cancel")).status_code == 202
    async with asyncio.timeout(5):
        result = await http.get(f"/api/executions/{root}/result")
    assert result.json()["phase"] in {"cancelled", "completed"}, result.text
    if result.json()["phase"] == "completed":
        assert json.loads(result.json()["result"]["answer"])["decisions"] == ["reject"]
    assert (await http.get(f"/api/executions/{root}/approvals")).json() == []
    rejected = await http.post(
        f"/api/executions/{root}/approvals/{ticket['request']['request_id']}",
        json={"decision": "approve"},
    )
    assert rejected.status_code == 409


async def test_conflicting_approval_decisions_are_atomic(interacting):
    http, _, _ = interacting
    root = await submit(interacting)
    ticket = await pending(http, root)
    endpoint = f"/api/executions/{root}/approvals/{ticket['request']['request_id']}"
    results = await asyncio.gather(
        http.post(endpoint, json={"decision": "approve"}),
        http.post(endpoint, json={"decision": "reject"}),
    )
    assert sorted(response.status_code for response in results) == [202, 409]
    result = await http.get(f"/api/executions/{root}/result")
    decisions = json.loads(result.json()["result"]["answer"])["decisions"]
    winner = "approve" if results[0].status_code == 202 else "reject"
    assert decisions == [winner]


async def test_approval_access_is_owner_scoped_before_read_or_submission(interacting):
    http, services, _ = interacting
    root = await submit(interacting)
    await pending(http, root)

    async def another_owner(request):
        return Identity.user("another-owner")

    app = create_app(
        services.programs, services.executions, another_owner, interactions=services.interactions
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as other:
        assert (await other.get(f"/api/executions/{root}/approvals")).status_code == 403
        assert (await other.get(f"/api/executions/{root}/stream")).status_code == 403
        assert (
            await other.post(
                f"/api/executions/{root}/approvals/probe-0", json={"decision": "approve"}
            )
        ).status_code == 403
    assert (await http.post(f"/api/executions/{root}/cancel")).status_code == 202


async def test_live_rule_update_is_seen_by_the_next_tool_request(interacting):
    http, _, _ = interacting
    root = await submit(interacting, requests=2)
    ticket = await pending(http, root)
    rules = {"global_rules": {"auto_approve_tools": ["fixture-write"]}}
    assert (await http.put(f"/api/executions/{root}/approval-rules", json=rules)).status_code == 200
    assert (
        await http.post(
            f"/api/executions/{root}/approvals/{ticket['request']['request_id']}",
            json={"decision": "approve"},
        )
    ).status_code == 202
    result = await http.get(f"/api/executions/{root}/result")
    assert json.loads(result.json()["result"]["answer"])["decisions"] == ["approve", "approve"]
    stream = await http.get(f"/api/executions/{root}/stream")
    events = [
        json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")
    ]
    assert sum(event["data"]["type"] == "approval_required" for event in events) == 1
    assert sum(event["data"]["type"] == "approval_resolved" for event in events) == 1


async def test_unanswered_approval_times_out_to_rejection(interacting, monkeypatch):
    http, _, _ = interacting
    monkeypatch.setenv("FLAREWARD_APPROVAL_TIMEOUT", "0.2")
    root = await submit(interacting)
    async with asyncio.timeout(5):
        result = await http.get(f"/api/executions/{root}/result")
    assert result.json()["phase"] == "completed", result.text
    assert json.loads(result.json()["result"]["answer"])["decisions"] == ["reject"]
    assert (await http.get(f"/api/executions/{root}/approvals")).json() == []
    assert (
        await http.post(f"/api/executions/{root}/approvals/probe-0", json={"decision": "approve"})
    ).status_code == 409


async def test_session_rules_are_snapshotted_and_seeded_before_receiver_requests(interacting):
    http, services, roots = interacting
    program_id = "rules-" + uuid4().hex
    definition = ProgramDefinition(
        program_id=program_id,
        name="Session rules",
        owner=Identity.user("owner"),
        implementation=approval_graph("thread"),
    )
    await services.programs.save(definition, Identity.user("owner"))
    revision = await services.programs.publish(
        program_id,
        Identity.user("owner"),
        expected_version=(
            await services.programs.draft(program_id, Identity.user("owner"))
        ).version,
    )
    created = await http.post(
        "/api/sessions",
        json={
            "program": revision.reference.model_dump(mode="json"),
            "metadata": {
                "hitl_enabled": True,
                "hitl_overrides": {"global_rules": {"approve_all": True}},
            },
        },
    )
    assert created.status_code == 201, created.text
    root = "session-rule-" + uuid4().hex
    roots.append(root)
    submitted = await http.post(
        f"/api/sessions/{created.json()['run_id']}/executions", json={"execution_id": root}
    )
    assert submitted.status_code == 202, submitted.text
    result = await http.get(f"/api/executions/{root}/result")
    assert json.loads(result.json()["result"]["answer"])["decisions"] == ["approve"]
    assert (await http.get(f"/api/executions/{root}/approval-rules")).json()["global_rules"][
        "approve_all"
    ] is True


async def test_trimmed_stream_cursor_is_explicitly_rejected(interacting):
    http, _, _ = interacting
    root = await submit(interacting)
    await pending(http, root)
    await http.post(f"/api/executions/{root}/approvals/probe-0", json={"decision": "approve"})
    await http.get(f"/api/executions/{root}/result")
    original = await http.get(f"/api/executions/{root}/stream")
    cursors = [line[4:] for line in original.text.splitlines() if line.startswith("id: ")]
    async with owned_redis(os.environ["FLAREWARD_TEST_REDIS_URI"], decode_responses=True) as client:
        await client.xtrim(root_key(root) + ":events", maxlen=1, approximate=False)
    stale = await http.get(f"/api/executions/{root}/stream", params={"after": cursors[0]})
    assert stale.status_code == 409


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("cancel_inside", [False, True])
async def test_cancelling_child_subtree_preserves_waiting_sibling(
    interacting, profile, cancel_inside
):
    http, services, roots = interacting
    owner = Identity.user("owner")
    revisions = {}
    for name in ("left", "right"):
        definition = ProgramDefinition(
            program_id=name,
            name=name,
            owner=owner,
            implementation=approval_graph(profile, request_prefix=name),
        )
        await services.programs.save(definition, owner)
        revisions[name] = (
            await services.programs.publish(
                name, owner, expected_version=(await services.programs.draft(name, owner)).version
            )
        ).reference
    # The cancelled child is itself a program that calls another program. Its
    # grandchild's process wait must see the ancestor cancellation fence.
    middle = ProgramDefinition(
        program_id="middle",
        name="middle",
        owner=owner,
        implementation=ApplicationDefinition(
            implementation="composed", version="1", children={"greet": revisions["left"]}
        ),
    )
    await services.programs.save(middle, owner)
    revisions["left"] = (
        await services.programs.publish(
            "middle",
            owner,
            expected_version=(await services.programs.draft("middle", owner)).version,
        )
    ).reference
    parent = ProgramDefinition(
        program_id="parallel",
        name="parallel",
        owner=owner,
        implementation=ApplicationDefinition(
            implementation="parallel_waiting", version="1", children=revisions
        ),
    )
    await services.programs.save(parent, owner)
    revision = await services.programs.publish(
        "parallel",
        owner,
        expected_version=(await services.programs.draft("parallel", owner)).version,
    )
    root = "scoped-" + uuid4().hex
    roots.append(root)
    response = await http.post(
        "/api/executions",
        json={
            "program": revision.reference.model_dump(mode="json"),
            "execution_id": root,
            "inputs": {"cancel_inside": cancel_inside},
        },
    )
    assert response.status_code == 202, response.text
    async with asyncio.timeout(10):
        while True:
            tickets = (await http.get(f"/api/executions/{root}/approvals")).json()
            children = (await http.get(f"/api/executions/{root}/children")).json()
            if len(tickets) == len(children) == 2:
                break
            await asyncio.sleep(0.02)
    left = next(child for child in children if child["program"]["program_id"] == "middle")
    right = next(child for child in children if child["program"]["program_id"] == "right")
    if cancel_inside:
        response = await http.post(
            f"/api/executions/{root}/messages", json={"name": "cancel_left", "data": True}
        )
    else:
        response = await http.post(f"/api/executions/{left['execution_id']}/cancel")
    assert response.status_code == 202, response.text
    async with asyncio.timeout(5):
        await http.get(f"/api/executions/{left['execution_id']}/result")
        remaining = (await http.get(f"/api/executions/{root}/approvals")).json()
    assert [ticket["request"]["request_id"] for ticket in remaining] == ["right-0"]
    assert (await http.get(f"/api/executions/{root}")).json()["phase"] == "running"
    assert (await http.get(f"/api/executions/{right['execution_id']}")).json()["phase"] == "running"
    decision = await http.post(
        f"/api/executions/{root}/approvals/right-0", json={"decision": "approve"}
    )
    assert decision.status_code == 202, decision.text
    completed = await http.get(f"/api/executions/{right['execution_id']}/result")
    assert json.loads(completed.json()["result"]["answer"])["decisions"] == ["approve"]
    await http.post(f"/api/executions/{root}/messages", json={"name": "answer", "data": "finished"})
    assert (await http.get(f"/api/executions/{root}/result")).json()["phase"] == "completed"
