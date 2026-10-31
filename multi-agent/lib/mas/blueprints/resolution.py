"""Select authoring data and authorize saved documents before resolving references."""

from mas.blueprints.authoring import BlueprintAuthoringService
from mas.blueprints.contracts import (
    BlueprintData,
    BlueprintResolution,
    BlueprintResolutionSource,
    ResolvedBlueprint,
)
from mas.core.identity import Identity


async def resolve_blueprint(
    authoring: BlueprintAuthoringService,
    source: BlueprintResolutionSource,
    caller: Identity,
    *,
    blueprint_id: str | None,
    spec: BlueprintData | None,
) -> BlueprintResolution:
    if (blueprint_id is None) == (spec is None):
        raise ValueError("Provide a stored blueprint or a draft")
    if blueprint_id is not None:
        spec = (await authoring.get(blueprint_id, caller)).spec_dict
    assert spec is not None
    return await source.resolve(spec, caller, stored=blueprint_id is not None)


class BlueprintImportSource:
    """Use the same owner checks and installed schemas as authoring and inspection."""

    def __init__(
        self, authoring: BlueprintAuthoringService, resolution: BlueprintResolutionSource
    ) -> None:
        self._authoring, self._resolution = authoring, resolution

    async def resolve(self, blueprint_id: str, caller: Identity) -> ResolvedBlueprint:
        result = await resolve_blueprint(
            self._authoring, self._resolution, caller, blueprint_id=blueprint_id, spec=None
        )
        if result.missing:
            raise KeyError(next(iter(result.missing)))
        return result.blueprint
