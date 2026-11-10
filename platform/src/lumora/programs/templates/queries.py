"""Authorized blueprint display snapshots omit declared credentials without storing new secrets."""

from lumora.programs.templates.authoring import BlueprintAuthoringService
from lumora.programs.templates.contracts import (
    BlueprintDocument,
    BlueprintResolutionSource,
    BlueprintSummary,
    BlueprintView,
    BlueprintViews,
)
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.secrets import map_configuration_secrets, public_default
from lumora.services.identity.domain import Identity


class BlueprintQueryService:
    def __init__(
        self, authoring: BlueprintAuthoringService, source: BlueprintResolutionSource
    ) -> None:
        self._authoring, self._source = authoring, source

    async def summaries(
        self, caller: Identity, *, skip: int = 0, limit: int = 100, sort_desc: bool = True
    ) -> list[BlueprintSummary]:
        page = await self._authoring.list(caller, skip=skip, limit=limit, sort_desc=sort_desc)
        return [
            BlueprintSummary.model_validate(
                {
                    **document.model_dump(exclude={"spec_dict", "rid_refs", "version"}),
                    "name": document.spec_dict.get("name", "Untitled blueprint"),
                    "description": document.spec_dict.get("description", ""),
                }
            )
            for document in page.items
        ]

    async def get(self, blueprint_id: str, caller: Identity) -> BlueprintView:
        return await self._view(await self._authoring.get(blueprint_id, caller), caller)

    async def list(
        self, caller: Identity, *, skip: int = 0, limit: int = 100, sort_desc: bool = True
    ) -> BlueprintViews:
        page = await self._authoring.list(caller, skip=skip, limit=limit, sort_desc=sort_desc)
        return BlueprintViews(
            items=[await self._view(document, caller) for document in page.items],
            total=page.total,
            skip=page.skip,
            limit=page.limit,
        )

    async def _view(self, document: BlueprintDocument, caller: Identity) -> BlueprintView:
        resolved = await self._source.resolve(document.spec_dict, caller, stored=True)
        spec = {
            "name": resolved.blueprint.name,
            "description": resolved.blueprint.description,
            "plan": [step.model_dump(mode="json") for step in resolved.blueprint.plan],
        }
        for category in ResourceCategory:
            spec[category.value] = [
                map_configuration_secrets(
                    resource,
                    lambda value, default: value if public_default(value, default) else "********",
                )
                for resource in getattr(resolved.blueprint, category.value)
            ]
        if "prompt_shortcuts" in document.spec_dict:
            spec["prompt_shortcuts"] = document.spec_dict["prompt_shortcuts"]
        return BlueprintView.model_validate(
            {
                **document.model_dump(exclude={"spec_dict"}),
                "spec_dict": spec,
                "missing_resources": resolved.missing,
            }
        )
