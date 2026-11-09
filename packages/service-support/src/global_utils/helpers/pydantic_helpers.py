"""
Pydantic helpers and custom type aliases.
"""
from __future__ import annotations
from typing import Any, Annotated
from pydantic import BeforeValidator


def coerce_to_str(v: Any) -> str:
    """
    Convert None or non-string values to empty string.
    """
    if v is None:
        return ""
    return str(v)


CoercedStr = Annotated[str, BeforeValidator(coerce_to_str)]
