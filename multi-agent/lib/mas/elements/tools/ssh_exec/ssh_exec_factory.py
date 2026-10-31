from typing import Any

from mas.application.elements.exceptions import PluginConfigurationError
from mas.application.elements.factory import BaseFactory

from .config import SshExecToolConfig
from .identifiers import Identifier
from .ssh_exec import SshExecTool


class SshExecToolFactory(BaseFactory[SshExecToolConfig, SshExecTool]):
    """
    Factory for creating SshExecTool clients from an SshExecToolConfig.
    """

    def accepts(self, cfg: SshExecToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: SshExecToolConfig, **kwargs: Any) -> SshExecTool:
        """
        Instantiate an DivisionToolConfig using validated config values.

        :param cfg: Fully‐validated DivisionToolConfig
        :raises PluginConfigurationError: if instantiation fails
        """
        try:
            client = SshExecTool(
                host=cfg.host, port=cfg.port, username=cfg.username, password=cfg.password
            )
            return client
        except Exception as e:
            raise PluginConfigurationError(
                f"SshExecToolFactory.create() failed: {e}", cfg.dict()
            ) from e
