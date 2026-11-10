from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Extra, Field

from lumora.elements.hints import CardContext, CardHint, SecretHint
from plugins.gemini.elements.google_genai.identifiers import Identifier


class GoogleGenAIConfig(BaseModel):
    """Configuration for Google Generative AI (Gemini) API."""

    type: Literal[Identifier.TYPE] = Identifier.TYPE

    model_name: str = Field(
        default="gemini-3.5-flash",
        description="The Gemini model ID to use (e.g., gemini-3.5-flash, gemini-2.5-pro)",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )

    api_key: str = Field(
        default="",
        description="Google API key for Generative AI",
        # No ReadOnlyHint(read_only=False) here — the API key is set once by
        # whoever creates the LLM resource and is never overridden per-user
        # on built-ins (no "Configure" affordance on the built-in card).
        json_schema_extra=SecretHint(reason="API credentials should be masked").to_hints(),
    )

    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0 to 2.0)",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )

    max_tokens: Optional[int] = Field(
        default=8192,
        description="Maximum number of tokens to generate (None for model default)",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )

    top_p: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Top-p (nucleus) sampling parameter"
    )

    top_k: Optional[int] = Field(default=None, description="Top-k sampling parameter")

    extra: Dict[str, Any] = Field(
        default_factory=dict, description="Provider-specific kwargs passed through as is"
    )

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
