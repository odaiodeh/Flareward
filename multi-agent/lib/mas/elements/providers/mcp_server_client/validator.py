"""
elements/providers/mcp_server_client/validator.py

Validator for MCP Provider — uses McpProviderFactory for a real connection probe.

Uses the same transport path as the wizard and runtime (McpProviderFactory),
and resolves auth credentials via ``core/auth`` before probing.
"""

import asyncio
import logging
from concurrent.futures import CancelledError

from global_utils.utils.async_bridge import get_async_bridge

from mas.application.elements.validation import (
    BaseElementValidator,
    ValidationCode,
    ValidationContext,
    ValidationMessage,
    ValidatorReport,
)
from mas.core.async_work import await_owned
from mas.core.auth.errors import AuthError
from mas.elements.providers.mcp_server_client.config import (
    McpAuthMethod,
    McpProviderConfig,
)
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory

logger = logging.getLogger(__name__)


class McpProviderValidator(BaseElementValidator):
    """
    Validates MCP Provider configuration.

    Uses McpProviderFactory.create_async() for a real MCP connection probe,
    matching the same transport path the wizard and runtime use.
    """

    def __init__(self, factory: McpProviderFactory = None):
        super().__init__()
        self._factory = factory or McpProviderFactory()

    def validate(self, config: McpProviderConfig, context: ValidationContext) -> ValidatorReport:
        """Retained synchronous entry point; native callers await validate_async directly."""
        try:
            with get_async_bridge() as bridge:
                return bridge.run(
                    self.validate_async(config, context), timeout=context.timeout_seconds
                )
        except CancelledError, TimeoutError:
            return self._build_report(
                [
                    self._error(
                        ValidationCode.NETWORK_TIMEOUT.value,
                        "Connection probe timed out",
                        field="mcp_url",
                    )
                ]
            )

    async def validate_async(
        self, config: McpProviderConfig, context: ValidationContext
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
                    field="mcp_url",
                )
            )
        except Exception:
            messages.append(
                self._error(
                    ValidationCode.ENDPOINT_UNREACHABLE.value,
                    "Connection probe failed",
                    field="mcp_url",
                )
            )
        return self._build_report(messages)

    async def _check_connection(
        self,
        config: McpProviderConfig,
        context: ValidationContext,
        messages: list[ValidationMessage],
    ) -> None:
        lookup_id = getattr(config, "server_identifier", "") or str(config.mcp_url)
        scheme_type = getattr(config, "scheme_type", "") or ""

        auth_method = getattr(config, "auth_method", None)
        is_sign_in = (
            auth_method == McpAuthMethod.SIGN_IN
            or getattr(
                auth_method,
                "value",
                None,
            )
            == McpAuthMethod.SIGN_IN.value
        )

        auth_cred = None
        if context.auth_service:
            # For SIGN_IN (OAuth), credentials are stored per human member, never on a team.
            # credential_lookup_user_id() handles the owner-vs-credential-user resolution.
            lookup_user = (
                context.credential_lookup_user_id()
                if is_sign_in
                else (context.user_id or "").strip()
            )
            if lookup_user:
                auth_cred = await context.auth_service.bind_async(
                    lookup_user,
                    lookup_id,
                    scheme_type=scheme_type,
                )
                # The saved `server_identifier` can be empty or stale (e.g. it
                # was never persisted back to the resource after sign-in, or
                # fell back to the raw mcp_url) even though the user is
                # genuinely signed in — OAuth credentials are stored under the
                # real issuer, not the MCP URL. Rediscover the issuer the same
                # way the sign-in status widget (auth.discovery) does before
                # concluding the resource is unauthenticated.
                if auth_cred is None and is_sign_in:
                    try:
                        detection = await context.auth_service.discover(str(config.mcp_url))
                    except CancelledError, TimeoutError:
                        # Real budget exhaustion — let it propagate so the
                        # outer handler reports it as a timeout, not a
                        # misleading "connection failed".
                        raise
                    except Exception:
                        logger.warning("MCP auth rediscovery failed")
                        detection = None
                    identifier_changed = (
                        detection
                        and detection.server_identifier
                        and detection.server_identifier != lookup_id
                    )
                    protocol_changed = (
                        detection
                        and detection.protocol_type
                        and detection.protocol_type != scheme_type
                    )
                    if (
                        detection
                        and detection.server_identifier
                        and (identifier_changed or protocol_changed)
                    ):
                        auth_cred = await context.auth_service.bind_async(
                            lookup_user,
                            detection.server_identifier,
                            scheme_type=detection.protocol_type or scheme_type,
                        )

        if is_sign_in and auth_cred is None:
            messages.append(
                self._error(
                    ValidationCode.INVALID_CREDENTIALS.value,
                    "Sign in before validating this resource",
                    field="mcp_url",
                )
            )
            return

        try:
            await self._factory.create_async(config, auth_credential=auth_cred)

            messages.append(
                self._info(
                    "CONNECTION_OK",
                    "Connected to MCP server",
                    field="mcp_url",
                )
            )

        except TimeoutError:
            messages.append(
                self._error(
                    ValidationCode.NETWORK_TIMEOUT.value,
                    f"Connection timed out after {context.timeout_seconds}s",
                    field="mcp_url",
                )
            )
        except RuntimeError:
            raise
        except Exception as e:
            pending, errors = [e], []
            while pending:
                error = pending.pop()
                if error.__cause__ is not None:
                    pending.append(error.__cause__)
                elif isinstance(error, BaseExceptionGroup):
                    pending.extend(error.exceptions)
                else:
                    errors.append(error)
            error_msg = " ".join(str(error) for error in errors)
            if (
                any(isinstance(error, AuthError) for error in errors)
                or "401" in error_msg
                or "Unauthorized" in error_msg
            ):
                messages.append(
                    self._error(
                        ValidationCode.INVALID_CREDENTIALS.value,
                        "Server rejected the credentials; sign in again or update your token",
                        field="mcp_url",
                    )
                )
            elif "403" in error_msg or "Forbidden" in error_msg:
                messages.append(
                    self._error(
                        ValidationCode.INVALID_CREDENTIALS.value,
                        "Not authorized; check your scopes or contact the administrator",
                        field="mcp_url",
                    )
                )
            else:
                messages.append(
                    self._error(
                        ValidationCode.ENDPOINT_UNREACHABLE.value,
                        "Connection probe failed",
                        field="mcp_url",
                    )
                )
