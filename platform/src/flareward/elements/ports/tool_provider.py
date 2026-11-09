"""Application contract for adapters that discover executable tools."""

from collections.abc import Sequence
from typing import Protocol

from flareward.elements.ports.tool import BaseTool


class ToolProvider(Protocol):
    async def get_tools(self) -> Sequence[BaseTool]: ...
