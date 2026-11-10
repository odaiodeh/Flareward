from typing import Any

from lumora.elements.exceptions import PluginConfigurationError
from lumora.elements.factory import BaseFactory
from plugins.testing.elements.mock.config import MockLLMConfig
from plugins.testing.elements.mock.identifiers import Identifier
from plugins.testing.elements.mock.mock import MockLLM


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
