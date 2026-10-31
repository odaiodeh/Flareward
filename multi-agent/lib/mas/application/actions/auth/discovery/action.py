"""
auth.discovery — discover auth requirements and initiate sign-in.

Shared by both MCP and A2A elements.  Two entry paths:

1. **MCP** — ``mcp_url`` is provided; the action auto-detects the auth
   server via well-known metadata, then checks for an existing credential
   or initiates OAuth.
2. **A2A** — ``server_identifier`` is provided directly (selected from
   the auth-server dropdown); the action checks for an existing credential
   or initiates OAuth against that server.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import Field

from mas.application.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from mas.core.async_work import await_owned
from mas.core.auth.service import AuthService
from mas.core.enums import AuthErrorCode, AuthStatus, ResourceCategory

logger = logging.getLogger(__name__)


class DiscoveryInput(BaseActionInput):
    user_id: str = Field(default="")
    mcp_url: str = Field(default="")
    server_identifier: str = Field(default="")


class DiscoveryOutput(BaseActionOutput):
    status: AuthStatus = AuthStatus.NOT_CONFIGURED
    authenticated: bool = False
    server_identifier: str = ""
    scheme_type: str = ""
    challenge: dict[str, Any] | None = None
    error_code: AuthErrorCode | None = None
    form_updates: dict[str, Any] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)


class DiscoveryAction(BaseAction[DiscoveryInput, DiscoveryOutput]):
    uid = "auth.discovery"
    name = "discovery"
    description = "Discover auth requirements and initiate sign-in"
    action_type = ActionType.VALIDATION
    input_schema = DiscoveryInput
    output_schema = DiscoveryOutput
    version = "1.0.0"
    tags = frozenset({"auth", "discovery"})
    elements = frozenset(
        {
            (ResourceCategory.PROVIDER.value, "mcp_server"),
            (ResourceCategory.NODE.value, "a2a_agent_node"),
            (ResourceCategory.PROVIDER.value, "a2a_agent"),
        }
    )

    def __init__(self, auth_service: AuthService | None = None):
        super().__init__()
        self._auth = auth_service

    async def execute(
        self, input_data: DiscoveryInput, context: ActionContext | None = None
    ) -> DiscoveryOutput:
        user_id = input_data.user_id
        server_id = input_data.server_identifier

        if not user_id:
            return DiscoveryOutput(
                success=False,
                message="User ID required",
                error_code=AuthErrorCode.MISSING_USER_ID,
            )
        if self._auth is None:
            return DiscoveryOutput(
                success=False,
                message="Authentication is not configured",
                error_code=AuthErrorCode.AUTH_SERVICE_UNAVAILABLE,
            )

        # Step 1: Discover if server_identifier unknown
        if not server_id:
            if not input_data.mcp_url:
                return DiscoveryOutput(
                    success=False,
                    message="MCP URL required",
                    error_code=AuthErrorCode.MISSING_SERVER_ID,
                )
            detection = await self._auth.discover(input_data.mcp_url)
            if not detection:
                return DiscoveryOutput(
                    success=False,
                    message="No authentication requirements detected",
                )
            server_id = detection.server_identifier
            scheme_type = detection.protocol_type
        else:
            cred = await await_owned(
                asyncio.to_thread(self._auth.get_credential, user_id, server_id)
            )
            scheme_type = cred.scheme_type if cred else "oauth2"

        # Step 2: Already authenticated?
        token = await self._auth.get_valid_token(user_id, server_id)
        if token:
            sealed = self._auth.seal_token(token)
            return DiscoveryOutput(
                success=True,
                message="Authenticated",
                status=AuthStatus.AUTHENTICATED,
                authenticated=True,
                server_identifier=server_id,
                scheme_type=scheme_type,
                form_updates={
                    "credential_token": sealed,
                    "server_identifier": server_id,
                    "scheme_type": scheme_type,
                },
                actions=[
                    {
                        "uid": "auth.sign_out",
                        "label": "Sign Out",
                        "style": "danger",
                        "dependencies": {
                            "server_identifier": "server_identifier",
                        },
                    }
                ],
            )

        # Step 3: Initiate sign-in
        config = await await_owned(asyncio.to_thread(self._auth.get_client_config, "", server_id))
        login_config = config.model_dump() if config else {}

        try:
            challenge = await self._auth.initiate(
                user_id,
                server_id,
                scheme_type=scheme_type,
                config=login_config,
            )
            return DiscoveryOutput(
                success=True,
                message="Sign in required",
                status=AuthStatus.CHALLENGE,
                server_identifier=server_id,
                scheme_type=scheme_type,
                challenge=challenge.to_response(),
                form_updates={
                    "server_identifier": server_id,
                    "scheme_type": scheme_type,
                },
            )
        except Exception:
            logger.warning("Auth initiation failed")
            return DiscoveryOutput(
                success=False,
                message="Authentication initiation failed",
                server_identifier=server_id,
                error_code=AuthErrorCode.INITIATION_FAILED,
            )
