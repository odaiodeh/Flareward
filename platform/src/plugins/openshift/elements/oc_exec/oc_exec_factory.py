"""Factory for OcExecTool."""

from typing import Any

from lumora.elements.exceptions import PluginConfigurationError
from lumora.elements.factory import BaseFactory
from plugins.openshift.elements.oc_exec.config import OcExecToolConfig
from plugins.openshift.elements.oc_exec.identifiers import Identifier
from plugins.openshift.elements.oc_exec.oc_exec import OcExecTool


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
