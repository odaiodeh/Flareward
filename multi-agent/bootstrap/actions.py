"""Explicit action registrations; optional provider imports stay in composition."""

import logging
from importlib import import_module

from mas.application.actions.auth.discovery.action import DiscoveryAction
from mas.application.actions.auth.list_servers.action import ListServersAction
from mas.application.actions.auth.sign_out.action import SignOutAction
from mas.application.actions.auth.store_credential.action import StoreCredentialAction
from mas.application.actions.contracts import ActionSettings
from mas.application.actions.service import ActionsService
from mas.core.auth.service import AuthService
from outbound.actions.llms.openai.capabilities import ModelCapabilities
from outbound.actions.llms.openai.get_models.get_models import GetOpenAIModelsAction
from outbound.actions.llms.openai.get_reasoning_levels.get_reasoning_levels import (
    GetOpenAIReasoningLevelsAction,
)
from outbound.actions.providers.rag.client import RagActionClient
from outbound.actions.providers.rag.get_available_docs.get_available_docs import (
    GetAvailableDocsAction,
)
from outbound.actions.providers.rag.get_available_tags.get_available_tags import (
    GetAvailableTagsAction,
)
from outbound.actions.providers.rag.validate_connection.validate_connection import (
    ValidateConnectionAction as RagValidateConnectionAction,
)

logger = logging.getLogger(__name__)

_OPTIONAL = (
    ("mcp.get_tools_names.get_tools_names", "GetToolsNamesAction", True),
    ("mcp.validate_connection.validate_connection", "ValidateConnectionAction", True),
    ("a2a.get_agent_card.get_agent_card", "GetAgentCardAction", False),
    ("a2a.validate_connection.validate_connection", "ValidateConnectionAction", True),
    (
        "claude_agent.validate_vertex_connection.validate_vertex_connection",
        "ValidateVertexConnectionAction",
        False,
    ),
)


def build_actions(
    *,
    auth: AuthService | None,
    settings: ActionSettings | None,
    rag: RagActionClient,
) -> ActionsService:
    capabilities = ModelCapabilities(settings)
    service = ActionsService(
        (
            StoreCredentialAction(auth),
            DiscoveryAction(auth),
            SignOutAction(auth),
            ListServersAction(auth),
            GetOpenAIModelsAction(capabilities),
            GetOpenAIReasoningLevelsAction(capabilities),
            GetAvailableDocsAction(rag),
            GetAvailableTagsAction(rag),
            RagValidateConnectionAction(rag),
        )
    )
    for module, name, needs_auth in _OPTIONAL:
        try:
            implementation = getattr(import_module("outbound.actions.providers." + module), name)
        except ModuleNotFoundError as error:
            if error.name and error.name.startswith(("outbound.", "mas.")):
                raise
            logger.info("Optional action adapter unavailable: %s", module)
            continue
        service.register_instance(
            implementation(auth_service=auth) if needs_auth else implementation()
        )
    return service
