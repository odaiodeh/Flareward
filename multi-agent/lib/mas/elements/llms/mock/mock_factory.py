from typing import Any

from mas.application.elements.exceptions import PluginConfigurationError
from mas.application.elements.factory import BaseFactory

from .config import MockLLMConfig
from .identifiers import Identifier
from .mock import MockLLM


class MockLLMFactory(BaseFactory[MockLLMConfig, MockLLM]):
    """
    Factory for creating a MockLLM instance for testing.

    Ensures config is well-formed (type="mock") but otherwise returns a stateless mock.
    """

    def accepts(self, cfg: MockLLMConfig, element_type: str) -> bool:
        """
        Recognize configs with 'type': 'mock'.
        """
        return element_type == Identifier.TYPE

    def create(self, cfg: MockLLMConfig, **deps: Any) -> MockLLM:
        """
        Validate cfg and return a MockLLM.

        :param cfg: config dict with keys:
            - name (str)
            - type == "mock"
        :raises PluginConfigurationError: on validation failure
        """
        try:
            return MockLLM()
        except Exception as e:
            raise PluginConfigurationError(f"Failed to create MockLLM: {e}", cfg) from e
