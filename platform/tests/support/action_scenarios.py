"""Application-only action fixtures shared by service and HTTP contracts."""

from flareward.services.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)


class IdentityInput(BaseActionInput):
    user_id: str = ""
    count: int = 1


class IdentityOutput(BaseActionOutput):
    actor: str
    owner: str
    count: int


class IdentityAction(BaseAction[IdentityInput, IdentityOutput]):
    uid = "fixture.identity"
    name = "identity"
    description = "Verify trusted authoring context"
    action_type = ActionType.UTILITY
    input_schema = IdentityInput
    output_schema = IdentityOutput
    elements = frozenset({("nodes", "fixture")})
    tags = frozenset({"fixture", "identity"})

    async def execute(self, input_data: IdentityInput, context: ActionContext) -> IdentityOutput:
        return IdentityOutput(
            success=True,
            message="Context checked",
            actor=input_data.user_id,
            owner=context.owner.id,
            count=input_data.count,
        )


class FailingAction(IdentityAction):
    uid = "fixture.failure"

    async def execute(self, input_data: IdentityInput, context: ActionContext) -> IdentityOutput:
        raise RuntimeError("private-provider-credential")


class InvalidOutputAction(IdentityAction):
    uid = "fixture.invalid-output"

    async def execute(self, input_data: IdentityInput, context: ActionContext):
        return {"private": "private-invalid-result"}
