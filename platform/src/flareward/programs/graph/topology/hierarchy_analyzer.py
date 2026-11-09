"""
Generic hierarchy analyzer for graph topologies.

Provides reusable hierarchy analysis for any node types and edge relationships.
Can be used by validators, executors, or any component needing hierarchy insights.

SOLID Principles:
- Single Responsibility: Only analyzes hierarchies based on edge relationships
- Open/Closed: Extensible via EdgeRelation enum
- Dependency Inversion: Depends on GraphAnalyzer abstraction
"""

from collections import deque
from typing import Dict, List, Set

from flareward.programs.graph.topology.graph_builder import EdgeType, GraphAnalyzer
from flareward.programs.graph.topology.models import EdgeRelation, GraphHierarchy, HierarchyInfo


class HierarchyAnalyzer:
    """
    Generic hierarchy analyzer that works with any subset of nodes.

    Key Features:
    - Configurable edge filtering (AFTER, BRANCH, or BOTH)
    - Depth calculation using BFS
    - Parent-child relationship mapping
    - Root and leaf detection

    Usage Example:
        >>> analyzer = HierarchyAnalyzer(graph_analyzer)
        >>>
        >>> # Analyze orchestrator hierarchy using BOTH edge types
        >>> orch_uids = {s.uid for s in plan.steps if s.type_key == "orchestrator_node"}
        >>> hierarchy = analyzer.analyze_hierarchy(orch_uids, EdgeRelation.BOTH)
        >>>
        >>> # Find top-level orchestrator
        >>> top_level_orchs = hierarchy.root_nodes
        >>>
        >>> # Check if one node is ancestor of another
        >>> is_parent = hierarchy.is_ancestor_of(parent_uid, child_uid)
    """

    def __init__(self, graph_analyzer: GraphAnalyzer):
        """
        Initialize with a graph analyzer.

        Args:
            graph_analyzer: Graph analyzer providing edge and adjacency information
        """
        self.graph_analyzer = graph_analyzer

    def analyze_hierarchy(
        self, node_uids: Set[str], edge_relation: EdgeRelation = EdgeRelation.BOTH
    ) -> GraphHierarchy:
        """
        Analyze hierarchy for a specific subset of nodes.

        Args:
            node_uids: Set of node UIDs to analyze (e.g., all orchestrators, all agents)
            edge_relation: Which edge types to consider for hierarchy:
                - EdgeRelation.AFTER: Only dependency edges
                - EdgeRelation.BRANCH: Only conditional routing edges
                - EdgeRelation.BOTH: Both edge types

        Returns:
            Complete hierarchy analysis for the specified nodes
        """
        hierarchies: Dict[str, HierarchyInfo] = {}

        # Step 1: Build parent-child relationships within the subset
        for node_uid in node_uids:
            parents = self._find_parents(node_uid, node_uids, edge_relation)
            children = self._find_children(node_uid, node_uids, edge_relation)

            hierarchies[node_uid] = HierarchyInfo(
                node_uid=node_uid,
                parent_nodes=parents,
                child_nodes=children,
                is_root=len(parents) == 0,
                is_leaf=len(children) == 0,
                depth=0,  # Will be calculated in next step
            )

        # Step 2: Calculate depths using BFS from root nodes
        root_nodes = [uid for uid, info in hierarchies.items() if info.is_root]
        max_depth = self._calculate_depths(hierarchies, root_nodes)

        # Step 3: Rebuild hierarchies with calculated depths (immutable models)
        updated_hierarchies = {
            uid: HierarchyInfo(
                node_uid=info.node_uid,
                parent_nodes=info.parent_nodes,
                child_nodes=info.child_nodes,
                is_root=info.is_root,
                is_leaf=info.is_leaf,
                depth=info.depth,
            )
            for uid, info in hierarchies.items()
        }

        return GraphHierarchy(
            hierarchies=updated_hierarchies,
            edge_relation=edge_relation,
            root_nodes=root_nodes,
            max_depth=max_depth,
        )

    def _find_parents(
        self, node_uid: str, node_subset: Set[str], edge_relation: EdgeRelation
    ) -> List[str]:
        """
        Find parent nodes (nodes that point TO this node).

        Only considers nodes within the subset and respects edge_relation filter.
        """
        parents = []

        # Check all potential parent nodes in the subset
        for potential_parent_uid in node_subset:
            if potential_parent_uid == node_uid:
                continue

            # Check if there's an edge from potential_parent to node
            edge = (potential_parent_uid, node_uid)
            edge_type = self.graph_analyzer.edge_types.get(edge)

            if edge_type and self._should_consider_edge(edge_type, edge_relation):
                parents.append(potential_parent_uid)

        return parents

    def _find_children(
        self, node_uid: str, node_subset: Set[str], edge_relation: EdgeRelation
    ) -> List[str]:
        """
        Find child nodes (nodes this node points TO).

        Only considers nodes within the subset and respects edge_relation filter.
        """
        children = []

        # Get all adjacent nodes
        for target_uid in self.graph_analyzer.adjacency.get(node_uid, set()):
            if target_uid not in node_subset:
                continue

            edge = (node_uid, target_uid)
            edge_type = self.graph_analyzer.edge_types.get(edge)

            if edge_type and self._should_consider_edge(edge_type, edge_relation):
                children.append(target_uid)

        return children

    def _should_consider_edge(self, edge_type: EdgeType, edge_relation: EdgeRelation) -> bool:
        """
        Check if an edge type should be considered given the edge_relation filter.

        SOLID: Single point of edge filtering logic.
        """
        if edge_relation == EdgeRelation.BOTH:
            return True
        elif edge_relation == EdgeRelation.AFTER:
            return edge_type == EdgeType.AFTER
        elif edge_relation == EdgeRelation.BRANCH:
            return edge_type == EdgeType.BRANCH
        return False

    def _calculate_depths(
        self, hierarchies: Dict[str, HierarchyInfo], root_nodes: List[str]
    ) -> int:
        """
        Calculate depth for each node using BFS from roots.

        Modifies hierarchies in-place to set depth values.
        Returns maximum depth found.

        Note: Nodes reachable from multiple paths get the maximum depth.
        """
        max_depth = 0
        visited: Set[str] = set()
        queue: deque = deque([(uid, 0) for uid in root_nodes])

        while queue:
            node_uid, depth = queue.popleft()

            if node_uid in visited:
                continue

            visited.add(node_uid)

            # Update depth (use max if node reachable from multiple paths)
            current_info = hierarchies.get(node_uid)
            if current_info:
                # Create new HierarchyInfo with updated depth (Pydantic models are immutable)
                hierarchies[node_uid] = HierarchyInfo(
                    node_uid=current_info.node_uid,
                    parent_nodes=current_info.parent_nodes,
                    child_nodes=current_info.child_nodes,
                    is_root=current_info.is_root,
                    is_leaf=current_info.is_leaf,
                    depth=max(depth, current_info.depth),
                )

                max_depth = max(max_depth, depth)

                # Queue children with incremented depth
                for child_uid in current_info.child_nodes:
                    if child_uid not in visited:
                        queue.append((child_uid, depth + 1))

        return max_depth
