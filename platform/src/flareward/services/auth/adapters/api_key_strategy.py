"""
ApiKeyStrategy — static credential, no interactive acquisition flow.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from flareward.resources.domain.categories import SchemeType
from flareward.services.auth.credentials.models import RecoveryResult, StoredCredential, TokenSet
from flareward.services.auth.ports import AuthChallenge, AuthStrategy, CompletionResult
from flareward.services.auth.strategies.api_key.config import ApiKeyConfig

logger = logging.getLogger(__name__)


class ApiKeyStrategy(AuthStrategy):
    @property
    def scheme_type(self) -> str:
        return SchemeType.API_KEY

    def build_headers(self, credential: StoredCredential) -> dict[str, str]:
        cfg = ApiKeyConfig()
        value = (
            f"{cfg.header_prefix}{credential.access_token}"
            if cfg.header_prefix
            else credential.access_token
        )
        return {cfg.header_name: value}

    async def attempt_recovery(
        self,
        credential: StoredCredential,
        config: dict[str, Any],
    ) -> RecoveryResult:
        return RecoveryResult(
            recovered=False,
            should_retry=False,
            reason="API key was rejected; verify the key or generate a new one",
        )

    async def initiate(
        self,
        user_id: str,
        server_identifier: str,
        config: dict[str, Any],
    ) -> AuthChallenge:
        return AuthChallenge.collect(
            fields=[{"name": "api_key", "label": "API Key", "secret": True}],
            flow_id=secrets.token_urlsafe(16),
            server_identifier=server_identifier,
        )

    async def complete(
        self,
        raw_callback_data: dict[str, Any],
    ) -> CompletionResult:
        api_key = raw_callback_data.get("api_key", "")
        return CompletionResult(
            token_set=TokenSet(access_token=api_key, token_type="ApiKey"),
            user_id=raw_callback_data.get("user_id", ""),
            server_identifier=raw_callback_data.get("server_identifier", ""),
            scheme_type=SchemeType.API_KEY,
        )
