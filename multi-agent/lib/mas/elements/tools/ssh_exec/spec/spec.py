from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.elements.tools.common.card_builder import ToolCardBuilder

from ..config import SshExecToolConfig
from ..identifiers import META, Identifier
from ..ssh_exec_factory import SshExecToolFactory
from ..validator import SshExecToolValidator


class SshExecToolElementSpec(BaseElementSpec):
    """Element specification for SSH Exec Tool."""

    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = SshExecToolConfig
    factory_cls = SshExecToolFactory
    tags = META.tags
    validator_cls = SshExecToolValidator
    card_builder_cls = ToolCardBuilder
