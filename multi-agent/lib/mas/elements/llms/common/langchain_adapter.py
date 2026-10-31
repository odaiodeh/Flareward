"""
Adapter that presents any domain ``BaseLLM`` as a LangChain ``BaseChatModel``.

This lets LangChain-based systems (Deep Agents, LangGraph, chains) use
any of our LLM implementations transparently::

    from deepagents import create_deep_agent

    adapter = BaseLLMChatModelAdapter(llm=my_openai_llm)
    agent   = create_deep_agent(model=adapter, tools=[...])

The adapter delegates all work to the underlying ``BaseLLM`` and converts
between LangChain message types and domain ``ChatMessage`` objects using
the existing ``LangChainConverter``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import aclosing
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import BaseTool as LangChainBaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict

from mas.domain.messages import ChatMessage
from mas.domain.tools import ToolDefinition

from ..common.chat.converter import LangChainConverter

_EMPTY_PARAMS: dict[str, Any] = {"type": "object", "properties": {}}


def _lc_tool_to_definition(
    tool: dict[str, Any] | type | Callable | LangChainBaseTool,
) -> ToolDefinition:
    """Convert any LangChain-accepted tool format to a provider-agnostic ``ToolDefinition``."""
    openai_schema = convert_to_openai_tool(tool)
    func = openai_schema.get("function", openai_schema)
    return ToolDefinition(
        name=func["name"],
        description=func.get("description", ""),
        parameters=func.get("parameters", _EMPTY_PARAMS),
    )


class BaseLLMChatModelAdapter(BaseChatModel):
    """Wraps any domain ``BaseLLM`` as a LangChain ``BaseChatModel``.

    This enables usage with LangChain agents, LangGraph, Deep Agents,
    and any other LangChain-based system that expects a ``BaseChatModel``.

    Example::

        adapter = BaseLLMChatModelAdapter(llm=OpenAILLM(...))
        result  = adapter.invoke([HumanMessage(content="Hello")])
    """

    llm: Any

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ------------------------------------------------------------------
    # Required overrides
    # ------------------------------------------------------------------

    @property
    def _llm_type(self) -> str:
        return f"unifai-{self.llm.name}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("Use the asynchronous LLM adapter interface")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        domain_msgs = LangChainConverter.from_lc(messages)
        result = await self.llm.chat(domain_msgs)
        ai_message = LangChainConverter.to_lc_message(result)
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    # ------------------------------------------------------------------
    # Optional: streaming
    # ------------------------------------------------------------------

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        domain_msgs = LangChainConverter.from_lc(messages)
        async with aclosing(self.llm.stream(domain_msgs)) as chunks:
            async for token_or_msg in chunks:
                if isinstance(token_or_msg, str):
                    yield ChatGenerationChunk(
                        message=AIMessageChunk(content=token_or_msg),
                    )
                elif isinstance(token_or_msg, ChatMessage):
                    yield ChatGenerationChunk(
                        message=LangChainConverter.to_lc_message_chunk(token_or_msg),
                    )

    # ------------------------------------------------------------------
    # Optional: tool binding
    # ------------------------------------------------------------------

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | LangChainBaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> BaseLLMChatModelAdapter:
        """Bind LangChain-format tools to the underlying domain ``BaseLLM``.

        Converts each tool to a ``ToolDefinition`` via ``convert_to_openai_tool``,
        delegates to ``BaseLLM.bind_tools()``, and returns a new adapter
        wrapping the tool-bound LLM.
        """
        definitions: list[ToolDefinition] = [_lc_tool_to_definition(t) for t in tools]
        bound_llm = self.llm.bind_tools(definitions)
        return BaseLLMChatModelAdapter(llm=bound_llm)
