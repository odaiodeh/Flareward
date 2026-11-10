from lumora.elements.exceptions import PluginConfigurationError
from lumora.elements.factory import BaseFactory
from plugins.human_interaction.elements.user_question.config import UserQuestionNodeConfig
from plugins.human_interaction.elements.user_question.identifiers import Identifier
from plugins.human_interaction.elements.user_question.user_question import (
    UserQuestionNode,
)


class UserQuestionNodeFactory(BaseFactory[UserQuestionNodeConfig, UserQuestionNode]):
    """Factory for UserQuestionNode (needs no LLM/retriever/tools)."""

    def accepts(self, cfg: UserQuestionNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: UserQuestionNodeConfig, **deps) -> UserQuestionNode:
        try:
            return UserQuestionNode()
        except Exception as exc:
            raise PluginConfigurationError(
                f"UserQuestionNodeFactory.create failed: {exc}", cfg.dict()
            ) from exc
