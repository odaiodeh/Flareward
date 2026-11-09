from collections.abc import AsyncGenerator

from flareward.elements.messaging.domain.messages import ChatMessage, Role
from flareward.elements.ports.llm import BaseLLM
from flareward.elements.tools.domain.models import ToolDefinition


class MockLLM(BaseLLM):
    async def chat(self, messages: list[ChatMessage]) -> ChatMessage:
        last_content = messages[-1].content if messages else ""
        return ChatMessage(
            role=Role.ASSISTANT,
            content=f"[MOCK RESPONSE] Hello! You said: {last_content}",
        )

    async def stream(
        self, messages: list[ChatMessage], **call_params
    ) -> AsyncGenerator[str | ChatMessage]:
        response = await self.chat(messages)
        yield response.content

    def bind_tools(self, tools: list[ToolDefinition]) -> MockLLM:
        return MockLLM()

    @property
    def name(self) -> str:
        return "mock"
