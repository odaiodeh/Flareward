from pydantic import HttpUrl, JsonValue

from flareward.resources.domain.categories import ResourceCategory
from flareward.services.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from plugins.a2a.elements.a2a_agent.identifiers import Identifier
from plugins.a2a.elements.a2a_client import A2AClient


# Input/Output models for this action
class GetAgentCardInput(BaseActionInput):
    """Input for A2A agent card discovery"""

    base_url: HttpUrl


class GetAgentCardOutput(BaseActionOutput):
    """Output for A2A agent card discovery"""

    agent_card: dict[str, JsonValue] | None = None


class GetAgentCardAction(BaseAction[GetAgentCardInput, GetAgentCardOutput]):
    """
    Discovers agent card from A2A agent endpoint.

    Returns the agent card as portable JSON; SDK model instances stay in this adapter.
    The agent card contains all agent metadata including identity,
    skills, capabilities, and any other fields defined by the SDK.

    Single Responsibility: Only discovers and returns the agent card
    """

    uid = "a2a.get_agent_card"
    name = "get_agent_card"
    description = "Retrieve the agent card from an A2A agent endpoint"
    action_type = ActionType.DISCOVERY
    input_schema = GetAgentCardInput
    output_schema = GetAgentCardOutput
    version = "1.0.0"
    tags = frozenset({"a2a", "discovery", "agent-card", "skills"})
    elements = frozenset({(ResourceCategory.NODE.value, Identifier.TYPE)})

    async def execute(
        self, input_data: GetAgentCardInput, context: ActionContext | None = None
    ) -> GetAgentCardOutput:
        """
        Execute agent card discovery asynchronously.

        Args:
            input_data: Validated discovery input with base_url and optional bearer_token
            context: Optional execution context

        Returns:
            Discovery result with complete agent card
        """
        # Build headers from bearer_token if provided
        headers = None
        # if input_data.bearer_token:
        #     headers = {"Authorization": f"Bearer {input_data.bearer_token}"}

        try:
            # Create A2A client and fetch agent card
            async with A2AClient(base_url=input_data.base_url, headers=headers) as client:
                agent_card = client.agent_card

            # Convert the protocol response before crossing the application boundary
            return GetAgentCardOutput(
                success=True,
                message=f"Successfully retrieved agent card for '{agent_card.name}'",
                agent_card=agent_card.model_dump(mode="json", by_alias=True),
            )

        except Exception:
            return GetAgentCardOutput(
                success=False, message="Failed to retrieve agent card", agent_card=None
            )
