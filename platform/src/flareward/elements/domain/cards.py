"""
Element card and related models.

Skill and Capability use extra='allow' to accept additional fields
from external sources (like A2A AgentSkill).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from flareward.resources.domain.categories import ResourceCategory


class Skill(BaseModel):
    """
    A skill represents what an element CAN DO.

    Examples: git_status tool, file_read tool, send_slack_message

    Uses extra='allow' to preserve additional fields from external sources
    like A2A AgentSkill (which has id, examples, tags, input_modes, etc.)
    """

    name: str = Field(..., description="Skill name")
    description: str = Field(default="", description="What this skill does")

    model_config = ConfigDict(frozen=True, extra="allow")


class Capability(BaseModel):
    """
    A capability represents what an element IS CAPABLE OF.

    Examples: document_retrieval, code_analysis, web_search
    Capabilities are semantic abilities, not specific tools.

    Uses extra='allow' to preserve additional fields from external sources.
    """

    name: str = Field(..., description="Capability name")
    description: str = Field(default="", description="What this capability enables")

    model_config = ConfigDict(frozen=True, extra="allow")


class ElementCard(BaseModel):
    """
    Element card: Describes what an element is and what it can do.

    Used for:
    - UI display (resource details, blueprint view)
    - Node context (adjacent nodes in RTGraphPlan)
    - LLM understanding (agent knows about available nodes/tools)
    """

    uid: str = Field(..., description="Unique identifier")
    category: ResourceCategory = Field(..., description="Element category")
    type_key: str = Field(..., description="Element type key")
    name: str = Field(..., description="User-defined name")
    description: str = Field(default="", description="Element description")
    skills: list[Skill] = Field(default_factory=list, description="Skills (tools, actions)")
    capabilities: list[Capability] = Field(default_factory=list, description="Capabilities")
    configuration: dict[str, Any] = Field(default_factory=dict, description="Element configuration")
    metadata: Any | None = Field(default=None, description="Step metadata")

    model_config = ConfigDict(frozen=True)

    def _format_extra_fields(self, model: BaseModel, exclude: set = None) -> list[str]:
        """Format extra fields from a model with extra='allow'."""
        exclude = exclude or {"name", "description"}
        extra_lines = []

        data = model.model_dump()
        for key, value in data.items():
            if key in exclude or value is None:
                continue
            if isinstance(value, list) and value:
                extra_lines.append(f"      {key}: {value}")
            elif isinstance(value, dict) and value:
                extra_lines.append(f"      {key}: {value}")
            elif not isinstance(value, (list, dict)):
                extra_lines.append(f"      {key}: {value}")

        return extra_lines

    def __str__(self) -> str:
        """Clean, LLM-friendly representation with full details."""
        lines = [f"Name: {self.name}", f"UID: {self.uid}"]

        if self.description:
            lines.append(f"Description: {self.description}")

        if self.capabilities:
            lines.append("Capabilities:")
            for cap in self.capabilities:
                cap_data = cap.model_dump()
                value = cap_data.get("value")
                if value is not None:
                    lines.append(f"  - {cap.name}: {value}")
                elif cap.description:
                    lines.append(f"  - {cap.name}: {cap.description}")
                else:
                    lines.append(f"  - {cap.name}")
                lines.extend(
                    self._format_extra_fields(cap, exclude={"name", "description", "value"})
                )

        if self.skills:
            lines.append("Skills:")
            for skill in self.skills:
                if skill.description:
                    lines.append(f"  - {skill.name}: {skill.description}")
                else:
                    lines.append(f"  - {skill.name}")
                lines.extend(self._format_extra_fields(skill))

        if self.configuration:
            lines.append("Configuration:")
            for key, value in self.configuration.items():
                if isinstance(value, str):
                    lines.append(f'  {key}: "{value}"')
                else:
                    lines.append(f"  {key}: {value}")

        return "\n".join(lines)
