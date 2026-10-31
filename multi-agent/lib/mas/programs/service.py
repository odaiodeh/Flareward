"""Publication validates domain contracts without allocating execution infrastructure."""

from jsonschema import Draft202012Validator, SchemaError
from pydantic import ValidationError

from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.application.elements.construction.secrets import ConfigurationSecrets
from mas.core.identity import Identity
from mas.programs.models import (
    ApplicationDefinition,
    GraphDefinition,
    ProgramCallStep,
    ProgramDefinition,
    ProgramRef,
    ProgramRevision,
)
from mas.programs.ports import ProgramRepository
from mas.programs.registry import ApplicationRegistry


class ProgramAccessDenied(PermissionError):
    """The caller does not own the requested program."""


class ProgramContractError(ValueError):
    """A public program contract is not a valid JSON schema."""


class ProgramService:
    def __init__(
        self,
        repository: ProgramRepository,
        applications: ApplicationRegistry,
        bundles: ElementBundleResolver,
        configuration: ConfigurationSecrets,
    ) -> None:
        self._repository = repository
        self._applications = applications
        self._bundles = bundles
        self._configuration = configuration

    @staticmethod
    def authorize(definition: ProgramDefinition, caller: Identity) -> None:
        if not caller.owns(definition.owner):
            raise ProgramAccessDenied(definition.program_id)

    async def save(self, definition: ProgramDefinition, caller: Identity) -> ProgramDefinition:
        self.authorize(definition, caller)
        try:
            previous = await self._repository.get_draft(definition.program_id)
        except KeyError:
            previous = None
        if previous is not None:
            self.authorize(previous, caller)
        for name, schema in (
            ("input", definition.input_schema),
            ("output", definition.output_schema),
        ):
            try:
                Draft202012Validator.check_schema(schema)
            except SchemaError as error:
                raise ProgramContractError(
                    f"Invalid program {name} schema: {error.message}"
                ) from error
        implementation = definition.implementation
        if isinstance(implementation, GraphDefinition):
            resources = tuple(
                [
                    await self._configuration.protect_resource(resource, caller)
                    for resource in implementation.resources
                ]
            )
            implementation = implementation.model_copy(update={"resources": resources}, deep=True)
        else:
            registration = self._applications.get(
                implementation.implementation, implementation.version
            )
            try:
                config = registration.config_schema.model_validate(
                    implementation.config, by_name=True
                )
            except ValidationError:
                raise ProgramContractError(
                    f"Invalid configuration for application program {implementation.implementation}"
                ) from None
            implementation = implementation.model_copy(
                update={"config": await self._configuration.protect(config, caller)}, deep=True
            )
        definition = definition.model_copy(update={"implementation": implementation}, deep=True)
        await self._repository.save_draft(definition)
        return definition

    async def revision(self, reference: ProgramRef, caller: Identity) -> ProgramRevision:
        revision = await self._repository.get_revision(reference)
        self.authorize(revision.definition, caller)
        return ProgramRevision.model_validate_json(revision.model_dump_json())

    async def publish(self, program_id: str, caller: Identity) -> ProgramRevision:
        definition = await self._repository.get_draft(program_id)
        self.authorize(definition, caller)
        implementation = definition.implementation
        if isinstance(implementation, GraphDefinition):
            children = [
                step.program for step in implementation.steps if isinstance(step, ProgramCallStep)
            ]
            for step in implementation.steps:
                if not isinstance(step, ProgramCallStep):
                    self._bundles.resolve(step.element, implementation.resources)
            for condition in implementation.conditions:
                self._bundles.resolve(condition.condition, implementation.resources)
        elif isinstance(implementation, ApplicationDefinition):
            registration = self._applications.get(
                implementation.implementation, implementation.version
            )
            registration.config_schema.model_validate(implementation.config, by_name=True)
            children = list(implementation.children.values())
        for child in children:
            await self._validate_dependency(child, caller, (program_id,))
        return await self._repository.publish(definition)

    async def _validate_dependency(
        self,
        reference: ProgramRef,
        caller: Identity,
        ancestors: tuple[str, ...],
    ) -> None:
        if reference.program_id in ancestors:
            raise ValueError(
                f"Recursive program dependency: {' -> '.join((*ancestors, reference.program_id))}"
            )
        revision = await self.revision(reference, caller)
        implementation = revision.definition.implementation
        if isinstance(implementation, GraphDefinition):
            children = [
                step.program for step in implementation.steps if isinstance(step, ProgramCallStep)
            ]
        else:
            children = list(implementation.children.values())
        for child in children:
            await self._validate_dependency(child, caller, (*ancestors, reference.program_id))
