"""
Tool for getting detailed node information.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from mas.application.agents.constants import ToolNames
from mas.application.ports.tool import BaseTool


class GetNodeCardArgs(BaseModel):
    """Arguments for getting a specific node's card."""

    uid: str = Field(..., description="UID of the node to inspect")


class GetNodeCardTool(BaseTool):
    """Get detailed information about a specific node."""

    name = ToolNames.TOPOLOGY_GET_NODE_CARD
    description = "Get detailed capability and skill information for a specific adjacent node"
    args_schema = GetNodeCardArgs

    def __init__(self, get_adjacent_nodes: Callable[[], dict[str, Any]]):
        self._get_adjacent_nodes = get_adjacent_nodes

    async def run(self, **kwargs) -> dict[str, Any]:
        """Get specific node card."""
        args = GetNodeCardArgs(**kwargs)
        adjacent_nodes = self._get_adjacent_nodes()

        if args.uid not in adjacent_nodes:
            return {"found": False, "error": f"Node {args.uid} is not adjacent or does not exist"}

        card = adjacent_nodes.get_card(args.uid)

        node_details = {
            "found": True,
            "uid": args.uid,
            "name": card.name,
            "type": card.type_key,
            "description": card.description,
            "capabilities": [cap.name for cap in card.capabilities] if card.capabilities else [],
            "skills": self._extract_skills(card.skills),
            "configuration": card.configuration if card.configuration else {},
        }

        return node_details

    def _extract_skills(self, skills: list) -> list[dict[str, str]]:
        """Extract skills in a structured format."""
        extracted = []
        for skill in skills:
            extracted.append({"name": skill.name, "description": skill.description or ""})
        return extracted
