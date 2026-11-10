"""Inspect authorized authoring data through existing validators and card builders."""

import asyncio
from collections.abc import Awaitable
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter

from pydantic import ValidationError

from lumora.async_work import await_owned
from lumora.elements.catalog.card_service import ElementCardService
from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.configuration.meta import ElementConfigMeta
from lumora.elements.construction.references import references
from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.elements.domain.cards import ElementCard
from lumora.elements.exceptions import ElementInspectionError
from lumora.elements.validation import ElementValidationResult, ValidationContext
from lumora.elements.validation_services.models import BlueprintValidationResult
from lumora.elements.validation_services.service import ElementValidationService
from lumora.programs.templates.authoring import BlueprintAuthoringService
from lumora.programs.templates.collector import BlueprintConfigCollector
from lumora.programs.templates.contracts import BlueprintData, BlueprintResolutionSource
from lumora.programs.templates.resolution import resolve_blueprint
from lumora.resources.secrets import authored_configuration
from lumora.services.auth.service import AuthService
from lumora.services.identity.domain import Identity


@dataclass(frozen=True)
class InspectionBlueprint:
    configurations: tuple[ElementConfigMeta, ...]
    missing: dict[str, str]


class BlueprintInspectionService:
    def __init__(
        self,
        authoring: BlueprintAuthoringService,
        source: BlueprintResolutionSource,
        elements: ElementRegistry,
        configuration: ConfigurationSecrets,
        auth: AuthService | None = None,
    ) -> None:
        self._authoring, self._source, self._elements = authoring, source, elements
        self._configuration, self._auth = configuration, auth
        self._validation, self._cards = (
            ElementValidationService(elements),
            ElementCardService(elements),
        )

    async def validate(
        self,
        caller: Identity,
        *,
        blueprint_id: str | None = None,
        spec: BlueprintData | None = None,
        credential_user_id: str = "",
        timeout_seconds: float = 10,
    ) -> BlueprintValidationResult:
        resolved = await self._resolve(caller, blueprint_id, spec)
        ordered, missing = self._ordered(resolved)
        configurations = await self._hydrate(ordered, caller)
        context = ValidationContext(
            user_id=caller.id,
            credential_user_id=credential_user_id,
            timeout_seconds=timeout_seconds,
            auth_service=self._auth,
        )
        results = await self._run(self._validation.validate_ordered_async(configurations, context))
        results.update(
            {
                rid: ElementValidationResult.create_error(rid, reason)
                for rid, reason in missing.items()
            }
        )
        return BlueprintValidationResult(
            blueprint_id=blueprint_id if blueprint_id is not None else "draft",
            is_valid=all(result.is_valid for result in results.values()),
            element_results=results,
        )

    async def cards(
        self,
        caller: Identity,
        *,
        blueprint_id: str | None = None,
        spec: BlueprintData | None = None,
    ) -> dict[str, ElementCard]:
        resolved = await self._resolve(caller, blueprint_id, spec)
        ordered, missing = self._ordered(resolved)
        if missing:
            raise KeyError("Blueprint resource not found")
        if any(meta.validation_override_error for meta in ordered):
            raise ValueError("Invalid blueprint resource dependencies")
        configurations = await self._hydrate(ordered, caller)
        return await self._run(
            await_owned(asyncio.to_thread(self._cards.build_all_cards, configurations))
        )

    async def _resolve(
        self, caller: Identity, blueprint_id: str | None, spec: BlueprintData | None
    ) -> InspectionBlueprint:
        resolved = await resolve_blueprint(
            self._authoring, self._source, caller, blueprint_id=blueprint_id, spec=spec
        )
        configurations = []
        for meta in BlueprintConfigCollector().collect(resolved.blueprint):
            schema = self._elements.get_schema(meta.category, meta.type_key)
            try:
                model = schema.model_validate(authored_configuration(meta.config), by_name=True)
            except ValidationError:
                raise ValueError("Invalid blueprint configuration") from None
            configurations.append(meta.model_copy(update={"config": model}))
        return InspectionBlueprint(tuple(configurations), resolved.missing)

    async def _hydrate(
        self, configurations: list[ElementConfigMeta], caller: Identity
    ) -> list[ElementConfigMeta]:
        hydrated = []
        for meta in configurations:
            try:
                data = await self._configuration.resolve_authored(meta.config, caller)
                hydrated.append(
                    meta.model_copy(
                        update={"config": type(meta.config).model_validate(data, by_name=True)}
                    )
                )
            except ValidationError:
                raise ValueError("Invalid blueprint configuration") from None
        return hydrated

    @staticmethod
    def _ordered(resolved: InspectionBlueprint) -> tuple[list[ElementConfigMeta], dict[str, str]]:
        configurations = {meta.rid: meta for meta in resolved.configurations}
        if len(configurations) != len(resolved.configurations):
            raise ValueError("Duplicate blueprint resource identifiers")
        missing = dict(resolved.missing)
        graph, prepared = {}, {}
        for rid, meta in configurations.items():
            dependencies = sorted(
                set(references(meta.config)), key=lambda key: (key.category, key.rid)
            )
            absent = {key.rid for key in dependencies if key.rid not in configurations}
            missing.update({key: "Referenced resource not found" for key in absent})
            mismatch = any(
                key.rid in configurations and configurations[key.rid].category != key.category
                for key in dependencies
            )
            error = (
                "Resource dependency not found"
                if absent
                else (
                    "Resource dependency category mismatch"
                    if mismatch
                    else meta.validation_override_error
                )
            )
            prepared[rid] = meta.model_copy(
                update={
                    "validation_override_error": error,
                    "dependency_rids": [key.rid for key in dependencies],
                }
            )
            graph[rid] = {key.rid for key in dependencies if key.rid in configurations}
        try:
            return [prepared[rid] for rid in TopologicalSorter(graph).static_order()], missing
        except CycleError:
            raise ValueError("Blueprint construction dependency cycle") from None

    @staticmethod
    async def _run[T](operation: Awaitable[T]) -> T:
        try:
            return await operation
        except ValidationError:
            raise ValueError("Invalid blueprint configuration") from None
        except Exception:
            # Plugin/SDK exception details can contain resolved credentials.
            raise ElementInspectionError() from None
