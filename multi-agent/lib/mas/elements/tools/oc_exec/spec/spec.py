from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..config import OcExecToolConfig
from ..identifiers import META, Identifier
from ..oc_exec_factory import OcExecToolFactory
from ..validator import OcExecToolValidator


class OcExecToolElementSpec(BaseElementSpec):
    """Element specification for OpenShift OC Exec Tool."""

    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = OcExecToolConfig
    factory_cls = OcExecToolFactory
    tags = META.tags
    validator_cls = OcExecToolValidator
