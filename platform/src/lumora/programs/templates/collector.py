"""
blueprints/collector.py

BlueprintConfigCollector - collects configs from resolved blueprints.

This is a general-purpose utility for extracting element metadata
from a BlueprintSpec. Used by validation, card building, and other services.
"""

from lumora.elements.configuration.meta import ElementConfigMeta
from lumora.programs.templates.contracts import ResolvedBlueprint
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.domain.references import Ref
from lumora.resources.references import RefWalker


class BlueprintConfigCollector:
    """
    Collects element configs from a resolved BlueprintSpec.

    Responsible for:
    - Iterating through all categories in the blueprint
    - Extracting config metadata for each element
    - Identifying dependency rids for each config (using RefWalker)

    Used by:
    - BlueprintService.validate_blueprint()
    - BlueprintService.get_blueprint_cards()
    """

    def collect(self, spec: ResolvedBlueprint) -> list[ElementConfigMeta]:
        """
        Collect all configs from a resolved blueprint.

        Args:
            spec: A fully resolved BlueprintSpec

        Returns:
            List of ElementConfigMeta for all elements in the blueprint
        """
        result: list[ElementConfigMeta] = []

        for category in ResourceCategory:
            elements = getattr(spec, category.value, [])
            for element in elements:
                rid = self._extract_rid(element.rid)

                dep_rids = list(RefWalker.all_rids(element.config))

                result.append(
                    ElementConfigMeta(
                        rid=rid,
                        category=category,
                        type_key=element.type,
                        name=element.name,
                        config=element.config,
                        dependency_rids=dep_rids,
                    )
                )

        return result

    @staticmethod
    def _extract_rid(rid_obj) -> str:
        """Extract rid string from Ref or string."""
        if isinstance(rid_obj, Ref):
            return rid_obj.ref
        return str(rid_obj)
