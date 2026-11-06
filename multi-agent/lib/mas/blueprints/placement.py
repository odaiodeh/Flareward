"""Authorize and resolve placement inspection through normal blueprint boundaries."""

from uuid import uuid4

from mas.application.execution.placement import GraphPlacementPreviewer
from mas.application.programs.blueprints import BlueprintProgramImporter
from mas.blueprints.authoring import BlueprintAuthoringService
from mas.blueprints.contracts import BlueprintData, BlueprintResolutionSource
from mas.blueprints.resolution import resolve_blueprint
from mas.core.identity import Identity
from mas.domain.execution.placement import GraphPlacementPlan


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
