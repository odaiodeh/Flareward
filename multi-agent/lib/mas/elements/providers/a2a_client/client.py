"""
A2AClient - Wrapper around official A2A SDK.

Uses BaseHandler to convert SDK responses to A2AResult.
"""

from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver
from a2a.client import A2AClient as SDKA2AClient
from a2a.types import (
    AgentCard,
    CancelTaskRequest,
    CancelTaskResponse,
    CancelTaskSuccessResponse,
    GetTaskRequest,
    GetTaskResponse,
    GetTaskSuccessResponse,
    Message,
    MessageSendParams,
    SendMessageRequest,
    SendMessageResponse,
    SendMessageSuccessResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageSuccessResponse,
    TaskIdParams,
    TaskQueryParams,
)
from pydantic import HttpUrl

from mas.core.async_work import await_owned
from mas.elements.providers.a2a_client.handlers import BaseHandler
from mas.elements.providers.a2a_client.result import A2AResult


class A2AClientError(Exception):
    """Base error for A2A client operations."""

    pass


class A2AConnectionError(A2AClientError):
    """Connection-related errors."""

    pass


class A2AClient:
    """
    A2A Client wrapper.

    Uses BaseHandler to convert SDK responses to A2AResult.
    """

    def __init__(
        self,
        base_url: HttpUrl,
        agent_card: AgentCard | None = None,
        headers: dict[str, str] | None = None,
    ):
        """
        Initialize A2A client.

        Args:
            base_url: A2A agent URL
            agent_card: Pre-fetched agent card (optional)
            headers: HTTP headers for auth (optional)
        """
        self._base_url = str(base_url)
        self._agent_card = agent_card
        self._headers = headers or {}
        self._httpx: httpx.AsyncClient | None = None
        self._sdk: SDKA2AClient | None = None

    async def __aenter__(self) -> A2AClient:
        """Connect to agent."""
        self._httpx = httpx.AsyncClient(
            headers=self._headers,
            timeout=httpx.Timeout(
                connect=10.0,
                read=300.0,
                write=10.0,
                pool=10.0,
            ),
        )
        try:
            await self._httpx.__aenter__()
            if not self._agent_card:
                self._agent_card = await self._fetch_agent_card()

            self._sdk = SDKA2AClient(
                httpx_client=self._httpx,
                agent_card=self._agent_card,
            )
        except BaseException as error:
            await self.__aexit__(type(error), error, error.__traceback__)
            if isinstance(error, Exception):
                raise A2AConnectionError(f"Failed to connect: {error}") from error
            raise

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from agent."""
        client, self._httpx = self._httpx, None
        self._sdk = None
        if client is not None:
            await await_owned(client.__aexit__(exc_type, exc_val, exc_tb))

    async def _fetch_agent_card(self) -> AgentCard:
        """Fetch agent card from server."""
        resolver = A2ACardResolver(
            httpx_client=self._httpx,
            base_url=self._base_url,
        )
        return await resolver.get_agent_card()

    def _require_connected(self) -> None:
        """Ensure client is connected."""
        if not self._sdk:
            raise A2AConnectionError("Not connected. Use 'async with' context manager.")

    @property
    def agent_card(self) -> AgentCard:
        """Get agent card."""
        if not self._agent_card:
            raise A2AConnectionError("Agent card not loaded.")
        return self._agent_card

    @property
    def skills(self) -> list:
        """Get available skill names."""
        if not self._agent_card or not self._agent_card.skills:
            return []
        return [s.name for s in self._agent_card.skills if s.name]

    async def send(self, message: Message) -> A2AResult:
        """
        Send message and get response.

        Args:
            message: SDK Message to send

        Returns:
            A2AResult wrapping response
        """
        self._require_connected()

        request = SendMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(message=message),
        )

        response: SendMessageResponse = await self._sdk.send_message(request)
        return self._handle_send_response(response)

    def _handle_send_response(self, response: SendMessageResponse) -> A2AResult:
        """Handle SendMessageResponse."""
        if isinstance(response.root, SendMessageSuccessResponse):
            result = BaseHandler.handle(response.root.result, is_streaming=False)
            if result:
                return result
            return A2AResult.from_error(message="Unknown response type")

        if hasattr(response.root, "error") and response.root.error:
            return A2AResult.from_error(response.root.error)

        return A2AResult.from_error(message="Unknown error")

    async def stream(self, message: Message) -> AsyncIterator[A2AResult]:
        """
        Stream message and yield responses.

        Args:
            message: SDK Message to send

        Yields:
            A2AResult for each streaming event
        """
        self._require_connected()

        request = SendStreamingMessageRequest(
            id=str(uuid4()),
            params=MessageSendParams(message=message),
        )

        try:
            async for chunk in self._sdk.send_message_streaming(request):
                result = self._handle_stream_chunk(chunk)
                if result:
                    yield result
        except Exception as e:
            yield A2AResult.from_error(message=f"Stream error: {e}")

    def _handle_stream_chunk(self, chunk) -> A2AResult | None:
        """Handle streaming chunk."""
        if hasattr(chunk.root, "error") and chunk.root.error:
            return A2AResult.from_error(chunk.root.error)

        if isinstance(chunk.root, SendStreamingMessageSuccessResponse):
            return BaseHandler.handle(chunk.root.result, is_streaming=True)

        return None

    async def get_task(self, task_id: str) -> A2AResult:
        """
        Get task by ID.

        Args:
            task_id: Task ID to fetch

        Returns:
            A2AResult with task data
        """
        self._require_connected()

        request = GetTaskRequest(
            id=str(uuid4()),
            params=TaskQueryParams(id=task_id),
        )

        response: GetTaskResponse = await self._sdk.get_task(request)

        if isinstance(response.root, GetTaskSuccessResponse):
            return BaseHandler.handle(response.root.result, is_streaming=False)

        if hasattr(response.root, "error") and response.root.error:
            return A2AResult.from_error(response.root.error, task_id=task_id)

        return A2AResult.from_error(message="Failed to get task", task_id=task_id)

    async def cancel_task(self, task_id: str) -> A2AResult:
        """
        Cancel a task.

        Args:
            task_id: Task ID to cancel

        Returns:
            A2AResult with final task state
        """
        self._require_connected()

        request = CancelTaskRequest(
            id=str(uuid4()),
            params=TaskIdParams(id=task_id),
        )

        response: CancelTaskResponse = await self._sdk.cancel_task(request)

        if isinstance(response.root, CancelTaskSuccessResponse):
            return BaseHandler.handle(response.root.result, is_streaming=False)

        if hasattr(response.root, "error") and response.root.error:
            return A2AResult.from_error(response.root.error, task_id=task_id)

        return A2AResult.from_error(message="Failed to cancel task", task_id=task_id)

    def supports_streaming(self) -> bool:
        """Check if agent supports streaming."""
        if not self._agent_card or not self._agent_card.capabilities:
            return False
        return self._agent_card.capabilities.streaming or False

    def supports_push_notifications(self) -> bool:
        """Check if agent supports push notifications."""
        if not self._agent_card or not self._agent_card.capabilities:
            return False
        return self._agent_card.capabilities.push_notifications or False

    def supports_state_history(self) -> bool:
        """Check if agent provides state transition history."""
        if not self._agent_card or not self._agent_card.capabilities:
            return False
        return self._agent_card.capabilities.state_transition_history or False
