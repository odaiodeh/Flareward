"""
Claude Agent Node Configuration
"""

from typing import Any, Literal

from pydantic import Field, model_validator

from flareward.elements.hints import ActionHint, CardContext, CardHint, HiddenHint, HintType
from flareward.elements.node_config import NodeBaseConfig, retired_sandbox_configuration
from flareward.resources.domain.references import ProviderRef, RetrieverRef, ToolRef
from flareward.services.interactions.tools.models import HITLMode
from plugins.claude.elements.claude_agent.identifiers import EffortLevel, Identifier


class ClaudeAgentNodeConfig(NodeBaseConfig):
    """
    Claude Agent Node - runs autonomous Claude Agent SDK sessions.

    Configures the Claude Agent SDK with model, tools, skills,
    and Vertex AI authentication.  Tool-call permissions are
    managed by HITL (``hitl_mode``) instead of the SDK's built-in
    permission system.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE

    # --- Authentication (Vertex AI) ---

    vertex_project_id: str = Field(
        description="GCP Project ID for Vertex AI (e.g., 'my-project-123')",
        json_schema_extra=ActionHint(
            action_uid="claude_agent.validate_vertex_connection",
            hint_type=HintType.VALIDATE,
            field_mapping="is_reachable",
            dependencies={
                "vertex_project_id": "vertex_project_id",
                "vertex_region": "vertex_region",
                "model": "model",
            },
        ).to_hints(),
    )

    vertex_region: str = Field(
        default="us-east5",
        description="GCP region for Vertex AI (e.g., 'us-east5', 'europe-west1')",
    )

    # --- Model Configuration ---

    model: str = Field(
        default="claude-sonnet-4-6",
        description=(
            "Claude model to use (e.g., claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5)"
        ),
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )

    # --- Agent Behavior ---

    system_prompt: str = Field(
        default="", description="Custom system prompt for the Claude agent session"
    )

    max_turns: int | None = Field(
        default=200,
        description="Maximum agentic turns (tool-use round trips). Prevents runaway execution.",
    )

    hitl_mode: HITLMode = Field(
        default=HITLMode.SKIP,
        description="HITL approval mode: ask (always), skip (never), dynamic (runtime flag)",
    )

    effort: EffortLevel = Field(
        default=EffortLevel.MEDIUM,
        description="Controls how much effort Claude puts into reasoning. "
        "'low' — minimal thinking, fastest. "
        "'medium' — balanced cost/quality. "
        "'high' — deep reasoning. "
        "'xhigh' — extended reasoning (Opus 4.7+ only).",
    )

    permission_mode: str = Field(
        default="bypassPermissions",
        description="Permission mode: 'bypassPermissions' (fully autonomous), "
        "'acceptEdits' (auto-accept edits), 'plan' (read-only)",
    )

    allowed_tools: list[str] = Field(
        default_factory=lambda: [
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
            "WebSearch",
            "WebFetch",
        ],
        description="Tools to auto-approve without permission checks",
    )

    disallowed_tools: list[str] = Field(
        default_factory=list, description="Tools to explicitly deny"
    )

    # --- Skills ---

    skills_repos: dict[str, str] = Field(
        default_factory=dict,
        description="Skill sources — each key is the skill path within the repo and "
        "the value is the git repo URL "
        '(e.g., {"skills/docx": "https://github.com/org/repo"})',
    )

    # --- Advanced ---

    cwd: str | None = Field(
        default=None,
        description="Working directory for the Claude agent session (defaults to temp directory)",
        json_schema_extra=HiddenHint(reason="Advanced: override working directory").to_hints(),
    )

    env_vars: dict[str, str] = Field(
        default_factory=dict,
        description="Additional environment variables to pass to the SDK session",
        json_schema_extra=HiddenHint(reason="Advanced: custom environment variables").to_hints(),
    )

    # --- Integration ---

    tools: list[ToolRef] | None = Field(
        default_factory=list,
        description="List of tool keys",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )

    providers: list[ProviderRef] | None = Field(
        default_factory=list,
        description="List of MCP Provider Refs",
        title="MCP Servers",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )

    retriever: RetrieverRef | None = Field(
        None,
        description="Retriever for context augmentation (optional)",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )

    @model_validator(mode="before")
    @classmethod
    def reject_retired_sandbox(cls, value: Any) -> Any:
        return retired_sandbox_configuration(value)
