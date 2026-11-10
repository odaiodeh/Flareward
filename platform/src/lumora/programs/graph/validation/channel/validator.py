from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.programs.graph.graph_plan import GraphPlan
from lumora.programs.graph.validation.channel.analyzer import ChannelAnalyzer
from lumora.programs.graph.validation.channel.matrix_builder import MatrixBuilder
from lumora.programs.graph.validation.interfaces import ValidationProvider
from lumora.programs.graph.validation.models import ValidationReport


class ChannelValidator(ValidationProvider):
    """Validates channel/data flow connections between nodes."""

    name = "channel"

    def __init__(self, element_registry: ElementRegistry = None, *args, **kwargs):
        # Extract element_registry from kwargs if not provided as positional arg
        if element_registry is None:
            element_registry = kwargs.get("element_registry")

        if element_registry is None:
            raise ValueError("ChannelValidator requires element_registry parameter")

        # Build matrix from registry
        matrix = MatrixBuilder(element_registry).build()
        self._analyzer = ChannelAnalyzer(matrix)

    def validate(self, plan: GraphPlan) -> ValidationReport:
        details, messages = self._analyzer.analyze(plan)

        # Overall validation fails if any individual path is invalid
        is_valid = all(pv.is_valid for pv in details.path_validations.values())

        return ValidationReport(
            validator_name=self.name, is_valid=is_valid, messages=messages, details=details
        )
