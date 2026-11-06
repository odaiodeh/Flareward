"""Graph channel metadata is opt-in and cannot leak into generic resource dependencies."""

import pytest
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.specification import BaseElementSpec
from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory
from mas.graph.validation.channel.matrix_builder import MatrixBuilder
from support.elements import DependencySpec, EchoSpec
from support.operations import TextConfig, TextFactory, TextSpec


def test_graph_channels_are_separate_from_typed_operation_contracts():
    assert not hasattr(BaseElementSpec, "reads") and not hasattr(BaseElementSpec, "writes")
    assert not issubclass(TextSpec, GraphElementSpec)
    assert GraphElementSpec.require(EchoSpec) is EchoSpec
    with pytest.raises(ValueError, match="graph specification"):
        GraphElementSpec.require(TextSpec)


def test_abstract_specification_cannot_be_installed_without_required_metadata():
    registry = ElementRegistry()
    with pytest.raises(TypeError, match="Abstract element specifications"):
        registry.register_spec_class(GraphElementSpec)
    assert registry.list_categories() == []


def test_concrete_generic_specification_still_requires_complete_metadata():
    with pytest.raises(TypeError, match="missing required spec attributes"):

        class MissingSpecification(BaseElementSpec):
            pass


def test_graph_specialization_cannot_be_used_for_an_operation():
    with pytest.raises(TypeError, match="only to nodes and conditions"):

        class IncorrectGraphOperation(GraphElementSpec):
            category = ResourceCategory.OPERATION
            type_key = "incorrect-graph-operation"
            name = "Incorrect"
            description = "An operation must use its typed I/O contract"
            config_schema = TextConfig
            factory_cls = TextFactory


def test_dependency_resource_metadata_does_not_create_graph_channel_producers():
    class DependencyWithOwnMetadata(DependencySpec):
        reads = {"dependency-private-input"}
        writes = {"dependency-private-output"}

    registry = ElementRegistry()
    for specification in (DependencyWithOwnMetadata, TextSpec, EchoSpec):
        registry.register_spec_class(specification)
    matrix = MatrixBuilder(registry).build()
    assert "dependency-private-input" not in matrix.consumer_map
    assert "dependency-private-output" not in matrix.producer_map
    assert matrix.consumer_map["user_prompt"] == {(ResourceCategory.NODE.value, EchoSpec.type_key)}
    assert matrix.producer_map["output"] == {(ResourceCategory.NODE.value, EchoSpec.type_key)}


@pytest.mark.parametrize("channels", ({""}, {"output", 7}, ["output"], "output"))
def test_invalid_channel_declarations_are_rejected_before_installation(channels):
    with pytest.raises(TypeError, match="sets of nonempty names"):
        type("InvalidChannels", (EchoSpec,), {"reads": channels})
