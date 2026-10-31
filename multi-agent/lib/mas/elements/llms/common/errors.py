"""Translate provider failures without exposing SDK responses or credentials."""

from collections.abc import Iterator
from contextlib import contextmanager

from mas.core.tracing import ObservationHandle


class LLMProviderError(RuntimeError):
    """A model request failed at its provider boundary."""


@contextmanager
def provider_errors(observation: ObservationHandle, provider: str) -> Iterator[None]:
    try:
        yield
    except Exception as error:
        message = f"{provider} request failed ({type(error).__name__})"
        observation.update(level="ERROR", status_message=message)
        raise LLMProviderError(message) from None
