from typing import Any

import httpx
from global_utils.constants import INTERNAL_AUTH_HEADER
from pydantic import HttpUrl

from lumora.elements.ports.retrieval import BaseRetriever
from lumora.elements.ports.retrieval_identity import RetrievalIdentity


class SlackRetriever(BaseRetriever):
    """
    Calls an external Slack-query API to fetch matching messages.

    Depends on ``RetrievalIdentity`` (Protocol) for access control —
    knows nothing about ``ExecutionContext`` or holders.
    """

    def __init__(
        self,
        api_url: HttpUrl,
        top_k_results: int,
        threshold: float,
        timeout: float = 30.0,
        identity: RetrievalIdentity | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        self.api_url = str(api_url)
        self.top_k = top_k_results
        self.threshold = threshold
        self.timeout = timeout
        self._identity = identity
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    _AUTH_HEADER = INTERNAL_AUTH_HEADER

    async def retrieve(self, query: str) -> Any:
        user_id = self._identity.identity_id if self._identity else ""

        params = {
            "query": query,
            "top_k_results": self.top_k,
        }

        headers = {self._AUTH_HEADER: user_id} if user_id else {}

        resp = await self._client.get(
            self.api_url, params=params, headers=headers, timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()
        if "search_results" in data:
            data = data["search_results"]
        if isinstance(data, list):
            return [item for item in data if item.get("score", 0.0) >= self.threshold]
        return data

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
