from mas.application.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from mas.core.enums import ResourceCategory

from outbound.actions.providers.rag.client import RagActionClient


class GetAvailableTagsInput(BaseActionInput):
    """Input for fetching available tags"""

    user_id: str = ""
    limit: int = 50
    cursor: str | None = None
    search_regex: str | None = None


class GetAvailableTagsOutput(BaseActionOutput):
    """Output for available tags"""

    tags: list[str] = []
    next_cursor: str | None = None
    has_more: bool = False
    total: int = 0


class GetAvailableTagsAction(BaseAction[GetAvailableTagsInput, GetAvailableTagsOutput]):
    """
    Fetches available tags from RAG service asynchronously.
    """

    uid = "rag.get_available_tags"
    name = "get_available_tags"
    description = "Retrieve available tags from the RAG service"
    action_type = ActionType.DISCOVERY
    input_schema = GetAvailableTagsInput
    output_schema = GetAvailableTagsOutput
    version = "1.0.0"
    tags = frozenset({"rag", "discovery", "tags"})
    elements = frozenset(
        {
            (ResourceCategory.PROVIDER.value, "rag_client"),
            (ResourceCategory.RETRIEVER.value, "docs_rag"),
        }
    )

    def __init__(self, provider: RagActionClient) -> None:
        self._provider = provider

    async def execute(
        self, input_data: GetAvailableTagsInput, context: ActionContext | None = None
    ) -> GetAvailableTagsOutput:
        """Execute tags discovery asynchronously."""
        try:
            response = await self._provider.get_available_tags(
                limit=input_data.limit,
                cursor=input_data.cursor,
                search_regex=input_data.search_regex,
                authenticated_user=input_data.user_id,
            )

            return GetAvailableTagsOutput(
                success=True,
                message=f"Found {response.total} tags",
                tags=[t.label for t in response.options],
                next_cursor=response.nextCursor,
                has_more=response.hasMore,
                total=response.total,
            )

        except Exception:
            return GetAvailableTagsOutput(
                success=False, message="Failed to retrieve tags", tags=[], total=0
            )
