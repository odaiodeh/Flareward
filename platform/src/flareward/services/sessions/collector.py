"""
session/collector.py

SessionConfigCollector - collects configs from ElementInstances.

This is a general-purpose utility for extracting element metadata
from a ElementInstances. Used by RTGraphPlan for card building.
"""

from flareward.elements.configuration.meta import ElementConfigMeta
from flareward.elements.instances import ElementInstances
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.references import RefWalker


class SessionConfigCollector:
    """
    Collects element configs from a ElementInstances.

    ElementInstances contains runtime elements that were resolved
    from a blueprint. This collector extracts their metadata
    for card building.

    Responsible for:
    - Iterating through all categories in the session
    - Extracting config metadata for each runtime element
    - Identifying dependency rids for each config (using RefWalker)

    Used by:
    - RTGraphPlan._build_all_cards()
    """

    def collect(self, session: ElementInstances) -> list[ElementConfigMeta]:
        """
        Collect all configs from a session registry.

        Args:
            session: ElementInstances containing runtime elements

        Returns:
            List of ElementConfigMeta for all elements in the session
        """
        result: list[ElementConfigMeta] = []

        for category in ResourceCategory:
            for rid, runtime_element in session._store[category].items():
                resource_spec = runtime_element.resource_spec
                if resource_spec and resource_spec.config:
                    dep_rids = list(RefWalker.all_rids(resource_spec.config))

                    result.append(
                        ElementConfigMeta(
                            rid=rid,
                            category=category,
                            type_key=resource_spec.type,
                            name=resource_spec.name,
                            config=resource_spec.config,
                            dependency_rids=dep_rids,
                        )
                    )

        return result
