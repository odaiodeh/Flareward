import time

import httpx
from mas.application.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from mas.core.enums import ResourceCategory
from mas.elements.providers.rag_client.identifiers import Identifier
from pydantic import HttpUrl

from outbound.actions.providers.rag.client import RagActionClient


class ValidateConnectionInput(BaseActionInput):
    """Input for RAG connection validation"""

    base_url: HttpUrl


class ValidateConnectionOutput(BaseActionOutput):
    """Output for RAG connection validation"""

    is_reachable: bool = False
    response_time_ms: float = 0.0


class ValidateConnectionAction(BaseAction[ValidateConnectionInput, ValidateConnectionOutput]):
    """
    Validates RAG server connection.
    """

    uid = "rag.validate_connection"
    name = "validate_connection"
    description = "Validate that the RAG server endpoint is reachable"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "1.0.0"
    tags = frozenset({"rag", "validation", "connectivity"})
    elements = frozenset({(ResourceCategory.PROVIDER.value, Identifier.TYPE)})

    def __init__(self, client: RagActionClient) -> None:
        self._client = client

    async def execute(
        self, input_data: ValidateConnectionInput, context: ActionContext | None = None
    ) -> ValidateConnectionOutput:
        started = time.monotonic()
        try:
            health = await self._client.health(str(input_data.base_url))
            return ValidateConnectionOutput(
                success=health.is_healthy,
                message=health.message,
                is_reachable=health.is_healthy,
                response_time_ms=(time.monotonic() - started) * 1000,
            )
        except httpx.HTTPError:
            return ValidateConnectionOutput(success=False, message="RAG connection failed")
