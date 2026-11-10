"""
auth.sign_out — revoke a stored credential.

Deletes the credential from the store and returns form_updates
to clear auth-related form fields.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import Field

from lumora.async_work import await_owned
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from lumora.services.auth.service import AuthService

logger = logging.getLogger(__name__)


class SignOutInput(BaseActionInput):
    user_id: str = Field(default="")
    server_identifier: str = Field(default="")


class SignOutOutput(BaseActionOutput):
    signed_out: bool = False
    form_updates: dict[str, Any] = Field(default_factory=dict)


class SignOutAction(BaseAction[SignOutInput, SignOutOutput]):
    uid = "auth.sign_out"
    name = "sign_out"
    description = "Revoke a stored credential"
    action_type = ActionType.VALIDATION
    input_schema = SignOutInput
    output_schema = SignOutOutput
    version = "1.0.0"
    tags = frozenset({"auth", "credential"})
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
        self, input_data: SignOutInput, context: ActionContext | None = None
    ) -> SignOutOutput:
        if not input_data.user_id or not input_data.server_identifier:
            return SignOutOutput(success=False, message="Missing required fields")
        if self._auth is None:
            return SignOutOutput(success=False, message="Authentication is not configured")

        await await_owned(
            asyncio.to_thread(
                self._auth.delete_credential, input_data.user_id, input_data.server_identifier
            )
        )

        logger.info(
            "Credential deleted for user=%s server=%s",
            input_data.user_id,
            input_data.server_identifier,
        )

        return SignOutOutput(
            success=True,
            message="Signed out",
            signed_out=True,
            form_updates={
                "credential_token": "",
                "server_identifier": "",
                "scheme_type": "",
            },
        )
