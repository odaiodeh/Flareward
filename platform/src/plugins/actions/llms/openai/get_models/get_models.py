"""
Action: Get available OpenAI model names.

Returns the list of model-name prefixes configured in the
``openai_model_capabilities`` admin config section.  The frontend uses
this list to render ``model_name`` as a dropdown instead of a free-text
field when creating or editing an OpenAI LLM resource.
"""

from __future__ import annotations

from lumora.resources.domain.categories import ResourceCategory
from lumora.services.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from plugins.actions.llms.openai.capabilities import ModelCapabilities
from plugins.openai.elements.openai.identifiers import Identifier


class GetOpenAIModelsInput(BaseActionInput):
    """No input required — returns all configured model names."""

    pass


class GetOpenAIModelsOutput(BaseActionOutput):
    """List of model-name prefixes available in the admin config."""

    models: list[str] = []
    total_count: int = 0


class GetOpenAIModelsAction(BaseAction[GetOpenAIModelsInput, GetOpenAIModelsOutput]):
    uid = "openai.get_models"
    name = "get_models"
    description = (
        "Retrieve the list of OpenAI model names configured in the "
        "admin MODEL_CAPABILITIES settings."
    )
    action_type = ActionType.DISCOVERY
    input_schema = GetOpenAIModelsInput
    output_schema = GetOpenAIModelsOutput
    version = "1.0.0"
    tags = frozenset({"openai", "llm", "discovery", "models"})
    elements = frozenset({(ResourceCategory.LLM.value, Identifier.TYPE)})

    def __init__(self, capabilities: ModelCapabilities) -> None:
        self._capabilities = capabilities

    async def execute(
        self,
        input_data: GetOpenAIModelsInput,
        context: ActionContext | None = None,
    ) -> GetOpenAIModelsOutput:
        try:
            caps = await self._capabilities.load()
            models = sorted(caps.keys())
            return GetOpenAIModelsOutput(
                success=True,
                message=f"Found {len(models)} configured models",
                models=models,
                total_count=len(models),
            )
        except Exception:
            return GetOpenAIModelsOutput(
                success=False,
                message="Failed to retrieve models",
                models=[],
                total_count=0,
            )
