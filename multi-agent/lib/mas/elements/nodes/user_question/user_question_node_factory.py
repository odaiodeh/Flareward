from mas.application.elements.exceptions import PluginConfigurationError
from mas.application.elements.factory import BaseFactory

from .config import UserQuestionNodeConfig
from .identifiers import Identifier
from .user_question import UserQuestionNode


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
