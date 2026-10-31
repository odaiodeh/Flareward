"""
elements/nodes/a2a_agent/validator.py

Validator for A2A Agent Node — real agent-card probe with auth awareness.

Aligns with MCP card-grid validation: missing/expired SSO or rejected
credentials produce INVALID_CREDENTIALS (yellow invalid on the card).
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import CancelledError

from global_utils.utils.async_bridge import get_async_bridge

from mas.application.elements.validation import (
    BaseElementValidator,
    ElementValidationResult,
    ValidationCode,
    ValidationContext,
    ValidationMessage,
    ValidatorReport,
)
from mas.core.async_work import await_owned
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.core.auth.errors import AuthError
from mas.core.ref.models import Ref
from mas.elements.nodes.a2a_agent.config import A2AAgentNodeConfig
from mas.elements.providers.a2a_client import A2AClient

logger = logging.getLogger(__name__)


class A2AAgentNodeValidator(BaseElementValidator):
    """
    Validates A2A Agent Node configuration.

    Checks:
    - Auth credential state (access token / SSO) when required
    - A2A agent endpoint connectivity (agent card fetch)
    - Retriever dependency (if configured)
    """

    def validate(self, config: A2AAgentNodeConfig, context: ValidationContext) -> ValidatorReport:
        """Retained synchronous entry point; native callers await validate_async directly."""
        try:
            with get_async_bridge() as bridge:
                return bridge.run(self.validate_async(config, context))
        except CancelledError, TimeoutError:
            return self._report(
                config,
                context,
                [
                    self._error(
                        ValidationCode.NETWORK_TIMEOUT.value,
                        "Connection probe timed out",
                        field="base_url",
                    )
                ],
            )

    async def validate_async(
        self, config: A2AAgentNodeConfig, context: ValidationContext
    ) -> ValidatorReport:
        messages: list[ValidationMessage] = []
        operation = asyncio.create_task(self._check_connection(config, context, messages))
        try:
            async with asyncio.timeout(context.timeout_seconds):
                await await_owned(operation, on_cancel=operation.cancel)
        except TimeoutError:
            messages.append(
                self._error(
                    ValidationCode.NETWORK_TIMEOUT.value,
                    "Connection probe timed out",
                    field="base_url",
                )
            )
        return self._report(config, context, messages)

    def _report(
        self,
        config: A2AAgentNodeConfig,
        context: ValidationContext,
        messages: list[ValidationMessage],
    ) -> ValidatorReport:
        dependencies: dict[str, ElementValidationResult] = {}
        if config.retriever:
            self._check_dependency(
                context, self._extract_rid(config.retriever), "retriever", messages, dependencies
            )
        return self._build_report(messages, dependencies)

    async def _resolve_headers(
        self,
        config: A2AAgentNodeConfig,
        context: ValidationContext,
    ) -> tuple[dict[str, str] | None, str | None]:
        """
        Build probe headers from config + AuthService.

        Returns (headers, auth_error_message). When auth_error_message is set,
        the card should report INVALID_CREDENTIALS.
        """
        auth_method = config.auth_method or StaticAuthMethod.NONE.value

        if auth_method == StaticAuthMethod.NONE.value:
            return None, None

        if auth_method == StaticAuthMethod.ACCESS_TOKEN.value:
            raw = config.bearer_token or config.credential_token or ""
            if not raw:
                return None, ("Bearer token required — provide a token or sign in")
            token = context.auth_service.unseal_token(raw) if context.auth_service else raw
            if not token:
                return None, ("Bearer token required — provide a token or sign in")
            return {"Authorization": f"Bearer {token}"}, None

        # Registry SSO — AuthService is source of truth (expiry + refresh).
        server_id = (config.server_identifier or "").strip() or auth_method
        if not context.auth_service or not server_id:
            return None, "Session expired — sign in again"

        lookup_user = context.credential_lookup_user_id()
        if not lookup_user:
            return None, "Session expired — sign in again"

        auth_cred = await context.auth_service.bind_async(
            lookup_user,
            server_id,
            scheme_type=config.scheme_type or "",
        )
        if not auth_cred:
            return None, "Session expired — sign in again"

        try:
            headers = await auth_cred.get_headers()
        except AuthError:
            return None, "Session expired — sign in again"
        except Exception:
            logger.warning(
                "A2A validator: failed to resolve auth headers server_identifier=%r",
                server_id,
            )
            return None, "Session expired — sign in again"

        if not headers:
            return None, "Session expired — sign in again"
        return dict(headers), None

    async def _check_connection(
        self,
        config: A2AAgentNodeConfig,
        context: ValidationContext,
        messages: list[ValidationMessage],
    ) -> None:
        """Async A2A connection check using A2AClient with auth headers."""
        headers, auth_error = await self._resolve_headers(config, context)
        if auth_error:
            messages.append(
                self._error(
                    ValidationCode.INVALID_CREDENTIALS.value,
                    auth_error,
                    field="base_url",
                )
            )
            return

        try:
            async with A2AClient(
                base_url=config.base_url,
                headers=headers,
            ) as client:
                _ = client.agent_card

            messages.append(
                self._info(
                    "CONNECTION_OK",
                    "Successfully connected to A2A agent",
                    field="base_url",
                )
            )

        except TimeoutError:
            messages.append(
                self._error(
                    ValidationCode.NETWORK_TIMEOUT.value,
                    f"Connection timed out after {context.timeout_seconds}s",
                    field="base_url",
                )
            )
        except Exception as e:
            error_msg = str(e)
            error_l = error_msg.lower()
            if "401" in error_l or "unauthorized" in error_l:
                messages.append(
                    self._error(
                        ValidationCode.INVALID_CREDENTIALS.value,
                        "Server rejected the credentials; sign in again or update your token",
                        field="base_url",
                    )
                )
            elif "403" in error_l or "forbidden" in error_l:
                messages.append(
                    self._error(
                        ValidationCode.INVALID_CREDENTIALS.value,
                        "Not authorized; check your scopes or contact the administrator",
                        field="base_url",
                    )
                )
            else:
                messages.append(
                    self._error(
                        ValidationCode.ENDPOINT_UNREACHABLE.value,
                        "Connection probe failed",
                        field="base_url",
                    )
                )

    @staticmethod
    def _extract_rid(ref_obj) -> str:
        """Extract rid string from Ref or string."""
        if isinstance(ref_obj, Ref):
            return ref_obj.ref
        return str(ref_obj)
