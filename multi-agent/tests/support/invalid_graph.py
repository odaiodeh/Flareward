"""Portable negative graph declaration, installed only by its explicit admission test."""

from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.elements.conditions.router_boolean.router_condition_factory import (
    RouterBooleanConditionFactory,
)
from mas.elements.conditions.router_boolean.spec.spec import RouterBooleanConditionElementSpec


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
