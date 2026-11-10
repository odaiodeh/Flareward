"""
Card builder abstract base class.

Defines the contract for element card builders.
"""

from abc import ABC, abstractmethod

from lumora.elements.cards.models import CardBuildInput
from lumora.elements.domain.cards import ElementCard


class CardBuilder(ABC):
    """
    Abstract base class for element card builders.

    Each element type can implement its own card builder to customize
    how its ElementCard is constructed.

    Receives CardBuildInput with:
    - The element's own config (Pydantic model)
    - ElementCards of all dependencies (already built)

    The builder's responsibility:
    - Build skills from its own config and/or dependency cards
    - Build capabilities from its own config and/or dependency cards
    - Extract configuration (like system_message for agents)
    """

    @abstractmethod
    def build(self, input: CardBuildInput) -> ElementCard:
        """
        Build and return an ElementCard from the input data.

        Args:
            input: CardBuildInput containing:
                   - rid: this element's resource ID
                   - name: user-defined name
                   - config: this element's Pydantic config
                   - spec_metadata: static spec info
                   - dependency_cards: cards of referenced elements

        Returns:
            ElementCard describing this element
        """
        ...
