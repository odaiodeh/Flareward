import asyncio

from mas.application.ports.retrieval import BaseRetriever
from mas.application.ports.retrieval_identity import RetrievalIdentity
from mas.core.async_work import await_owned
from mas.elements.providers.rag_client.config import RagProviderConfig
from mas.elements.providers.rag_client.rag_provider_factory import RagProviderFactory


class DocsRagRetriever(BaseRetriever):
    """
    Retrieves document passages via RAG vector database.

    Depends on ``RetrievalIdentity`` (Protocol) for access control —
    knows nothing about ``ExecutionContext`` or holders.
    """

    def __init__(
        self,
        top_k_results: int,
        threshold: float,
        timeout: float = 30.0,
        docs: list[dict] | None = None,
        tags: list[str] | None = None,
        identity: RetrievalIdentity | None = None,
    ):
        self.threshold = threshold
        self.docs = docs
        self.tags = tags
        self._identity = identity
        config = RagProviderConfig(
            top_k=top_k_results,
            timeout=timeout,
        )
        factory = RagProviderFactory()
        self._provider = factory.create(config)

    async def retrieve(self, query: str) -> list[dict]:
        user_id = self._identity.identity_id if self._identity else ""
        doc_ids = [doc["id"] for doc in self.docs] if self.docs else None

        response = await await_owned(
            asyncio.to_thread(
                self._provider.query,
                query=query,
                doc_ids=doc_ids,
                tags=self.tags,
                authenticated_user=user_id,
            )
        )

        return [match.model_dump() for match in response.matches if match.score >= self.threshold]
