"""Portable negative graph declaration, installed only by its explicit admission test."""

from lumora.elements.specification import BaseElementSpec
from lumora.resources.domain.categories import ResourceCategory
from plugins.routing.elements.router_boolean.router_condition_factory import (
    RouterBooleanConditionFactory,
)
from plugins.routing.elements.router_boolean.spec.spec import (
    RouterBooleanConditionElementSpec,
)


class UnscopedConditionFactory(RouterBooleanConditionFactory):
    def accepts(self, cfg, element_type):
        return element_type == "missing_graph_contract"


class UnscopedConditionSpec(BaseElementSpec):
    """Constructible condition with its graph declaration deliberately absent."""

    category = ResourceCategory.CONDITION
    type_key = "missing_graph_contract"
    name = "Condition without graph metadata"
    description = "Construction alone does not declare graph behavior"
    config_schema = RouterBooleanConditionElementSpec.config_schema
    factory_cls = UnscopedConditionFactory
