from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from mas.domain.messages import ChatMessage
from mas.domain.tools import ToolDefinition


class BaseLLM(ABC):
    """Abstract base class for all LLM integrations (OpenAI, Google GenAI, etc.)."""

    @abstractmethod
    async def chat(self, messages: list[ChatMessage]) -> ChatMessage:
        """Perform a single conversational completion and return the full response."""
        ...

    @abstractmethod
    def stream(
        self, messages: list[ChatMessage], **call_params: Any
    ) -> AsyncGenerator[str | ChatMessage]:
        """Stream conversational completion with real-time token generation."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier for the LLM (for logging/debug)."""
        ...

    @abstractmethod
    def bind_tools(self, tools: list[ToolDefinition]) -> BaseLLM:
        """Bind tool schemas to the LLM for function-calling."""
        ...
