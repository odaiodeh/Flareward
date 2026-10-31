"""
Orchestrator pattern validation logic.

Validates orchestrator delegation patterns, return paths, and finalization requirements.
Leverages existing topology utilities to avoid duplication (SOLID principles).
"""

from mas.graph.graph_plan import GraphPlan
from mas.graph.models.workflow import Step
from mas.graph.state.graph_state import Channel
from mas.graph.topology.finalizer_analyzer import FinalizerAnalyzer
from mas.graph.topology.graph_builder import EdgeType, GraphAnalyzer
from mas.graph.topology.hierarchy_analyzer import HierarchyAnalyzer
from mas.graph.topology.models import EdgeRelation

from ..models import MessageCode, MessageSeverity, ValidationMessage
from .models import NodeTypeConfig, OrchestratorIssue, OrchestratorIssueType


class OrchestratorPatternChecker:
    """
    Validates orchestrator delegation patterns and requirements.

    SOLID Design:
    - Single Responsibility: Only checks orchestrator patterns
    - Open/Closed: Extensible via NodeTypeConfig
    Topology analyzers supply connectivity, hierarchy, and finalizer information.

    DRY: Reuses existing topology utilities instead of duplicating logic:
    - GraphAnalyzer: For graph structure, edge types, adjacency
    - FinalizerAnalyzer: For finding finalization nodes
    - HierarchyAnalyzer: For orchestrator parent-child relationships
    """

    def __init__(self, config: NodeTypeConfig = None):
        """
        Initialize checker with configuration.

        Args:
            config: Configuration for node type identification (defaults to standard types)
        """
        self._config = config or NodeTypeConfig()
        self._finalizer_analyzer = FinalizerAnalyzer(output_channel=Channel.OUTPUT)

    def check_orchestrator_patterns(
        self, plan: GraphPlan
    ) -> tuple[list[OrchestratorIssue], list[ValidationMessage]]:
        """
        Check all orchestrator patterns using topology utilities.

        Validates:
        1. Delegation edges must be BRANCH (not AFTER)
        2. Non-finalization delegated nodes must have return path to orchestrator
        3. Top-level orchestrators must have at least one finalization path
        4. Orchestrators must have exit_condition of type router_direct

        Args:
            plan: Graph plan to validate

        Returns:
            Tuple of (issues, messages) for reporting
        """
        issues = []
        messages = []

        orchestrators = self._find_orchestrators(plan)
        if not orchestrators:
            return issues, messages

        # Reuse GraphAnalyzer for graph structure
        graph_analyzer = GraphAnalyzer(plan)

        # Reuse HierarchyAnalyzer for orchestrator hierarchy (BOTH edge types)
        hierarchy_analyzer = HierarchyAnalyzer(graph_analyzer)
        orch_uids = {o.uid for o in orchestrators}
        graph_hierarchy = hierarchy_analyzer.analyze_hierarchy(
            orch_uids,
            EdgeRelation.BOTH,  # Consider both AFTER and BRANCH edges
        )

        # Reuse FinalizerAnalyzer to find finalizers once
        finalizer_nodes = self._finalizer_analyzer.find_all_finalizers(plan)

        for orch in orchestrators:
            # Rule 1: Delegation edges validation
            self._check_delegation_edges(orch, graph_analyzer, issues, messages)

            # Rule 2: Return paths validation
            self._check_return_paths(orch, plan, graph_analyzer, finalizer_nodes, issues, messages)

            # Rule 3: Finalize requirement (top-level only)
            orch_hierarchy = graph_hierarchy.get_hierarchy(orch.uid)
            if orch_hierarchy and orch_hierarchy.is_root:
                self._check_finalize_exists(orch, finalizer_nodes, graph_analyzer, issues, messages)

            # Rule 4: Condition type validation
            self._check_condition_type(orch, issues, messages)

        return issues, messages

    # ================================================================
    # VALIDATION RULES - Using Topology Utilities
    # ================================================================

    def _check_delegation_edges(
        self,
        orch: Step,
        graph_analyzer: GraphAnalyzer,
        issues: list[OrchestratorIssue],
        messages: list[ValidationMessage],
    ) -> None:
        """
        Rule 1: Orchestrator must delegate via BRANCH, not AFTER.

        Orchestrators use conditional routing to delegate work.
        AFTER edges imply sequential dependency, not delegation.

        VALID:   orch → (BRANCH) → worker  (delegation)
        INVALID: orch → (AFTER) → worker   (sequential dependency, not delegation)

        Note: worker → (AFTER) → orch is VALID (return path, not checked here)

        Uses GraphAnalyzer.edge_types to check edge types.
        """
        if not orch.branches:
            return

        branch_targets = set(orch.branches.values())

        # Check if orchestrator has OUTGOING AFTER edge to any delegated node
        for target_uid in branch_targets:
            # Check edge FROM orchestrator TO target
            edge = (orch.uid, target_uid)
            edge_type = graph_analyzer.edge_types.get(edge)

            # If there's an AFTER edge from orch to target, that's wrong
            # (Should only delegate via BRANCH)
            if edge_type == EdgeType.AFTER:
                issue = OrchestratorIssue(
                    issue_type=OrchestratorIssueType.INVALID_DELEGATION_EDGE,
                    orchestrator_uid=orch.uid,
                    related_node_uid=target_uid,
                    description=(
                        f"Orchestrator has OUTGOING AFTER edge to delegated node '{target_uid}'"
                    ),
                )
                issues.append(issue)

                target_step = graph_analyzer.plan.get_step(target_uid)
                target_name = (
                    target_step.meta.display_name
                    if target_step and target_step.meta
                    else target_uid
                )

                messages.append(
                    ValidationMessage(
                        text=f"Orchestrator '{orch.uid}' has OUTGOING AFTER edge to "
                        f"'{target_name}' "
                        f"(should only use BRANCH for delegation)",
                        severity=MessageSeverity.ERROR,
                        code=MessageCode.ORCHESTRATOR_INVALID_DELEGATION_EDGE,
                        context={
                            "orchestrator_uid": orch.uid,
                            "worker_uid": target_uid,
                            "edge_type": EdgeType.AFTER.value,
                            "expected_edge_type": EdgeType.BRANCH.value,
                            "fix": (
                                "Remove OUTGOING AFTER edge from orchestrator to delegated "
                                "node, keep only BRANCH"
                            ),
                        },
                    )
                )

    def _check_return_paths(
        self,
        orch: Step,
        plan: GraphPlan,
        graph_analyzer: GraphAnalyzer,
        finalizer_nodes: set[str],
        issues: list[OrchestratorIssue],
        messages: list[ValidationMessage],
    ) -> None:
        """
        Rule 2: Delegated nodes must have return path to orchestrator.

        Two types of return paths:
        - Worker nodes: return via AFTER (worker → orch)
        - Orchestrator nodes: return via BRANCH (child_orch → parent_orch)

        Non-finalization paths should return to the orchestrator for response processing.
        Finalization paths (leading to output) don't need to return.

        Uses FinalizerAnalyzer to identify finalization paths.
        Uses GraphAnalyzer.adjacency to check return paths.
        """
        if not orch.branches:
            return

        for branch_name, target_uid in orch.branches.items():
            # Skip finalize paths (use existing finalizer detection)
            if target_uid in finalizer_nodes:
                continue

            # Check if target leads to finalizer (finalization path)
            if self._leads_to_finalizer(target_uid, finalizer_nodes, graph_analyzer):
                continue  # Finalization path - no return needed

            target_step = plan.get_step(target_uid)
            if not target_step:
                continue

            # Check if target is an orchestrator or a worker
            is_target_orchestrator = target_step.type_key == self._config.node_type

            has_return_path = False

            if is_target_orchestrator:
                # Target is an orchestrator - check for BRANCH return path
                if hasattr(target_step, "branches") and target_step.branches:
                    if orch.uid in target_step.branches.values():
                        has_return_path = True
            else:
                # Target is a worker - check for AFTER return path
                if self._has_return_path_to(target_uid, orch.uid, graph_analyzer):
                    has_return_path = True

            if not has_return_path:
                issue = OrchestratorIssue(
                    issue_type=OrchestratorIssueType.MISSING_RETURN_PATH,
                    orchestrator_uid=orch.uid,
                    related_node_uid=target_uid,
                    description=f"Delegated node '{target_uid}' has no return path to orchestrator",
                )
                issues.append(issue)

                target_name = target_step.meta.display_name if target_step.meta else target_uid

                if is_target_orchestrator:
                    fix_msg = (
                        f"Add branch in '{target_uid}' that returns to '{orch.uid}' via BRANCH"
                    )
                else:
                    fix_msg = (
                        f"Add 'after: [{orch.uid}]' to worker node or ensure path leads to "
                        f"finalization"
                    )

                messages.append(
                    ValidationMessage(
                        text=f"Orchestrator '{orch.uid}' delegates to '{target_name}' "
                        f"but node has no return path",
                        severity=MessageSeverity.WARNING,
                        code=MessageCode.ORCHESTRATOR_MISSING_RETURN_PATH,
                        context={
                            "orchestrator_uid": orch.uid,
                            "worker_uid": target_uid,
                            "branch_name": branch_name,
                            "target_type": "orchestrator" if is_target_orchestrator else "worker",
                            "expected_return_type": "BRANCH" if is_target_orchestrator else "AFTER",
                            "fix": fix_msg,
                        },
                    )
                )

    def _check_finalize_exists(
        self,
        orch: Step,
        finalizer_nodes: set[str],
        graph_analyzer: GraphAnalyzer,
        issues: list[OrchestratorIssue],
        messages: list[ValidationMessage],
    ) -> None:
        """
        Rule 3: Top-level orchestrator must have finalize branch.

        Top-level orchestrators (no parent orchestrators) must have a completion strategy.
        They need at least one branch that leads to finalization.

        Nested orchestrators don't need their own finalize path - parent handles it.

        Uses FinalizerAnalyzer to identify finalization nodes.
        """
        if not orch.branches:
            # No branches at all - definitely missing finalize
            issue = OrchestratorIssue(
                issue_type=OrchestratorIssueType.MISSING_FINALIZE,
                orchestrator_uid=orch.uid,
                related_node_uid=None,
                description=(
                    f"Top-level orchestrator '{orch.uid}' has no branches (needs finalize path)"
                ),
            )
            issues.append(issue)

            messages.append(
                ValidationMessage(
                    text=(
                        f"Top-level orchestrator '{orch.uid}' has no branches - needs "
                        f"completion strategy"
                    ),
                    severity=MessageSeverity.ERROR,
                    code=MessageCode.ORCHESTRATOR_MISSING_FINALIZE,
                    context={
                        "orchestrator_uid": orch.uid,
                        "fix": "Add branch to final_answer_node or terminal node",
                    },
                )
            )
            return

        # Check if any branch leads to finalization
        has_finalize_branch = False

        for target_uid in orch.branches.values():
            # Direct finalizer
            if target_uid in finalizer_nodes:
                has_finalize_branch = True
                break

            # Leads to finalizer
            if self._leads_to_finalizer(target_uid, finalizer_nodes, graph_analyzer):
                has_finalize_branch = True
                break

            # Terminal node (also counts as finalization)
            if target_uid in graph_analyzer.get_terminal_nodes():
                has_finalize_branch = True
                break

        if not has_finalize_branch:
            issue = OrchestratorIssue(
                issue_type=OrchestratorIssueType.MISSING_FINALIZE,
                orchestrator_uid=orch.uid,
                related_node_uid=None,
                description=f"Top-level orchestrator '{orch.uid}' has no finalize path",
            )
            issues.append(issue)

            messages.append(
                ValidationMessage(
                    text=f"Top-level orchestrator '{orch.uid}' missing finalize branch "
                    f"(needs completion strategy)",
                    severity=MessageSeverity.ERROR,
                    code=MessageCode.ORCHESTRATOR_MISSING_FINALIZE,
                    context={
                        "orchestrator_uid": orch.uid,
                        "fix": "Add branch to final_answer_node or terminal node",
                    },
                )
            )

    def _check_condition_type(
        self, orch: Step, issues: list[OrchestratorIssue], messages: list[ValidationMessage]
    ) -> None:
        """
        Rule 4: Orchestrator must have exit_condition of required type.

        Orchestrators need direct routing control to decide delegation paths.
        By default, they must use 'router_direct' condition type.

        Configuration allows flexibility for different orchestrator types.
        """
        # Only check if orchestrator has branches
        if not orch.branches:
            return

        # Check if orchestrator has a condition
        if not orch.condition:
            issue = OrchestratorIssue(
                issue_type=OrchestratorIssueType.INVALID_CONDITION_TYPE,
                orchestrator_uid=orch.uid,
                related_node_uid=None,
                description=(
                    f"Orchestrator '{orch.uid}' has branches but no exit_condition configured"
                ),
            )
            issues.append(issue)

            messages.append(
                ValidationMessage(
                    text=f"Orchestrator '{orch.uid}' has branches but no exit_condition "
                    f"(needs '{self._config.required_condition_type}' condition)",
                    severity=MessageSeverity.ERROR,
                    code=MessageCode.ORCHESTRATOR_INVALID_CONDITION_TYPE,
                    context={
                        "orchestrator_uid": orch.uid,
                        "expected_condition_type": self._config.required_condition_type,
                        "fix": (
                            f"Add exit_condition with type '{self._config.required_condition_type}'"
                        ),
                    },
                )
            )
            return

        # Check condition type
        if orch.condition.type_key != self._config.required_condition_type:
            issue = OrchestratorIssue(
                issue_type=OrchestratorIssueType.INVALID_CONDITION_TYPE,
                orchestrator_uid=orch.uid,
                related_node_uid=None,
                description=f"Orchestrator '{orch.uid}' has condition type "
                f"'{orch.condition.type_key}' "
                f"(expected '{self._config.required_condition_type}')",
            )
            issues.append(issue)

            messages.append(
                ValidationMessage(
                    text=f"Orchestrator '{orch.uid}' has condition type "
                    f"'{orch.condition.type_key}' "
                    f"(expected '{self._config.required_condition_type}')",
                    severity=MessageSeverity.ERROR,
                    code=MessageCode.ORCHESTRATOR_INVALID_CONDITION_TYPE,
                    context={
                        "orchestrator_uid": orch.uid,
                        "actual_condition_type": orch.condition.type_key,
                        "expected_condition_type": self._config.required_condition_type,
                        "fix": f"Change condition type to '{self._config.required_condition_type}'",
                    },
                )
            )

    # ================================================================
    # HELPER FUNCTIONS - Using Topology Utilities
    # ================================================================

    def _find_orchestrators(self, plan: GraphPlan) -> list[Step]:
        """Find all orchestrator nodes in the plan."""
        return [step for step in plan.steps if step.type_key == self._config.node_type]

    def _leads_to_finalizer(
        self, node_uid: str, finalizer_nodes: set[str], graph_analyzer: GraphAnalyzer
    ) -> bool:
        """
        Check if node has path to any finalizer.

        Uses GraphAnalyzer.adjacency for BFS traversal.
        """
        if node_uid in finalizer_nodes:
            return True

        visited = {node_uid}
        queue = [node_uid]

        while queue:
            current = queue.pop(0)

            for neighbor in graph_analyzer.adjacency.get(current, set()):
                if neighbor in finalizer_nodes:
                    return True

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return False

    def _has_return_path_to(
        self, worker_uid: str, orch_uid: str, graph_analyzer: GraphAnalyzer
    ) -> bool:
        """
        Check if worker has path back to orchestrator.

        Uses GraphAnalyzer to check AFTER dependencies (return paths).
        BFS follows 'after' edges to find return path.
        """
        worker_step = graph_analyzer.plan.get_step(worker_uid)
        if not worker_step:
            return False

        # Direct return
        if orch_uid in worker_step.after:
            return True

        # Indirect return via BFS on AFTER edges
        visited = {worker_uid}
        queue = list(worker_step.after)

        while queue:
            current_uid = queue.pop(0)

            if current_uid == orch_uid:
                return True

            if current_uid in visited:
                continue

            visited.add(current_uid)
            current_step = graph_analyzer.plan.get_step(current_uid)
            if current_step:
                queue.extend(current_step.after)

        return False
