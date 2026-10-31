"""Explicit contracts for graph validation and fix suggestions."""

from abc import ABC, abstractmethod

from mas.graph.graph_plan import GraphPlan

from .fix_models import FixSuggestion
from .models import ValidationReport


class ValidationProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Stable registered name for this check."""

    @abstractmethod
    def validate(self, plan: GraphPlan) -> ValidationReport:
        """Validate graph metadata without constructing executable elements."""


class FixSuggestionProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the validation check whose report this provider consumes."""

    @abstractmethod
    def suggest_fixes(
        self, plan: GraphPlan, validation_report: ValidationReport | None = None
    ) -> list[FixSuggestion]:
        """Suggest fixes without mutating the plan."""
