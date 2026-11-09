"""Application contract for retrieving context from a query."""

from abc import ABC, abstractmethod
from typing import Any


class BaseRetriever(ABC):
    @abstractmethod
    async def retrieve(self, query: str) -> Any:
        """Fetch context; concrete adapters own transport and resource lifetimes."""
        ...
