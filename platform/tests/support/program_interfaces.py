"""Explicit portable interface fixtures for domain and repository contract tests.

These tests supply metadata as the application publisher would. Installed-model
resolution and native execution tests use the production ProgramInterfaces service.
"""

from lumora.programs.domain.interfaces import CoordinatorIdentity, ProgramInterface
from lumora.programs.domain.models import GraphDefinition, ProgramBody


def declared_interface(body: ProgramBody) -> ProgramInterface:
    implementation = body.implementation
    identity = (
        CoordinatorIdentity(key="graph", version="1")
        if isinstance(implementation, GraphDefinition)
        else CoordinatorIdentity(
            key=implementation.implementation,
            version=implementation.version,
        )
    )
    return ProgramInterface(
        coordinator=identity,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
        children={
            name: declared_interface(target)
            for name, target in body.program_calls.items()
            if isinstance(target, ProgramBody)
        },
    )
