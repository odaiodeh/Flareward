from typing import Any

from flareward.elements.exceptions import PluginConfigurationError
from flareward.elements.factory import BaseFactory
from plugins.ssh.elements.ssh_exec.config import SshExecToolConfig
from plugins.ssh.elements.ssh_exec.identifiers import Identifier
from plugins.ssh.elements.ssh_exec.ssh_exec import SshExecTool


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
