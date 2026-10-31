"""
Default card builder for retrievers.

A retriever represents itself as a capability.
"""

from mas.application.elements.cards.interface import CardBuilder
from mas.application.elements.cards.models import CardBuildInput
from mas.domain.element_card import Capability, ElementCard


class RetrieverCardBuilder(CardBuilder):
    """
    Retriever builds its card with itself as a capability.

    Retrievers provide retrieval capabilities, not skills.
    """

    def build(self, input: CardBuildInput) -> ElementCard:
        """Build card with this retriever as a capability."""
        capability = Capability(name=input.name, description=input.spec_metadata.description)

        return ElementCard(
            uid=input.rid,
            category=input.spec_metadata.category,
            type_key=input.spec_metadata.type_key,
            name=input.name,
            description=input.spec_metadata.description,
            skills=[],
            capabilities=[capability],
            configuration={},
            metadata=None,
        )
