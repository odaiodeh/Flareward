"""
Card builder input models.
"""

from pydantic import BaseModel, ConfigDict, Field

from mas.core.enums import ResourceCategory
from mas.domain.element_card import ElementCard


class SpecMetadata(BaseModel):
    """
    Static metadata extracted from ElementSpec.

    Avoids passing the spec class directly to prevent circular imports.
    """

    category: ResourceCategory
    type_key: str
    name: str
    description: str
    capability_names: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class CardBuildInput(BaseModel):
    """
    Everything a card builder needs to build an element card.

    Key principle: Builder receives CARDS of dependencies, not their configs.
    This maintains encapsulation - each element only knows its own config.

    Attributes:
        rid: Resource ID for this element
        name: User-defined name for this element
        config: This element's Pydantic config (the typed config model)
        spec_metadata: Static metadata from the element's spec
        dependency_cards: ElementCards of elements this element references.
                         Built in dependency order - leaves first, so these
                         cards are always available when building a parent.
    """

    rid: str = Field(..., description="Resource ID")
    name: str = Field(..., description="User-defined name")
    config: BaseModel = Field(..., description="This element's Pydantic config")
    spec_metadata: SpecMetadata = Field(..., description="Static metadata from spec")
    dependency_cards: dict[str, ElementCard] = Field(
        default_factory=dict, description="Map of rid -> ElementCard for each referenced element"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)
