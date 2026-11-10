from lumora.elements.exceptions import PluginConfigurationError
from lumora.elements.factory import BaseFactory
from plugins.mas.elements.final_answer.config import FinalAnswerNodeConfig
from plugins.mas.elements.final_answer.final_answer import FinalAnswerNode
from plugins.mas.elements.final_answer.identifiers import Identifier


class FinalAnswerNodeFactory(BaseFactory[FinalAnswerNodeConfig, FinalAnswerNode]):
    """Builds a FinalAnswerNode (no LLM / retriever / tools needed)."""

    def accepts(self, cfg: FinalAnswerNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: FinalAnswerNodeConfig, **deps) -> FinalAnswerNode:
        try:
            return FinalAnswerNode()
        except Exception as exc:
            raise PluginConfigurationError(
                f"FinalAnswerNodeFactory.create failed: {exc}", cfg.dict()
            ) from exc
