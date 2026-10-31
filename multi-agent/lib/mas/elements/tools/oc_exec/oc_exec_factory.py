"""Factory for OcExecTool."""

from typing import Any

from mas.application.elements.exceptions import PluginConfigurationError
from mas.application.elements.factory import BaseFactory

from .config import OcExecToolConfig
from .identifiers import Identifier
from .oc_exec import OcExecTool


class OcExecToolFactory(BaseFactory[OcExecToolConfig, OcExecTool]):
    """Factory for creating OcExecTool instances."""

    def accepts(self, cfg: OcExecToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: OcExecToolConfig, **kwargs: Any) -> OcExecTool:
        """Create an OcExecTool instance from mas.config."""
        try:
            return OcExecTool(
                server=cfg.server,
                token=cfg.token,
                skip_tls_verify=cfg.skip_tls_verify,
            )
        except Exception as e:
            raise PluginConfigurationError(
                f"Failed to create OcExecTool: {e}", cfg.model_dump()
            ) from e
