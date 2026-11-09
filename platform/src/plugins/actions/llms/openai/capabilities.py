"""Per-composition model capabilities cache and pure longest-prefix lookup."""

import asyncio
import time
from copy import deepcopy

from pydantic import JsonValue

from flareward.services.actions.contracts import ActionSettings


class ModelCapabilities:
    def __init__(self, reader: ActionSettings | None, *, ttl: float = 30) -> None:
        self._reader, self._ttl = reader, ttl
        self._value: dict[str, JsonValue] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def load(self) -> dict[str, JsonValue]:
        async with self._lock:
            if time.monotonic() >= self._expires_at:
                section = (
                    await self._reader.get_section("openai_model_capabilities")
                    if self._reader
                    else None
                )
                value = section.get("capabilities", {}) if section else {}
                if not isinstance(value, dict):
                    raise ValueError("Invalid model capabilities configuration")
                self._value = deepcopy(value)
                self._expires_at = time.monotonic() + self._ttl
            return deepcopy(self._value)


def find_model_capabilities(
    caps: dict[str, JsonValue], model_name: str
) -> dict[str, JsonValue] | None:
    prefix = max((key for key in caps if model_name.startswith(key)), key=len, default=None)
    value = caps.get(prefix) if prefix is not None else None
    return value if isinstance(value, dict) else None
