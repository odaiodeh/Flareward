"""Explicit action registrations; optional provider imports stay in composition."""

import logging
from importlib import import_module

from lumora.services.actions.auth.discovery.action import DiscoveryAction
from lumora.services.actions.auth.list_servers.action import ListServersAction
from lumora.services.actions.auth.sign_out.action import SignOutAction
from lumora.services.actions.auth.store_credential.action import StoreCredentialAction
from lumora.services.actions.contracts import ActionSettings
from lumora.services.actions.service import ActionsService
from lumora.services.auth.service import AuthService
from plugins.actions.llms.openai.capabilities import ModelCapabilities
from plugins.actions.llms.openai.get_models.get_models import GetOpenAIModelsAction
from plugins.actions.llms.openai.get_reasoning_levels.get_reasoning_levels import (
    GetOpenAIReasoningLevelsAction,
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
        )
    )
    for module, name, needs_auth in _OPTIONAL:
        try:
            implementation = getattr(import_module("plugins.actions.providers." + module), name)
        except ModuleNotFoundError as error:
            if error.name and error.name.startswith(("lumora.", "plugins.")):
                raise
            logger.info("Optional action adapter unavailable: %s", module)
            continue
        service.register_instance(
            implementation(auth_service=auth) if needs_auth else implementation()
        )
    return service
