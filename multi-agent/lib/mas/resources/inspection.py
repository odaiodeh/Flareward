"""Async authoring inspection contracts independent of storage, HTTP, and execution SDKs."""

from typing import Protocol

from pydantic import JsonValue

from mas.application.elements.validation import ElementValidationResult
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.domain.element_card import ElementCard


class ResourceInspection(Protocol):
    async def validate(
        self, rids: list[str], caller: Identity, *, credential_user_id: str, timeout_seconds: float
    ) -> list[ElementValidationResult]: ...

    async def validate_config(
        self,
        category: ResourceCategory,
        type_key: str,
        config: dict[str, JsonValue],
        caller: Identity,
        *,
        name: str | None,
        credential_user_id: str,
        timeout_seconds: float,
    ) -> ElementValidationResult: ...

    async def cards(self, rids: list[str], caller: Identity) -> dict[str, ElementCard]: ...
