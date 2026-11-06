"""Inspection use cases distinguish owner overlays from authorized curated defaults."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, Field, JsonValue

from mas.application.access.administrators import AdministratorAccess
from mas.application.elements.validation import ElementValidationResult
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.domain.element_card import ElementCard
from mas.domain.models import Model
from mas.resources.inspection import (
    InspectionContext,
    InspectionMode,
    InspectionResourceReader,
    ResourceProbe,
)


class CuratedInspection(Model):
    mode: Literal[InspectionMode.CURATED_BASE] = InspectionMode.CURATED_BASE
    observed_at: AwareDatetime
    results: tuple[ElementValidationResult, ...] = Field(max_length=100)


class ResourceInspectionService:
    def __init__(
        self,
        probe: ResourceProbe,
        administrators: AdministratorAccess,
        resources: InspectionResourceReader,
    ) -> None:
        self._probe, self._administrators, self._resources = probe, administrators, resources

    @staticmethod
    def _selection(rids: list[str], timeout_seconds: float = 10) -> None:
        if len(rids) > 100 or any(not rid for rid in rids):
            raise ValueError("Invalid inspection selection")
        if not 0 < timeout_seconds <= 60:
            raise ValueError("Invalid inspection timeout")

    async def validate(
        self,
        rids: list[str],
        caller: Identity,
        *,
        credential_user_id: str,
        timeout_seconds: float,
    ) -> list[ElementValidationResult]:
        self._selection(rids, timeout_seconds)
        return await self._probe.validate(
            rids, InspectionContext(caller, credential_user_id), timeout_seconds=timeout_seconds
        )

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
    ) -> ElementValidationResult:
        self._selection([], timeout_seconds)
        return await self._probe.validate_config(
            category,
            type_key,
            config,
            InspectionContext(caller, credential_user_id),
            name=name,
            timeout_seconds=timeout_seconds,
        )

    async def cards(self, rids: list[str], caller: Identity) -> dict[str, ElementCard]:
        self._selection(rids)
        return await self._probe.cards(rids, InspectionContext(caller))

    async def _curated(self, user: Identity, owner: Identity) -> InspectionContext:
        if not user.is_user or not user.id or not await self._administrators.allowed(user):
            raise PermissionError("Administrator access is required")
        return InspectionContext(owner, user.id, InspectionMode.CURATED_BASE)

    async def validate_curated(
        self,
        rids: list[str],
        user: Identity,
        owner: Identity,
        *,
        timeout_seconds: float = 10,
    ) -> CuratedInspection:
        context = await self._curated(user, owner)
        self._selection(rids, timeout_seconds)
        for rid in dict.fromkeys(rids):
            if (await self._resources.get(rid)).descriptor is None:
                raise ValueError("Curated inspection requires built-in resources")
        results = await self._probe.validate(rids, context, timeout_seconds=timeout_seconds)
        return CuratedInspection(observed_at=datetime.now(UTC), results=tuple(results))

    async def validate_curated_config(
        self,
        category: ResourceCategory,
        type_key: str,
        config: dict[str, JsonValue],
        user: Identity,
        owner: Identity,
        *,
        name: str | None = None,
        timeout_seconds: float = 10,
    ) -> CuratedInspection:
        context = await self._curated(user, owner)
        self._selection([], timeout_seconds)
        result = await self._probe.validate_config(
            category, type_key, config, context, name=name, timeout_seconds=timeout_seconds
        )
        return CuratedInspection(observed_at=datetime.now(UTC), results=(result,))
