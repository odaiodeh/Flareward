"""
Protocol-agnostic auth detection.

:class:`AuthDetector` runs :class:`DetectionStrategy` instances in order.
First match wins.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from flareward.services.auth.discovery.models import DetectionResult
from flareward.services.auth.ports import HttpClient

logger = logging.getLogger(__name__)


class DetectionStrategy(ABC):
    """Pluggable probe that can recognise one auth scheme."""

    @abstractmethod
    async def detect(
        self,
        url: str,
        response_headers: dict[str, str],
        http_client: HttpClient,
    ) -> DetectionResult | None: ...


class AuthDetector:
    """Runs strategies in priority order. First match wins."""

    def __init__(
        self,
        strategies: list[DetectionStrategy] | None = None,
        http_client: HttpClient | None = None,
    ):
        self._strategies = strategies or []
        self._http_client = http_client

    async def detect(
        self,
        url: str,
        response_headers: dict[str, str] | None = None,
    ) -> DetectionResult | None:
        headers = response_headers or {}
        for strategy in self._strategies:
            try:
                result = await strategy.detect(url, headers, self._http_client)
                if result is not None:
                    return result
            except Exception as exc:
                logger.warning(
                    "Detection strategy %s failed for %s: %s",
                    type(strategy).__name__,
                    url,
                    exc,
                )
        return None
