from typing import Any

from lumora.elements.factory import BaseFactory
from plugins.agents.elements.custom_agent.config import CustomAgentNodeConfig
from plugins.agents.elements.custom_agent.custom_agent import CustomAgentNode
from plugins.agents.elements.custom_agent.identifiers import Identifier


class CustomAgentNodeFactory(BaseFactory[CustomAgentNodeConfig, CustomAgentNode]):
    """Factory for creating CustomAgentNode instances.

    HITL gate/policy are NOT passed at construction time — they
    are injected at execution time via ``NodeRuntimeBinder`` using
    the ``SupportsHITL`` protocol setters on the node.

    ``hitl_mode`` and ``execution_holder`` are build-time concerns:
    the mode is a static config choice; the holder is needed at
    runtime so the node can read ``hitl_enabled`` (sourced from
    session metadata) when ``hitl_mode == DYNAMIC``.
    """

    def accepts(self, cfg: CustomAgentNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: CustomAgentNodeConfig, **deps: Any) -> CustomAgentNode:
        element_deps = deps.get("deps")
        return CustomAgentNode(
            llm=deps["llm"],
            retriever=deps.get("retriever"),
            tools=deps.get("tools"),
            mcp_providers=deps.get("providers"),
            system_message=cfg.system_message,
            strategy_type=cfg.strategy_type,
            max_rounds=cfg.max_rounds,
            retries=cfg.retries,
            hitl_mode=cfg.hitl_mode,
            execution_holder=element_deps.execution_ctx if element_deps else None,
            tracing_service=element_deps.tracing_service if element_deps else None,
        )
