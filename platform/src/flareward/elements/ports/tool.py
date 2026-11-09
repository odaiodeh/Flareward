from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from flareward.elements.tools.domain.models import ToolDefinition
from flareward.services.interactions.tools.models import ToolAccessMode


class BaseTool(ABC):
    """Abstract base class for all executable tools."""

    name: str
    description: str
    args_schema: type[BaseModel] | dict[str, Any] | None = None
    access_mode: ToolAccessMode = ToolAccessMode.READ

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool; adapters own any unavoidable blocking SDK work."""
        ...

    def get_args_schema_json(self) -> dict[str, Any] | None:
        """Return the JSON Schema dict for this tool's parameters."""
        if self.args_schema is None:
            return None
        if isinstance(self.args_schema, dict):
            return self.args_schema
        return self.args_schema.model_json_schema()

    def to_definition(self) -> ToolDefinition:
        """Extract a provider-agnostic ToolDefinition (schema only, no execution)."""
        return ToolDefinition(
            name=self.name,
            description=self.description or "",
            parameters=self.get_args_schema_json() or {"type": "object", "properties": {}},
        )
