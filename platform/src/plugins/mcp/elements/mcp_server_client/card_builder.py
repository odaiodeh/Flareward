"""
Card builder for MCP Provider.

Extracts tool_names from flareward.bootstrap.settings as skills.
"""

from flareward.elements.cards.interface import CardBuilder
from flareward.elements.cards.models import CardBuildInput
from flareward.elements.domain.cards import ElementCard, Skill


class McpProviderCardBuilder(CardBuilder):
    """
    MCP Provider builds its card with tools as skills.

    Tool names come from flareward.bootstrap.settings.tool_names (list of str).
    Each tool name becomes a skill.
    """

    def build(self, input: CardBuildInput) -> ElementCard:
        """Build card with tools from flareward.bootstrap.settings."""
        skills = self._extract_tools_as_skills(input.config)

        return ElementCard(
            uid=input.rid,
            category=input.spec_metadata.category,
            type_key=input.spec_metadata.type_key,
            name=input.name,
            description=input.spec_metadata.description,
            skills=skills,
            capabilities=[],
            configuration={},
            metadata=None,
        )

    def _extract_tools_as_skills(self, config) -> list[Skill]:
        """Extract tool_names from flareward.bootstrap.settings as skills."""
        skills: list[Skill] = []

        tool_names = config.tool_names
        if tool_names:
            for tool_name in tool_names:
                skills.append(Skill(name=tool_name))

        return skills
