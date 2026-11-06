"""The orchestrator plugin supplies topology exclusions to graph-independent policy."""

import pytest
from mas.core.enums import ResourceCategory
from mas.domain.element_card import ElementCard
from mas.elements.nodes.orchestrator.delegation_policy import OrchestratorDelegationPolicy
from mas.graph.models import AdjacentNodes
from mas.graph.topology.models import FinalizerPathInfo, StepTopology


@pytest.mark.parametrize("distances", [None, {"finalizer": 1, "summary": 2}])
def test_only_adjacent_nonfinalization_targets_are_delegable(distances):
    nodes = {
        uid: ElementCard(uid=uid, category=ResourceCategory.NODE, type_key="test", name=uid)
        for uid in ("worker", "finalizer", "summary")
    }
    topology = StepTopology(
        finalizer_paths=FinalizerPathInfo(distances=distances) if distances is not None else None
    )
    policy = OrchestratorDelegationPolicy(topology, AdjacentNodes(nodes=nodes))
    expected = {uid: card for uid, card in nodes.items() if uid not in (distances or {})}
    assert policy.filter_delegable_nodes(nodes) == expected
    assert not policy.is_delegable("outside")
