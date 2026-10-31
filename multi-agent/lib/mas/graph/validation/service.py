from collections.abc import Iterable

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.graph.graph_plan import GraphPlan

from .channel.fix_provider import ChannelFixProvider
from .channel.validator import ChannelValidator
from .cycle.fix_provider import CycleFixProvider
from .cycle.validator import CycleValidator
from .dependency.fix_provider import DependencyFixProvider
from .dependency.validator import DependencyValidator
from .fix_models import FixSuggestion
from .interfaces import FixSuggestionProvider, ValidationProvider
from .models import ValidationReport, ValidationResult
from .orchestrator.validator import OrchestratorValidator
from .orphan.fix_provider import OrphanFixProvider
from .orphan.validator import OrphanValidator
from .required_nodes.fix_provider import RequiredNodesFixProvider
from .required_nodes.validator import RequiredNodesValidator
from .settings import ValidationSettings


class GraphValidationService:
    """Orchestrates validation and fix suggestion providers."""

    def __init__(
        self,
        element_registry: ElementRegistry,
        settings: ValidationSettings | None = None,
        *,
        validators: Iterable[ValidationProvider] | None = None,
        fix_providers: Iterable[FixSuggestionProvider] | None = None,
    ) -> None:
        self._settings = (settings or ValidationSettings()).model_copy(deep=True)
        self._validation_providers = (
            tuple(validators)
            if validators is not None
            else (
                DependencyValidator(),
                CycleValidator(),
                OrphanValidator(),
                ChannelValidator(element_registry),
                RequiredNodesValidator(self._settings),
                OrchestratorValidator(),
            )
        )
        self._fix_providers = (
            tuple(fix_providers)
            if fix_providers is not None
            else (
                ChannelFixProvider(element_registry),
                CycleFixProvider(),
                DependencyFixProvider(),
                OrphanFixProvider(),
                RequiredNodesFixProvider(self._settings),
            )
        )
        for providers in (self._validation_providers, self._fix_providers):
            names = [provider.name for provider in providers]
            if any(not name for name in names) or len(names) != len(set(names)):
                raise ValueError("Graph providers require distinct nonempty names")

    def validate_all(self, plan: GraphPlan) -> ValidationResult:
        """Run all validators and return aggregate result."""
        reports = [provider.validate(plan) for provider in self._validation_providers]
        is_valid = all(report.is_valid for report in reports)

        return ValidationResult(is_valid=is_valid, reports=reports)

    def get_validator(self, name: str) -> ValidationProvider | None:
        """Get validator by name."""
        return next((v for v in self._validation_providers if v.name == name), None)

    def run_validator(self, name: str, plan: GraphPlan) -> ValidationReport:
        """Run specific validator by name."""
        validator = self.get_validator(name)
        if not validator:
            raise ValueError("Unknown graph validator")
        return validator.validate(plan)

    def suggest_fixes(
        self, plan: GraphPlan, validation_result: ValidationResult | None = None
    ) -> list[FixSuggestion]:
        """Get fix suggestions from all providers."""
        suggestions = []

        # Create report lookup for providers that can use validation context
        report_map = {}
        if validation_result:
            report_map = {report.validator_name: report for report in validation_result.reports}

        for provider in self._fix_providers:
            # Pass the matching validation report if available
            matching_report = report_map.get(provider.name)
            provider_suggestions = provider.suggest_fixes(plan, matching_report)
            suggestions.extend(provider_suggestions)

        return suggestions

    def validate_and_suggest(
        self, plan: GraphPlan, name: str | None = None
    ) -> tuple[ValidationResult | ValidationReport, list[FixSuggestion]]:
        """Convenience method to validate and get suggestions in one call."""
        if name is not None:
            report = self.run_validator(name, plan)
            return report, self._get_suggestions_for_provider(name, plan, report)
        validation_result = self.validate_all(plan)
        suggestions = self.suggest_fixes(plan, validation_result)
        return validation_result, suggestions

    def _get_suggestions_for_provider(
        self, provider_name: str, plan: GraphPlan, validation_report: ValidationReport
    ) -> list[FixSuggestion]:
        """Get fix suggestions from a specific provider."""
        for provider in self._fix_providers:
            if provider.name == provider_name:
                return provider.suggest_fixes(plan, validation_report)
        return []

    def validate_dependencies(
        self, plan: GraphPlan
    ) -> tuple[ValidationReport, list[FixSuggestion]]:
        """Validate dependencies and get fix suggestions."""
        validation_report = self.run_validator("dependency", plan)
        suggestions = self._get_suggestions_for_provider("dependency", plan, validation_report)
        return validation_report, suggestions

    def validate_cycles(self, plan: GraphPlan) -> tuple[ValidationReport, list[FixSuggestion]]:
        """Validate cycles and get fix suggestions."""
        validation_report = self.run_validator("cycle", plan)
        suggestions = self._get_suggestions_for_provider("cycle", plan, validation_report)
        return validation_report, suggestions

    def validate_orphans(self, plan: GraphPlan) -> tuple[ValidationReport, list[FixSuggestion]]:
        """Validate orphans and get fix suggestions."""
        validation_report = self.run_validator("orphan", plan)
        suggestions = self._get_suggestions_for_provider("orphan", plan, validation_report)
        return validation_report, suggestions

    def validate_channels(self, plan: GraphPlan) -> tuple[ValidationReport, list[FixSuggestion]]:
        """Validate channels and get fix suggestions."""
        validation_report = self.run_validator("channel", plan)
        suggestions = self._get_suggestions_for_provider("channel", plan, validation_report)
        return validation_report, suggestions

    def validate_required_nodes(
        self, plan: GraphPlan
    ) -> tuple[ValidationReport, list[FixSuggestion]]:
        """Validate required nodes and get fix suggestions."""
        validation_report = self.run_validator("required_nodes", plan)
        suggestions = self._get_suggestions_for_provider("required_nodes", plan, validation_report)
        return validation_report, suggestions

    def get_validation_names(self) -> list[str]:
        """Get list of all available validation names."""
        return [provider.name for provider in self._validation_providers]
