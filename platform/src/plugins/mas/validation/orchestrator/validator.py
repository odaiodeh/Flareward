"""
Orchestrator validation provider.

ValidationProvider implementation for orchestrator pattern validation.
"""

from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.validation.interfaces import ValidationProvider
from lumora.programs.graph.validation.models import ValidationReport
from plugins.mas.validation.orchestrator.checker import OrchestratorPatternChecker
from plugins.mas.validation.orchestrator.models import NodeTypeConfig


class OrchestratorValidator(ValidationProvider):
    """
    Validates orchestrator node patterns and requirements.

    Checks:
    1. Delegation edges must be BRANCH (not AFTER)
    2. Non-finalization delegated nodes must have return paths
    3. Top-level orchestrators must have finalization paths
    4. Orchestrators must have exit_condition of required type

    SOLID:
    - Single Responsibility: Only orchestrator validation
    - Open/Closed: Extensible via NodeTypeConfig
    - Liskov Substitution: Implements ValidationProvider interface
    """

    name = "orchestrator"

    def __init__(self, config: NodeTypeConfig = None, *args, **kwargs):
        """
        Initialize validator with optional configuration.

        Args:
            config: Configuration for node type identification
        """
        self._checker = OrchestratorPatternChecker(config=config)

    def validate(self, plan: GraphPlan) -> ValidationReport:
        """
        Validate orchestrator patterns in the graph plan.

        Args:
            plan: Graph plan to validate

        Returns:
            ValidationReport with issues and messages
        """
        issues, messages = self._checker.check_orchestrator_patterns(plan)

        return ValidationReport(
            validator_name=self.name,
            is_valid=len(issues) == 0,
            messages=messages,
            details={"orchestrator_issues": [issue.model_dump() for issue in issues]},
        )
