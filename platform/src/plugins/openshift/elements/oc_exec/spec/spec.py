from lumora.elements.specification import BaseElementSpec
from lumora.resources.domain.categories import ResourceCategory
from plugins.openshift.elements.oc_exec.config import OcExecToolConfig
from plugins.openshift.elements.oc_exec.identifiers import META, Identifier
from plugins.openshift.elements.oc_exec.oc_exec_factory import OcExecToolFactory
from plugins.openshift.elements.oc_exec.validator import OcExecToolValidator


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
