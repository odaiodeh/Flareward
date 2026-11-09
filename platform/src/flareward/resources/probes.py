"""Owned inspection ports and explicit configuration views, independent of probe SDKs."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import JsonValue

from flareward.elements.domain.cards import ElementCard
from flareward.elements.validation import ElementValidationResult
from flareward.resources.authoring import ResourceRecord
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.identity.domain import Identity
from flareward.services.identity.scope import CallerScope


class InspectionMode(StrEnum):
    OWNER = "owner"
    CURATED_BASE = "curated_base"


@dataclass(frozen=True)
class InspectionContext:
    owner: Identity
    credential_user_id: str = ""
    mode: InspectionMode = InspectionMode.OWNER

    @property
    def scope(self) -> CallerScope:
        # Curated-base inspection must not substitute a caller's private overlay.
        return CallerScope(
            identity=self.owner if self.mode == InspectionMode.OWNER else None,
            is_admin=self.mode == InspectionMode.CURATED_BASE,
        )


class InspectionResourceReader(Protocol):
    async def get(self, rid: str) -> ResourceRecord: ...


class ResourceProbe(Protocol):
    async def validate(
        self, rids: list[str], context: InspectionContext, *, timeout_seconds: float
    ) -> list[ElementValidationResult]: ...

    async def validate_config(
        self,
        category: ResourceCategory,
        type_key: str,
        config: dict[str, JsonValue],
        context: InspectionContext,
        *,
        name: str | None,
        timeout_seconds: float,
    ) -> ElementValidationResult: ...

    async def cards(
        self, rids: list[str], context: InspectionContext
    ) -> dict[str, ElementCard]: ...
