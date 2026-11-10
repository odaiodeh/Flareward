from lumora.elements.specification import BaseElementSpec
from lumora.elements.tools.configuration.card_builder import ToolCardBuilder
from lumora.resources.domain.categories import ResourceCategory
from plugins.ssh.elements.ssh_exec.config import SshExecToolConfig
from plugins.ssh.elements.ssh_exec.identifiers import META, Identifier
from plugins.ssh.elements.ssh_exec.ssh_exec_factory import SshExecToolFactory
from plugins.ssh.elements.ssh_exec.validator import SshExecToolValidator


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
