"""Closed native tracing selections; vendor clients stay in optional adapters."""

from enum import StrEnum


class TracingBackend(StrEnum):
    DISABLED = "disabled"
    LANGFUSE = "langfuse"
