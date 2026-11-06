"""Author the shared agent scenario through the public API, with selectable model metadata."""

from functools import partial

import httpx
from mas.domain.execution.models import ExecutionRecord
from mas.domain.programs.models import PathBinding
from mas.graph.state.graph_state import GraphState
from mas.session.domain.session_record import SessionRecord

from support.agent_session import AgentRole, session_blueprint
from support.resource_http import create_resource


async def create_agent_session(
    http: httpx.AsyncClient,
    seed: str,
    *,
    profile: str = "thread",
    llm_type: str = "platform_session_llm",
    llm_config: dict | None = None,
    chat: bool = False,
) -> tuple[str, dict]:
    resource = partial(create_resource, http)

    leaf = await resource("tools", "platform_dependency", "Evidence data", {"value": seed})
    middle = await resource(
        "tools",
        "platform_dependency",
        "Shared source",
        {"value": "knowledge-base", "dependency": "$ref:" + leaf},
    )
    model = await resource("llms", llm_type, "Shared model", llm_config or {})
    agents = {}
    for role in AgentRole:
        tool = await resource(
            "tools",
            "platform_session_evidence",
            role.value + " tool",
            {"source": "$ref:" + middle, "role": role.value},
        )
        agents[role] = await resource(
            "nodes",
            "custom_agent_node",
            role.value,
            {
                "llm": "$ref:" + model,
                "tools": ["$ref:" + tool],
                "max_rounds": 4,
                "system_message": (
                    "Call your evidence tool once, then answer with its exact evidence token. "
                    "Include evidence from previous agent results and conversation when present."
                ),
            },
            execution={"profile": profile},
        )
    return await publish_agent_session(http, agents, resource_count=9, chat=chat)


async def publish_agent_session(http, agents, *, resource_count, chat=False):
    created = await http.post(
        "/api/blueprints",
        json={"spec": session_blueprint(agents[AgentRole.RESEARCH], agents[AgentRole.REVIEW])},
    )
    assert created.status_code == 201, created.text
    blueprint_id = created.json()["blueprint_id"]
    validated = await http.post(f"/api/blueprints/{blueprint_id}/validation", json={})
    assert validated.status_code == 200 and validated.json()["is_valid"], validated.text
    cards = await http.get(f"/api/blueprints/{blueprint_id}/cards")
    assert cards.status_code == 200 and len(cards.json()) == resource_count, cards.text
    if chat:
        session = await http.post(
            "/api/sessions/user.session.create", json={"blueprintId": blueprint_id}
        )
        assert session.status_code == 200, session.text
        session_id = session.json()
        record = await http.get(f"/api/sessions/{session_id}")
        reference = record.json()["program"]
        revision = await http.get(
            f"/api/programs/{reference['program_id']}/revisions/{reference['revision']}"
        )
        assert revision.status_code == 200, revision.text
        return session_id, revision.json()["definition"]
    imported = await http.put(
        "/api/programs/agent-session/blueprint", json={"blueprint_id": blueprint_id}
    )
    assert imported.status_code == 200, imported.text
    agents = [
        resource
        for resource in imported.json()["definition"]["implementation"]["resources"]
        if resource["type_key"] == "custom_agent_node"
    ]
    assert len(agents) == 2 and len({agent["config"]["llm"] for agent in agents}) == 1
    published = await http.post(
        "/api/programs/agent-session/revisions", json={"expected_version": 1}
    )
    assert published.status_code == 201, published.text
    bindings = {
        name: PathBinding(path=(name,)).model_dump(mode="json") for name in GraphState.model_fields
    }
    session = await http.post(
        "/api/sessions",
        json={
            "program": {"program_id": "agent-session", "revision": 1},
            "blueprint_id": blueprint_id,
            "input_bindings": bindings,
            "output_bindings": bindings,
        },
    )
    assert session.status_code == 201, session.text
    return session.json()["run_id"], imported.json()["definition"]


async def execute_agent_turn(
    http: httpx.AsyncClient, session_id: str, execution_id: str, prompt: str, *, chat: bool = False
) -> tuple[ExecutionRecord, SessionRecord]:
    started = (
        await http.post(
            "/api/sessions/user.session.submit",
            json={
                "sessionId": session_id,
                "executionId": execution_id,
                "inputs": {"user_prompt": prompt},
            },
        )
        if chat
        else await http.post(
            f"/api/sessions/{session_id}/executions",
            json={"execution_id": execution_id, "inputs": {"user_prompt": prompt}},
        )
    )
    assert started.status_code == 202, started.text
    result = await http.get(f"/api/executions/{execution_id}/result", timeout=180)
    assert result.status_code == 200 and result.json()["phase"] == "completed", result.text
    response = await http.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200, response.text
    children = await http.get(f"/api/executions/{execution_id}/children")
    assert children.status_code == 200 and children.json() == [], children.text
    if chat:
        projection = await http.get(
            "/api/sessions/session.chat.get", params={"sessionId": session_id}
        )
        assert projection.status_code == 200, projection.text
        assert projection.json()["output"] == response.json()["graph_state"]["output"]
        assert projection.json()["messages"] == response.json()["graph_state"]["messages"]
        assert projection.json()["status"] == "COMPLETED"
    return ExecutionRecord.model_validate(result.json()), SessionRecord.model_validate(
        response.json()
    )


async def create_mcp_agent_session(http, endpoint, *, profile):
    resource = partial(create_resource, http)
    provider = await resource("providers", "mcp_server", "MCP service", {"mcp_url": endpoint})
    tool = await resource(
        "tools",
        "mcp_proxy",
        "Selected remote tool",
        {"provider": "$ref:" + provider, "tool_name": "read_remote_evidence"},
    )
    model = await resource("llms", "platform_session_llm", "Shared model", {})
    agents = {}
    for role in AgentRole:
        agents[role] = await resource(
            "nodes",
            "custom_agent_node",
            role.value,
            {"llm": "$ref:" + model, "tools": ["$ref:" + tool], "max_rounds": 4},
            execution={"profile": profile},
        )
    return await publish_agent_session(http, agents, resource_count=7)
