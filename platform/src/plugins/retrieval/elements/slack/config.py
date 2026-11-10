from typing import Literal

from pydantic import Field, HttpUrl

from lumora.elements.hints import CardContext, CardHint
from lumora.elements.retrieval.base_config import BaseRetrieverConfig

from .identifiers import Identifier


class SlackRetrieverConfig(BaseRetrieverConfig):
    """
    Retrieves messages from Slack via an API endpoint.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
    api_url: HttpUrl = Field(description="URL of the configured external Slack query API")
    top_k_results: int = Field(
        3,
        ge=1,
        description="Number of top Slack messages to return",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
    threshold: float = Field(
        0.3, ge=0.0, le=1.0, description="Minimum relevance score to include a message"
    )
