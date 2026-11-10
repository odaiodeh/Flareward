"""Query identity and immutable message context survive native async retrieval."""

import asyncio

import httpx
import pytest
from global_utils.constants import INTERNAL_AUTH_HEADER

from lumora.elements.behaviors.retriever_capable import RetrieverCapableMixin
from lumora.elements.messaging.domain.messages import ChatMessage, Role
from lumora.executions.domain.context import ExecutionContext
from lumora.services.identity.domain import Identity
from plugins.mas.elements.builtin.retriever import RetrieverTool
from plugins.retrieval.elements.slack.slack_retriever import SlackRetriever


@pytest.fixture
async def retrieval_case():
    loop = asyncio.get_running_loop()
    requests = []

    async def respond(request):
        assert asyncio.get_running_loop() is loop
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "search_results": [
                    {"content": "included", "score": 0.9},
                    {"content": "excluded", "score": 0.1},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        retriever = SlackRetriever(
            api_url="https://retrieval.invalid/query",
            top_k_results=4,
            threshold=0.5,
            identity=ExecutionContext(identity=Identity.user("member")),
            client=client,
        )
        yield retriever, client, requests
        await retriever.aclose()


async def test_retrieval_tool_awaits_identity_scoped_query_and_filters_results(retrieval_case):
    retriever, client, requests = retrieval_case
    result = await RetrieverTool(retriever).run(query="evidence")
    assert result == [{"content": "included", "score": 0.9}]
    assert requests[0].url.params["query"] == "evidence"
    assert requests[0].url.params["top_k_results"] == "4"
    assert requests[0].headers[INTERNAL_AUTH_HEADER] == "member"
    await retriever.aclose()
    assert not client.is_closed


async def test_retrieval_augmentation_preserves_message_metadata(retrieval_case):
    retriever, _, _ = retrieval_case
    original = ChatMessage(
        role=Role.USER,
        content="evidence",
        sender_id="sender",
        metadata={"artifact": "kept"},
    )
    result = await RetrieverCapableMixin(retriever=retriever).augment_with_context(original)
    assert "included" in result.content and "excluded" not in result.content
    assert original.content == "evidence"
    assert result.sender_id == original.sender_id
    assert result.metadata == original.metadata
