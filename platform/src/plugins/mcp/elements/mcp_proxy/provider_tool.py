"""Select a provider-owned tool without owning its transport or credentials."""

from typing import Any

from lumora.elements.exceptions import PluginConfigurationError
from lumora.elements.ports.tool import BaseTool
from lumora.elements.ports.tool_provider import ToolProvider
from lumora.elements.tools.domain.models import ToolDefinition
from lumora.services.interactions.tools.models import ToolAccessMode


class ProviderTool(BaseTool):
    def __init__(self, name: str, provider: ToolProvider) -> None:
        self.name = name
        self.description = ""
        self.access_mode = ToolAccessMode.WRITE
        self._provider = provider
        self._tool: BaseTool | None = None

    async def prepare_element(self) -> None:
        if self._tool is not None:
            return
        tools = await self._provider.get_tools()
        matching = [tool for tool in tools if tool.name == self.name]
        if len(matching) != 1:
            raise PluginConfigurationError(
                f"Provider must expose exactly one tool named {self.name!r}",
                {"tool_name": self.name},
            )
        tool = matching[0]
        self.description = tool.description
        self.args_schema = tool.args_schema
        self.access_mode = tool.access_mode
        self._tool = tool

    def _prepared_tool(self) -> BaseTool:
        if self._tool is None:
            raise PluginConfigurationError(
                "Provider tool requires async element preparation",
                {"tool_name": self.name},
            )
        return self._tool

    def to_definition(self) -> ToolDefinition:
        self._prepared_tool()
        return super().to_definition()

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        return await self._prepared_tool().run(*args, **kwargs)
