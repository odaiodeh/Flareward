from mas.application.elements.exceptions import PluginConfigurationError
from mas.application.elements.factory import BaseFactory

from .branch_chooser import BranchChooserNode
from .config import BranchChooserNodeConfig
from .identifiers import Identifier


class BranchChooserNodeFactory(BaseFactory[BranchChooserNodeConfig, BranchChooserNode]):
    """Factory for BranchChooserNode."""

    def accepts(self, cfg: BranchChooserNodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: BranchChooserNodeConfig, **deps) -> BranchChooserNode:
        """
        deps delivers at least:
          • step_ctx  – mandatory identity capsule
        """
        try:
            return BranchChooserNode(default_branch=getattr(cfg, "default_branch", None))
        except Exception as exc:
            raise PluginConfigurationError(
                f"BranchChooserNodeFactory.create failed: {exc}", cfg.dict()
            ) from exc
