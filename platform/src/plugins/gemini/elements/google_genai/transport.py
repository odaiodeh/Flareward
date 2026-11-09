"""Own streamed HTTP responses independently of GenAI's nested generators."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from contextvars import ContextVar

import httpx
from google.genai.types import HttpOptions

from flareward.async_work import await_owned


class GenAITransport:
    def __init__(self, options: HttpOptions) -> None:
        self._owned = options.httpx_async_client is None
        self.client = options.httpx_async_client or httpx.AsyncClient(
            **(options.async_client_args or {})
        )
        self.options = options.model_copy(update={"httpx_async_client": self.client})
        self._responses: ContextVar[AsyncExitStack | None] = ContextVar(
            "genai_stream_responses", default=None
        )
        self.client.event_hooks.setdefault("response", []).append(self._capture)

    async def _capture(self, response: httpx.Response) -> None:
        responses = self._responses.get()
        if responses is not None:
            responses.push_async_callback(response.aclose)

    @asynccontextmanager
    async def stream(self) -> AsyncIterator[None]:
        responses = AsyncExitStack()
        token = self._responses.set(responses)
        try:
            yield
        finally:
            self._responses.reset(token)
            await await_owned(responses.aclose())

    async def aclose(self) -> None:
        self.client.event_hooks["response"].remove(self._capture)
        if self._owned:
            await self.client.aclose()
