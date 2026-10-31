"""Real HTTP clients close during successful, failed and cancelled action probes."""

import asyncio

import httpx
import pytest
from a2a.types import AgentCapabilities, AgentCard
from mas.application.actions.contracts import ActionContext
from mas.application.actions.service import ActionsService
from mas.core.identity import Identity
from outbound.actions.providers.a2a.get_agent_card.get_agent_card import GetAgentCardAction
from outbound.actions.providers.a2a.validate_connection.validate_connection import (
    ValidateConnectionAction,
)
from outbound.actions.providers.rag.client import RagActionClient
from outbound.actions.providers.rag.get_available_tags.get_available_tags import (
    GetAvailableTagsAction,
)


@pytest.mark.parametrize("kind", ["a2a-card", "a2a-connection", "rag-tags"])
@pytest.mark.parametrize("outcome", ["success", "failure", "cancel"])
async def test_action_clients_close_and_outputs_remain_portable(monkeypatch, kind, outcome):
    entered = asyncio.Event()
    clients = []
    client_type = httpx.AsyncClient
    card = AgentCard(
        name="Protocol",
        description="Fixture",
        url="http://provider",
        version="1",
        capabilities=AgentCapabilities(),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[],
    )

    async def protocol(request):
        entered.set()
        if outcome == "failure":
            return httpx.Response(500, text="private-provider-token")
        if outcome == "cancel":
            await asyncio.Future()
        data = (
            {"options": [{"label": "tag", "value": "tag"}]}
            if kind == "rag-tags"
            else card.model_dump(mode="json", by_alias=True)
        )
        return httpx.Response(200, json=data)

    def client(**kwargs):
        result = client_type(transport=httpx.MockTransport(protocol), **kwargs)
        clients.append(result)
        return result

    monkeypatch.setattr(httpx, "AsyncClient", client)
    action = {
        "a2a-card": GetAgentCardAction(),
        "a2a-connection": ValidateConnectionAction(),
        "rag-tags": GetAvailableTagsAction(RagActionClient("http://provider")),
    }[kind]
    service = ActionsService((action,))
    context = ActionContext(owner=Identity.team("team"), credential_user_id="alice")
    task = asyncio.create_task(
        service.execute(action.uid, {"base_url": "http://provider"}, context)
    )
    await asyncio.wait_for(entered.wait(), 3)
    if outcome == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        result = await task
        assert result.success == (outcome == "success"), result
        assert "private-provider-token" not in result.model_dump_json()
        if kind == "a2a-card" and result.success:
            assert isinstance(result.agent_card, dict)
    assert clients and all(item.is_closed for item in clients)


async def test_concurrent_rag_actions_keep_authenticated_headers_separate(monkeypatch):
    client_type = httpx.AsyncClient
    clients = []

    async def protocol(request):
        actor = request.headers["X-Authenticated-User"]
        await asyncio.sleep(0)
        return httpx.Response(200, json={"options": [{"label": actor, "value": actor}]})

    def client(**kwargs):
        result = client_type(transport=httpx.MockTransport(protocol), **kwargs)
        clients.append(result)
        return result

    monkeypatch.setattr(httpx, "AsyncClient", client)
    service = ActionsService((GetAvailableTagsAction(RagActionClient("http://provider")),))
    results = await asyncio.gather(
        *(
            service.execute(
                "rag.get_available_tags",
                {"user_id": "forged"},
                ActionContext(
                    owner=Identity.team("shared"),
                    credential_user_id=actor,
                ),
            )
            for actor in ("alice", "bob")
        )
    )
    assert [result.tags for result in results] == [["alice"], ["bob"]]
    assert all(item.is_closed for item in clients)
