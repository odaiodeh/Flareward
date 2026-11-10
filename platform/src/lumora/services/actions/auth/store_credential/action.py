"""
auth.store_credential — persist a user-provided credential.

Used by auth elements where the user supplies the secret directly (API key,
bearer token, etc.) as opposed to OAuth flows where the credential arrives
via external callback.

Connectivity validation is NOT performed here — that responsibility belongs
to the consumer (e.g. mcp.validate_connection) which knows the transport
protocol and can verify the credential properly.
"""

from __future__ import annotations

import asyncio
import logging

from pydantic import Field, SecretStr

from lumora.async_work import await_owned
from lumora.resources.domain.categories import (
    AuthErrorCode,
    AuthStatus,
    ResourceCategory,
    SchemeType,
)
from lumora.services.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from lumora.services.auth.credentials.models import StoredCredential, TokenStatus
from lumora.services.auth.service import AuthService

logger = logging.getLogger(__name__)


class StoreCredentialInput(BaseActionInput):
    user_id: str = Field(default="", description="User storing the credential")
    server_url: str = Field(
        default="", description="Server URL this credential authenticates against"
    )
    credential: SecretStr = Field(
        default=SecretStr(""), description="The secret value (API key, token, etc.)"
    )
    scheme_type: str = Field(default=SchemeType.API_KEY, description="Auth scheme type")


class StoreCredentialOutput(BaseActionOutput):
    status: AuthStatus = AuthStatus.ERROR
    authenticated: bool = False
    error_code: AuthErrorCode | None = None


class StoreCredentialAction(BaseAction[StoreCredentialInput, StoreCredentialOutput]):
    uid = "auth.store_credential"
    name = "store_credential"
    description = "Store a user-provided credential for a server"
    action_type = ActionType.VALIDATION
    input_schema = StoreCredentialInput
    output_schema = StoreCredentialOutput
    version = "1.0.0"
    tags = frozenset({"auth", "credential"})
    elements = frozenset(
        {
            (ResourceCategory.PROVIDER.value, "mcp_server"),
        }
    )

    def __init__(self, auth_service: AuthService | None = None):
        super().__init__()
        self._auth = auth_service

    async def execute(
        self,
        input_data: StoreCredentialInput,
        context: ActionContext | None = None,
    ) -> StoreCredentialOutput:
        user_id = input_data.user_id
        server_url = input_data.server_url
        credential = input_data.credential.get_secret_value()
        scheme = input_data.scheme_type

        if not user_id:
            return StoreCredentialOutput(
                success=False,
                message="User ID is required",
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.MISSING_USER_ID,
            )

        if not server_url:
            return StoreCredentialOutput(
                success=False,
                message="Server URL is required",
                status=AuthStatus.NOT_CONFIGURED,
                error_code=AuthErrorCode.MISSING_SERVER_ID,
            )

        if not credential:
            return StoreCredentialOutput(
                success=False,
                message="Credential value is required",
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.UNKNOWN,
            )

        if not self._auth:
            return StoreCredentialOutput(
                success=False,
                message="Auth service is not available",
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.AUTH_SERVICE_UNAVAILABLE,
            )

        await await_owned(
            asyncio.to_thread(
                self._auth.save_credential,
                StoredCredential(
                    user_id=user_id,
                    server_identifier=server_url,
                    access_token=credential,
                    scheme_type=scheme,
                    status=TokenStatus.ACTIVE,
                    expires_at=None,
                ),
            )
        )

        logger.info(
            "Credential stored for user=%s server=%s scheme=%s",
            user_id,
            server_url,
            scheme,
        )

        return StoreCredentialOutput(
            success=True,
            message="Credential stored",
            status=AuthStatus.AUTHENTICATED,
            authenticated=True,
        )
