"""
Default card builder for tools.

A tool represents itself as a single skill.
"""

from lumora.elements.cards.interface import CardBuilder
from lumora.elements.cards.models import CardBuildInput
from lumora.elements.domain.cards import ElementCard, Skill


class ToolCardBuilder(CardBuilder):
    """
    Tool builds its card with itself as a skill.

    Tools have no dependencies - they ARE the skill.
    """

    def build(self, input: CardBuildInput) -> ElementCard:
        """Build card with this tool as a skill."""
        skill = Skill(name=input.name, description=input.spec_metadata.description)

        return ElementCard(
            uid=input.rid,
            category=input.spec_metadata.category,
            type_key=input.spec_metadata.type_key,
            name=input.name,
            description=input.spec_metadata.description,
            skills=[skill],
            capabilities=[],
            configuration={},
            metadata=None,
        )
