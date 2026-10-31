"""Real async SDK transports preserve provider contracts and close owned streams."""

import asyncio
from contextlib import aclosing

import httpx
import pytest
from google.genai import types
from mas.domain.messages import ChatMessage, Role
from mas.domain.tools import ToolDefinition
from mas.elements.llms.common.errors import LLMProviderError
from mas.elements.llms.google_genai.google_genai import GoogleGenAILLM
from mas.elements.llms.openai.openai import OpenAILLM
from mas.elements.llms.openai_compatible.openai_compatible import OpenAICompatibleLLM
from support.llm_wire import LLMProtocol, ModelWire


@pytest.fixture(params=list(LLMProtocol))
async def model_case(request):
    wire = ModelWire(request.param)
    client = httpx.AsyncClient(transport=httpx.MockTransport(wire))
    if wire.protocol == LLMProtocol.GEMINI:
        model = GoogleGenAILLM(
            model_name="fixture",
            api_key="test-credential",
            http_options=types.HttpOptions(httpx_async_client=client),
        )
    else:
        implementation = (
            OpenAILLM if wire.protocol == LLMProtocol.RESPONSES else OpenAICompatibleLLM
        )
        model = implementation(
            base_url="https://model.invalid/v1",
            model_name="fixture",
            api_key="test-credential",
            http_client=client,
            max_retries=0,
        )
    try:
        yield model, wire, client
    finally:
        wire.release.set()
        await model.aclose()
        await client.aclose()


MESSAGES = [ChatMessage(role=Role.USER, content="Read evidence.")]


async def test_native_sdk_chat_and_bound_tool_response(model_case):
    model, wire, client = model_case
    assert (await model.chat(MESSAGES)).content == "hello world"
    wire.tool_call = True
    bound = model.bind_tools(
        [
            ToolDefinition(
                name="evidence",
                description="Read evidence",
                parameters={"type": "object"},
            )
        ]
    )
    result = await bound.chat(MESSAGES)
    assert result.tool_calls[0].name == "evidence"
    assert result.tool_calls[0].args == {"value": 7}
    await bound.aclose()
    assert not client.is_closed
    await model.aclose()
    # GenAI borrows injected HTTP clients; OpenAI closes the client it receives.
    assert client.is_closed is (wire.protocol != LLMProtocol.GEMINI)


async def test_native_sdk_stream_closes_after_completion(model_case):
    model, wire, _ = model_case
    chunks = [chunk async for chunk in model.stream(MESSAGES)]
    assert "".join(chunks) == "hello world"
    assert wire.streams[-1].closed


async def test_native_sdk_stream_closes_when_consumer_stops_early(model_case):
    model, wire, _ = model_case
    async with aclosing(model.stream(MESSAGES)) as chunks:
        assert await anext(chunks) == "hello "
    assert wire.streams[-1].closed


@pytest.mark.parametrize("streaming", [False, True])
async def test_provider_failure_is_sanitized_during_request_or_stream(model_case, streaming):
    model, wire, _ = model_case
    wire.fail = True
    with pytest.raises(LLMProviderError) as failure:
        if streaming:
            async with aclosing(model.stream(MESSAGES)) as chunks:
                async for _ in chunks:
                    pass
        else:
            await model.chat(MESSAGES)
    assert "private-provider-diagnostic" not in str(failure.value)
    assert "test-credential" not in str(failure.value)
    assert all(stream.closed for stream in wire.streams)


async def test_sdk_stream_cancellation_closes_response(model_case):
    model, wire, _ = model_case
    wire.pause = True

    async def consume():
        async with aclosing(model.stream(MESSAGES)) as chunks:
            async for _ in chunks:
                pass

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(wire.waiting.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert wire.streams[-1].closed
    finally:
        wire.release.set()
        await asyncio.gather(task, return_exceptions=True)
