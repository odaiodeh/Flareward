from enum import Enum


class LLMValidationCode(str, Enum):
    """Validation codes shared across LLM validators."""

    MODEL_AVAILABLE = "MODEL_AVAILABLE"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
