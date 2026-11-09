from __future__ import annotations

import logging
from contextlib import aclosing
from typing import Any, ClassVar

from flareward.elements.instance_ports import SupportsStreaming
from flareward.elements.messaging.domain.messages import ChatMessage, Role
from flareward.elements.ports.llm import BaseLLM
from flareward.elements.ports.tool import BaseTool
from flareward.elements.tools.domain.models import ToolDefinition

logger = logging.getLogger(__name__)


class LlmCapableMixin[T: SupportsStreaming]:
    """Clean LLM capability mixin with streaming support."""

    MIXIN_READS: ClassVar[set[str]] = set()
    MIXIN_WRITES: ClassVar[set[str]] = set()

    def __init_subclass__(cls) -> None:
        """Verify that host class implements required streaming interface."""
        if not issubclass(cls, SupportsStreaming):
            raise TypeError(f"{cls.__name__} requires streaming support (_stream + is_streaming).")
        super().__init_subclass__()

    def __init__(
        self,
        *,
        llm: BaseLLM,
        system_message: str = "",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.llm = llm
        self.system_message = system_message

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def chat(
        self: T,
        messages: list[ChatMessage],
        tools: list[BaseTool] | None = None,
    ) -> ChatMessage:
        """Primary chat interface with optional dynamic tool binding."""
        definitions = self._tools_to_definitions(tools)
        llm_instance = self.llm.bind_tools(definitions)

        if self.is_streaming():
            return await self._stream_chat(messages, llm_instance)
        return await llm_instance.chat(messages)

    def bind_tools(self, tools: list[BaseTool]) -> None:
        """Permanently bind tools to this instance's LLM."""
        definitions = self._tools_to_definitions(tools)
        self.llm = self.llm.bind_tools(definitions)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _tools_to_definitions(tools: list[BaseTool] | None) -> list[ToolDefinition]:
        """Convert executable domain tools to schema-only definitions for the LLM."""
        if not tools:
            return []
        return [t.to_definition() for t in tools]

    async def _stream_chat(
        self: T,
        messages: list[ChatMessage],
        llm_instance: BaseLLM,
        *,
        event_type: str = "llm_token",
    ) -> ChatMessage:
        """Handle streaming chat with any LLM instance."""
        accumulated_text = ""
        final_message: ChatMessage | None = None

        async with aclosing(llm_instance.stream(messages)) as chunks:
            async for chunk in chunks:
                if isinstance(chunk, str):
                    accumulated_text += chunk
                    if self.is_streaming():
                        self._stream({"type": event_type, "chunk": chunk})
                elif isinstance(chunk, ChatMessage):
                    final_message = chunk
                    break
                else:
                    raise TypeError(f"LLM stream returned unexpected type: {type(chunk)}")
        return final_message or ChatMessage(
            role=Role.ASSISTANT,
            content=accumulated_text,
        )
