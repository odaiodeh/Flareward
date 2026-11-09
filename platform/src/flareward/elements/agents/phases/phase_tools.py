"""Generic tool categorization for phase-based strategies."""

from flareward.elements.agents.constants import (
    ExecutionPhase,
    PhaseToolMapping,
    ToolCategory,
    ToolKeywords,
)
from flareward.elements.agents.phases.phase_protocols import PhaseToolProvider
from flareward.elements.ports.tool import BaseTool


class GenericToolCategorizer(PhaseToolProvider):
    """Generic tool categorizer for phase-based strategies."""

    def __init__(
        self,
        tools: list[BaseTool],
        *,
        custom_phase_mappings: dict[str, dict[str, set]] | None = None,
        additional_categorization_rules: dict[str, callable] | None = None,
    ):
        """Initialize tool categorizer."""
        self.all_tools = {tool.name: tool for tool in tools}
        self.custom_phase_mappings = custom_phase_mappings or {}
        self.additional_rules = additional_categorization_rules or {}

        # Categorize tools by type
        self._categorize_tools()

        # Build phase-specific tool sets
        self._build_phase_tools()

    def _categorize_tools(self) -> None:
        """Categorize tools by their name prefix and purpose."""
        self.workplan_tools = {}
        self.topology_tools = {}
        self.iem_tools = {}
        self.workspace_tools = {}
        self.domain_tools = {}

        for tool in self.all_tools.values():
            name = tool.name.lower()

            # Apply custom categorization rules first
            categorized = False
            for rule_name, rule_func in self.additional_rules.items():
                if rule_func(tool):
                    # Custom rule handled the tool
                    categorized = True
                    break

            if categorized:
                continue

            # Standard categorization by prefix
            if name.startswith(ToolKeywords.WORKPLAN_PREFIX):
                self.workplan_tools[tool.name] = tool
            elif name.startswith(ToolKeywords.TOPOLOGY_PREFIX):
                self.topology_tools[tool.name] = tool
            elif name.startswith(ToolKeywords.IEM_PREFIX) or name == ToolKeywords.DELEGATE_TASK:
                self.iem_tools[tool.name] = tool
            elif name.startswith(ToolKeywords.WORKSPACE_PREFIX):
                self.workspace_tools[tool.name] = tool
            else:
                # All other tools are domain tools
                self.domain_tools[tool.name] = tool

    def _build_phase_tools(self) -> None:
        """Build phase-specific tool mappings."""
        self._phase_tools = {}

        # Use custom mappings if provided, otherwise use defaults
        phase_mappings = self.custom_phase_mappings or {
            ExecutionPhase.PLANNING: {
                "keywords": PhaseToolMapping.PLANNING_KEYWORDS,
                "categories": PhaseToolMapping.PLANNING_CATEGORIES,
            },
            ExecutionPhase.ALLOCATION: {
                "keywords": PhaseToolMapping.ALLOCATION_KEYWORDS,
                "categories": PhaseToolMapping.ALLOCATION_CATEGORIES,
            },
            ExecutionPhase.EXECUTION: {
                "keywords": PhaseToolMapping.EXECUTION_KEYWORDS,
                "categories": PhaseToolMapping.EXECUTION_CATEGORIES,
            },
            ExecutionPhase.MONITORING: {
                "keywords": PhaseToolMapping.MONITORING_KEYWORDS,
                "categories": PhaseToolMapping.MONITORING_CATEGORIES,
            },
            ExecutionPhase.SYNTHESIS: {
                "keywords": PhaseToolMapping.SYNTHESIS_KEYWORDS,
                "categories": PhaseToolMapping.SYNTHESIS_CATEGORIES,
            },
        }

        for phase, mapping in phase_mappings.items():
            self._phase_tools[phase] = self._get_tools_for_mapping(
                mapping.get("keywords", set()), mapping.get("categories", set())
            )

    def _get_tools_for_mapping(
        self, keywords: set[str], categories: set[ToolCategory]
    ) -> list[BaseTool]:
        """Get tools matching the given keywords and categories."""
        tools = []

        # Add tools by category
        if ToolCategory.WORKPLAN in categories:
            if keywords:
                # Filter by keywords
                tools.extend(
                    [
                        t
                        for t in self.workplan_tools.values()
                        if any(kw in t.name for kw in keywords)
                    ]
                )
            else:
                # Add all workplan tools
                tools.extend(self.workplan_tools.values())

        if ToolCategory.TOPOLOGY in categories:
            tools.extend(self.topology_tools.values())

        if ToolCategory.IEM in categories or ToolCategory.DELEGATION in categories:
            tools.extend(self.iem_tools.values())

        if ToolCategory.WORKSPACE in categories:
            tools.extend(self.workspace_tools.values())

        if ToolCategory.DOMAIN in categories:
            tools.extend(self.domain_tools.values())

        return tools

    def get_tools_for_phase(self, phase: ExecutionPhase) -> list[BaseTool]:
        """Get tools appropriate for the given phase."""
        return self._phase_tools.get(phase, list(self.all_tools.values()))

    def get_all_phase_tools(self) -> dict[ExecutionPhase, list[BaseTool]]:
        """Get all phase-to-tools mappings."""
        return self._phase_tools.copy()

    def add_custom_phase(
        self, phase: ExecutionPhase, keywords: set[str], categories: set[ToolCategory]
    ) -> None:
        """Add a custom phase with specific tool requirements."""
        self._phase_tools[phase] = self._get_tools_for_mapping(keywords, categories)

    def get_tool_categories(self) -> dict[str, dict[str, BaseTool]]:
        """Get tools organized by category."""
        return {
            "workplan": self.workplan_tools,
            "topology": self.topology_tools,
            "iem": self.iem_tools,
            "workspace": self.workspace_tools,
            "domain": self.domain_tools,
        }


# =============================================================================
# ORCHESTRATOR-SPECIFIC EXTENSIONS
# =============================================================================


class OrchestratorToolCategorizer(GenericToolCategorizer):
    """Orchestrator-specific tool categorizer."""

    def __init__(self, tools: list[BaseTool]):
        """Initialize orchestrator tool categorizer."""

        # Define orchestrator-specific categorization rules
        def is_delegation_tool(tool: BaseTool) -> bool:
            """Check if tool is for delegation."""
            name = tool.name.lower()
            return "delegate" in name or "iem" in name

        additional_rules = {"delegation": is_delegation_tool}

        super().__init__(tools=tools, additional_categorization_rules=additional_rules)

    def get_delegation_tools(self) -> list[BaseTool]:
        """Get tools specifically for delegation."""
        return list(self.iem_tools.values())

    def get_planning_tools(self) -> list[BaseTool]:
        """Get tools for planning phase with orchestrator-specific logic."""
        return self.get_tools_for_phase("planning")

    def get_allocation_tools(self) -> list[BaseTool]:
        """Get tools for allocation phase with orchestrator-specific logic."""
        return self.get_tools_for_phase("allocation")


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_generic_categorizer(tools: list[BaseTool], **kwargs) -> GenericToolCategorizer:
    """Factory function for creating generic tool categorizers."""
    return GenericToolCategorizer(tools, **kwargs)


def create_orchestrator_categorizer(tools: list[BaseTool]) -> OrchestratorToolCategorizer:
    """Factory function for creating orchestrator tool categorizers."""
    return OrchestratorToolCategorizer(tools)
