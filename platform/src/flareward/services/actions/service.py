"""An instance-owned action catalog and typed async dispatch."""

from collections.abc import Iterable
from inspect import iscoroutinefunction
from typing import Any

from pydantic import BaseModel, JsonValue, ValidationError

from flareward.services.actions.contracts import (
    ActionContext,
    ActionMetadata,
    ActionType,
    BaseAction,
)

type RegisteredAction = BaseAction[Any, Any]


class ActionMissing(LookupError):
    pass


class ActionInputInvalid(ValueError):
    pass


class ActionExecutionFailed(RuntimeError):
    pass


class ActionsService:
    def __init__(self, actions: Iterable[RegisteredAction] = ()) -> None:
        self._actions: dict[str, RegisteredAction] = {}
        for action in actions:
            self.register_instance(action)

    def register_instance(self, action: RegisteredAction) -> None:
        if not isinstance(action, BaseAction) or not iscoroutinefunction(action.execute):
            raise TypeError("Action registrations require async action instances")
        if action.uid in self._actions:
            raise ValueError(f"Duplicate action registration: {action.uid}")
        action.get_metadata()
        self._actions[action.uid] = action

    def get_actions_metadata(
        self,
        *,
        action_type: ActionType | None = None,
        tags: set[str] | None = None,
        category: str | None = None,
        element_type: str | None = None,
    ) -> list[ActionMetadata]:
        return [
            action.get_metadata()
            for _, action in sorted(self._actions.items())
            if (action_type is None or action.action_type == action_type)
            and (not tags or tags <= action.tags)
            and (
                (category is None and element_type is None)
                or any(
                    (category is None or c == category)
                    and (element_type is None or t == element_type)
                    for c, t in action.elements
                )
            )
        ]

    async def execute(
        self, uid: str, input_data: dict[str, JsonValue], context: ActionContext
    ) -> BaseModel:
        action = self._actions.get(uid)
        if action is None:
            raise ActionMissing("Action not found")
        arguments = dict(input_data)
        if "user_id" in action.input_schema.model_fields:
            arguments["user_id"] = context.credential_user_id
        try:
            validated = action.input_schema.model_validate(arguments)
        except ValidationError:
            raise ActionInputInvalid("Invalid action input") from None
        try:
            result = await action.execute(validated, context)
            output: type[BaseModel] = action.output_schema
            return output.model_validate(result)
        except Exception:
            raise ActionExecutionFailed("Action execution failed") from None
