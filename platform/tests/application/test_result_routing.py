"""Result selection checks source availability and typed outcomes at publication."""

import pytest
from support.result_routing import result_graph
from support.scenarios import publish
from support.typed_programs import COORDINATORS

from lumora.programs.domain.bindings import LiteralBinding, PathBinding
from lumora.programs.graph_state import graph_state_type
from lumora.programs.service import ProgramContractError
from lumora.programs.state import ProgramState


@pytest.fixture(autouse=True)
def installed(application):
    for registration in COORDINATORS:
        application.applications.register(registration)


@pytest.mark.parametrize(
    "schema,path",
    [
        ({"type": "boolean"}, ()),
        ({"type": "string", "enum": ["approved", "changes_required"]}, ()),
        ({"type": "array", "items": {"type": "string"}}, ()),
        (
            {
                "type": "object",
                "properties": {"outcome": {"type": "string"}},
                "required": ["outcome"],
                "additionalProperties": False,
            },
            ("outcome",),
        ),
    ],
)
async def test_route_can_consume_the_completed_sources_typed_result(application, schema, path):
    graph = result_graph(schema=schema, selection=PathBinding(path=("results", "decide", *path)))
    assert graph_state_type(graph) is ProgramState
    assert not graph.resources
    revision = await publish(application, "result-route", graph, input_schema={}, output_schema={})
    assert revision.definition.implementation.conditions[0].kind == "result"


@pytest.mark.parametrize(
    "problem", ["unknown", "future", "missing", "number", "literal", "private-label"]
)
async def test_invalid_result_route_cannot_publish(application, problem):
    path = ("results", "decide")
    schema = {"type": "string"}
    if problem == "unknown":
        path = ("results", "unknown")
    elif problem == "future":
        path = ("results", "yes")
    elif problem == "missing":
        path = ("results", "decide", "missing")
        schema = {"type": "object", "additionalProperties": False}
    elif problem == "number":
        schema = {"type": "integer"}
    elif problem == "private-label":
        schema = {"const": "private-unmapped-value"}
    selection = (
        LiteralBinding(value="private-unmapped-value")
        if problem == "literal"
        else PathBinding(path=path)
    )
    graph = result_graph(schema=schema, selection=selection)
    with pytest.raises(ProgramContractError) as rejected:
        await publish(application, "invalid-result-route", graph, input_schema={}, output_schema={})
    assert rejected.value.issue.path[:4] == ("implementation", "conditions", 0, "selection")
    assert "private-unmapped-value" not in str(rejected.value)
