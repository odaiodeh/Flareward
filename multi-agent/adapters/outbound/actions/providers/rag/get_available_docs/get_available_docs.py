from typing import Any

from mas.application.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from mas.core.enums import ResourceCategory

from outbound.actions.providers.rag.client import RagActionClient


class GetAvailableDocsInput(BaseActionInput):
    """Input for fetching available documents"""

    user_id: str = ""
    limit: int = 50
    cursor: str | None = None
    search_regex: str | None = None


class GetAvailableDocsOutput(BaseActionOutput):
    """Output for available documents"""

    documents: list[dict[str, Any]] = []
    next_cursor: str | None = None
    has_more: bool = False
    total: int = 0


class GetAvailableDocsAction(BaseAction[GetAvailableDocsInput, GetAvailableDocsOutput]):
    """
    Fetches available documents from RAG service asynchronously.
    """

    uid = "rag.get_available_docs"
    name = "get_available_docs"
    description = "Retrieve available document sources from the RAG service"
    action_type = ActionType.DISCOVERY
    input_schema = GetAvailableDocsInput
    output_schema = GetAvailableDocsOutput
    version = "1.0.0"
    tags = frozenset({"rag", "discovery", "docs", "documents"})
    elements = frozenset(
        {
            (ResourceCategory.PROVIDER.value, "rag_client"),
            (ResourceCategory.RETRIEVER.value, "docs_rag"),
        }
    )

    def __init__(self, provider: RagActionClient) -> None:
        self._provider = provider

    async def execute(
        self, input_data: GetAvailableDocsInput, context: ActionContext | None = None
    ) -> GetAvailableDocsOutput:
        """Execute docs discovery asynchronously."""
        try:
            response = await self._provider.get_available_docs(
                limit=input_data.limit,
                cursor=input_data.cursor,
                search_regex=input_data.search_regex,
                authenticated_user=input_data.user_id,
            )

            return GetAvailableDocsOutput(
                success=True,
                message=f"Found {response.total} documents",
                documents=[doc.model_dump() for doc in response.documents],
                next_cursor=response.nextCursor,
                has_more=response.hasMore,
                total=response.total,
            )

        except Exception:
            return GetAvailableDocsOutput(
                success=False, message="Failed to retrieve documents", documents=[], total=0
            )
