"""
auth.list_servers — return auth options for a provider category.

Returns static entries (none, access_token) merged with dynamic entries
from the auth server registry. This powers a single dropdown where the
user picks their auth method directly.
"""

from __future__ import annotations

import asyncio
import logging

from pydantic import Field

from mas.application.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from mas.core.async_work import await_owned
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.core.auth.service import AuthService
from mas.core.enums import ResourceCategory

logger = logging.getLogger(__name__)

_STATIC_OPTIONS: list[dict[str, str]] = [
    {"label": "None", "value": StaticAuthMethod.NONE.value},
    {"label": "Access Token", "value": StaticAuthMethod.ACCESS_TOKEN.value},
]


class ListServersInput(BaseActionInput):
    category: str = Field(default="", description="Filter servers by category (e.g. 'a2a', 'mcp')")


class ListServersOutput(BaseActionOutput):
    servers: list[dict[str, str]] = Field(default_factory=list)


class ListServersAction(BaseAction[ListServersInput, ListServersOutput]):
    uid = "auth.list_servers"
    name = "list_servers"
    description = "List available auth options (static + registry) by category"
    action_type = ActionType.DISCOVERY
    input_schema = ListServersInput
    output_schema = ListServersOutput
    version = "1.0.0"
    tags = frozenset({"auth", "registry"})
    elements = frozenset(
        {
            (ResourceCategory.NODE.value, "a2a_agent_node"),
            (ResourceCategory.PROVIDER.value, "a2a_agent"),
            (ResourceCategory.PROVIDER.value, "mcp_server"),
        }
    )

    def __init__(self, auth_service: AuthService | None = None):
        super().__init__()
        self._auth = auth_service

    async def execute(
        self,
        input_data: ListServersInput,
        context: ActionContext | None = None,
    ) -> ListServersOutput:
        category = input_data.category
        if not category:
            return ListServersOutput(
                success=False,
                message="Category is required",
                servers=[],
            )

        servers: list[dict[str, str]] = list(_STATIC_OPTIONS)

        if self._auth:
            configs = await await_owned(asyncio.to_thread(self._auth.list_server_configs, category))
            for c in configs:
                servers.append(
                    {
                        "label": c.display_name or c.server_identifier,
                        "value": c.server_identifier,
                    }
                )

        return ListServersOutput(
            success=True,
            message=f"Found {len(servers)} option(s)",
            servers=servers,
        )
