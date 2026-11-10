from typing import Literal

from pydantic import Field

from lumora.elements.condition_config import BaseConditionConfig
from lumora.elements.hints import CardContext, CardHint
from plugins.routing.elements.router_boolean.identifiers import Identifier


class RouterBooleanConditionConfig(BaseConditionConfig):
    """
    Configuration for the router boolean condition that returns a configured boolean value.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
    boolean_value: bool = Field(
        True,
        description="The boolean value to return (true or false)",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
