"""WorkPlan lifecycle hooks."""

from abc import ABC, abstractmethod
from enum import StrEnum

from lumora.elements.workloads.domain.models import WorkPlan


class WorkPlanHookPoint(StrEnum):
    """Lifecycle points where hooks are triggered."""

    POST_SAVE = "on_post_save"
    POST_LOAD = "on_post_load"
    POST_DELETE = "on_post_delete"


class WorkPlanHook(ABC):
    """Base interface for workplan hooks."""

    @abstractmethod
    def on_post_save(self, plan: WorkPlan, context: dict) -> None:
        """Called after plan is saved successfully."""
        pass

    @abstractmethod
    def on_post_load(self, plan: WorkPlan | None, context: dict) -> None:
        """Called after plan is loaded (None if not found)."""
        pass

    @abstractmethod
    def on_post_delete(self, context: dict) -> None:
        """Called after plan is deleted."""
        pass


class BaseWorkPlanHook(WorkPlanHook):
    """Base implementation with no-op methods. Inherit and override what you need."""

    def on_post_save(self, plan: WorkPlan, context: dict) -> None:
        pass

    def on_post_load(self, plan: WorkPlan | None, context: dict) -> None:
        pass

    def on_post_delete(self, context: dict) -> None:
        pass
