"""Deterministic, bounded path enumeration for authoring analysis."""

from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.topology.graph_builder import GraphAnalyzer


class GraphAnalysisLimit(ValueError):
    def __init__(self) -> None:
        super().__init__("Graph exceeds the path analysis limit")


class PathEnumerator:
    def __init__(self, plan: GraphPlan, *, max_paths: int = 1024, max_depth: int = 256) -> None:
        if max_paths < 1 or max_depth < 1:
            raise ValueError("Path analysis limits must be positive")
        self.analyzer = GraphAnalyzer(plan)
        self._max_paths, self._max_depth = max_paths, max_depth

    def enumerate_paths(self) -> dict[str, list[str]]:
        paths: dict[str, list[str]] = {}
        pending = [(root, ()) for root in sorted(self.analyzer.get_root_nodes(), reverse=True)]
        while pending:
            current, path = pending.pop()
            if len(path) >= self._max_depth:
                raise GraphAnalysisLimit()
            cyclic = current in path
            current_path = (*path, current)
            successors = self.analyzer.adjacency.get(current, set())
            if cyclic or not successors:
                if len(paths) >= self._max_paths:
                    raise GraphAnalysisLimit()
                suffix = "_cyclic" if cyclic else ""
                paths[f"path_{len(paths) + 1}{suffix}"] = list(current_path)
            else:
                pending.extend(
                    (successor, current_path) for successor in sorted(successors, reverse=True)
                )
        return paths
