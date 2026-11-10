"""
Action: Get reasoning levels for a specific OpenAI model.

Given a model name (or prefix), returns the supported reasoning-effort
levels.  The frontend calls this action whenever the ``model_name``
selection changes to populate the ``reasoning_effort`` dropdown.

Matching uses the same longest-prefix rule as the capabilities map, so
``"gpt-5.6-sol"`` resolves correctly even when the capabilities dict
only has the full key ``"gpt-5.6-sol"``.
"""

from __future__ import annotations

from pydantic import Field, TypeAdapter

from lumora.resources.domain.categories import ResourceCategory
from lumora.services.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from plugins.actions.llms.openai.capabilities import (
    ModelCapabilities,
    find_model_capabilities,
)
from plugins.openai.elements.openai.identifiers import Identifier


class GetOpenAIReasoningLevelsInput(BaseActionInput):
    """Input: the model name to look up."""

    model_name: str = Field(
        description="Full model ID or prefix, e.g. 'gpt-5.6-sol' or 'gpt-5'.",
    )


class GetOpenAIReasoningLevelsOutput(BaseActionOutput):
    """Supported reasoning levels for the model."""

    model_name: str = ""
    reasoning_levels: list[str] = []
    model_found: bool = False


class GetOpenAIReasoningLevelsAction(
    BaseAction[GetOpenAIReasoningLevelsInput, GetOpenAIReasoningLevelsOutput]
):
    uid = "openai.get_reasoning_levels"
    name = "get_reasoning_levels"
    description = "Return the supported reasoning-effort levels for a given OpenAI model name."
    action_type = ActionType.DISCOVERY
    input_schema = GetOpenAIReasoningLevelsInput
    output_schema = GetOpenAIReasoningLevelsOutput
    version = "1.0.0"
    tags = frozenset({"openai", "llm", "discovery", "reasoning"})
    elements = frozenset({(ResourceCategory.LLM.value, Identifier.TYPE)})

    def __init__(self, capabilities: ModelCapabilities) -> None:
        self._capabilities = capabilities

    async def execute(
        self,
        input_data: GetOpenAIReasoningLevelsInput,
        context: ActionContext | None = None,
    ) -> GetOpenAIReasoningLevelsOutput:
        try:
            model_name = input_data.model_name.strip()
            # Fetch once so the cap lookup shares the cached map.
            caps = await self._capabilities.load()
            cap = find_model_capabilities(caps, model_name)

            if cap is None:
                return GetOpenAIReasoningLevelsOutput(
                    success=True,
                    message=f"Model '{model_name}' not found in capabilities config",
                    model_name=model_name,
                    reasoning_levels=[],
                    model_found=False,
                )

            levels = TypeAdapter(list[str]).validate_python(cap.get("reasoning", []))
            return GetOpenAIReasoningLevelsOutput(
                success=True,
                message=f"Found {len(levels)} reasoning levels for '{model_name}'",
                model_name=model_name,
                reasoning_levels=levels,
                model_found=True,
            )
        except Exception:
            return GetOpenAIReasoningLevelsOutput(
                success=False,
                message="Failed to retrieve reasoning levels",
                model_name=getattr(input_data, "model_name", ""),
                reasoning_levels=[],
                model_found=False,
            )
