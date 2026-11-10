"""Authorize and resolve placement inspection through normal blueprint boundaries."""

from uuid import uuid4

from lumora.executions.domain.placement import GraphPlacementPlan
from lumora.executions.placement import GraphPlacementPreviewer
from lumora.programs.blueprints import BlueprintProgramImporter
from lumora.programs.templates.authoring import BlueprintAuthoringService
from lumora.programs.templates.contracts import BlueprintData, BlueprintResolutionSource
from lumora.programs.templates.resolution import resolve_blueprint
from lumora.services.identity.domain import Identity


class BlueprintPlacementService:
    def __init__(
        self,
        authoring: BlueprintAuthoringService,
        source: BlueprintResolutionSource,
        importer: BlueprintProgramImporter,
        previewer: GraphPlacementPreviewer,
    ) -> None:
        self._authoring, self._source = authoring, source
        self._importer, self._previewer = importer, previewer

    async def preview(
        self,
        caller: Identity,
        *,
        blueprint_id: str | None = None,
        spec: BlueprintData | None = None,
    ) -> GraphPlacementPlan:
        resolved = await resolve_blueprint(
            self._authoring, self._source, caller, blueprint_id=blueprint_id, spec=spec
        )
        if resolved.missing:
            raise KeyError("Blueprint resource not found")
        definition = self._importer.convert(
            resolved.blueprint, program_id="preview-" + uuid4().hex, owner=caller
        )
        return await self._previewer.preview(definition, caller)
