from flareward.elements.exceptions import PluginConfigurationError
from flareward.elements.factory import BaseFactory
from plugins.routing.elements.branch_chooser.branch_chooser import BranchChooserNode
from plugins.routing.elements.branch_chooser.config import BranchChooserNodeConfig
from plugins.routing.elements.branch_chooser.identifiers import Identifier


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
