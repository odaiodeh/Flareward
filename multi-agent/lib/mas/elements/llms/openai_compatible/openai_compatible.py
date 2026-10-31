"""
OpenAI-compatible LLM implementation using the Chat Completions API.

Works with any server implementing the ``/v1/chat/completions`` endpoint:
vLLM, LocalAI, Ollama, Azure OpenAI, and older OpenAI models (GPT-4, GPT-3.5).

For newer OpenAI models (GPT-5+) that require the Responses API, use the
``openai`` provider instead.
"""

from __future__ import annotations

import copy
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionToolParam

from mas.application.ports.llm import BaseLLM
from mas.core.tracing import NoOpTracingService, TracingService
from mas.domain.messages import ChatMessage, Role
from mas.domain.tools import ToolDefinition

from ..common.errors import provider_errors
from ..common.name_sanitizer import build_name_maps, map_name
from ..common.tool_name_restorer import restore_tool_names
from .message_converter import OpenAIMessageConverter
from .stream_aggregator import StreamToolCallAggregator
from .tools_converter import OpenAIToolsConverter


class OpenAICompatibleLLM(BaseLLM):
    """LLM client for any OpenAI-compatible Chat Completions API.

    Responsibilities are split across dedicated collaborators:

    * **OpenAIMessageConverter** – bidirectional ``ChatMessage`` ↔ OpenAI dict
    * **OpenAIToolsConverter** – ``ToolDefinition`` → Chat Completions tool schema
    * **StreamToolCallAggregator** – reassembles incremental tool-call deltas

    Tool names containing dots (e.g. ``time.get_current_time``) are
    sanitized to underscores at the API boundary and restored on
    inbound tool calls.  Converters remain unaware of sanitization.
    """

    def __init__(
        self,
        base_url: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        api_key: str = "EMPTY",
        tracing: TracingService = None,
        **extra: Any,
    ) -> None:
        self._name = "openai_compatible"
        self._model = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._tools: list[ChatCompletionToolParam] | None = None
        self._fwd_names: dict[str, str] = {}
        self._rev_names: dict[str, str] = {}
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, **extra)
        self._tracing = tracing or NoOpTracingService()
        self._owns_client = True

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    async def chat(self, messages: list[ChatMessage]) -> ChatMessage:
        raw_messages = OpenAIMessageConverter.to_openai(messages)
        self._sanitize_outbound_names(raw_messages)

        with (
            self._tracing.trace_llm(
                model=self._model,
                provider="openai_compatible",
                input_messages=[
                    {"role": m.role.value, "content": m.content} for m in messages[-5:]
                ],
            ) as gen,
            provider_errors(gen, self.name),
        ):
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=raw_messages,
                temperature=self._temperature,
                max_completion_tokens=self._max_tokens,
                tools=self._tools or [],
            )
            result_msg = OpenAIMessageConverter.from_openai(
                response.choices[0].message,
            )
            result_msg = restore_tool_names(self._rev_names, result_msg)
            usage = {}
            if response.usage:
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            gen.update(output=result_msg.content, usage_details=usage or None)
        return result_msg

    async def stream(
        self,
        messages: list[ChatMessage],
        **call_params: Any,
    ) -> AsyncGenerator[str | ChatMessage]:
        raw_messages = OpenAIMessageConverter.to_openai(messages)
        self._sanitize_outbound_names(raw_messages)
        aggregator = StreamToolCallAggregator()
        accumulated_content = ""

        with (
            self._tracing.trace_llm(
                model=self._model,
                provider="openai_compatible",
                input_messages=[
                    {"role": m.role.value, "content": m.content} for m in messages[-5:]
                ],
                metadata={"streaming": True},
            ) as gen,
            provider_errors(gen, self.name),
        ):
            stream_iter = await self._client.chat.completions.create(
                model=self._model,
                messages=raw_messages,
                temperature=self._temperature,
                max_completion_tokens=self._max_tokens,
                tools=self._tools or [],
                stream=True,
                **call_params,
            )
            async with stream_iter:
                async for chunk in stream_iter:
                    if not chunk.choices:
                        if hasattr(chunk, "usage") and chunk.usage:
                            gen.update(
                                usage_details={
                                    "input_tokens": chunk.usage.prompt_tokens,
                                    "output_tokens": chunk.usage.completion_tokens,
                                    "total_tokens": chunk.usage.total_tokens,
                                }
                            )
                        continue
                    delta = chunk.choices[0].delta
                    if delta.content:
                        accumulated_content += delta.content
                        yield delta.content
                    if delta.tool_calls:
                        aggregator.absorb(delta.tool_calls)
            gen.update(output=accumulated_content)

        if aggregator.has_tool_calls:
            tool_calls = aggregator.build()
            result = ChatMessage(
                role=Role.ASSISTANT,
                content=accumulated_content,
                tool_calls=tool_calls,
            )
            yield restore_tool_names(self._rev_names, result)

    async def aclose(self) -> None:
        if self._owns_client:
            self._owns_client = False
            await self._client.close()

    def bind_tools(self, tools: list[ToolDefinition]) -> OpenAICompatibleLLM:
        clone = copy.copy(self)
        clone._owns_client = False
        clone._fwd_names, clone._rev_names = build_name_maps(t.name for t in tools)
        clone._tools = OpenAIToolsConverter.to_openai(tools)
        self._sanitize_tool_defs(clone._tools, clone._fwd_names)
        return clone

    @property
    def name(self) -> str:
        return self._name

    # ------------------------------------------------------------------
    # Name sanitization
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_tool_defs(
        tools: list[ChatCompletionToolParam] | None,
        fwd_names: dict[str, str],
    ) -> None:
        """Sanitize function names inside Chat Completions tool defs (in-place)."""
        if not tools:
            return
        for tool in tools:
            name = tool["function"]["name"]
            tool["function"]["name"] = map_name(name, fwd_names)

    def _sanitize_outbound_names(self, messages: list[dict[str, Any]]) -> None:
        """Sanitize tool-call names in outbound messages (in-place)."""
        for msg in messages:
            for tc in msg.get("tool_calls", []):
                name = tc["function"]["name"]
                tc["function"]["name"] = map_name(name, self._fwd_names)
