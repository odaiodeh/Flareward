"""Publication validates domain contracts without allocating execution infrastructure."""

from collections.abc import Iterator, Mapping, Sequence

from jsonschema import SchemaError

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.elements.construction.secrets import ConfigurationSecrets
from flareward.elements.construction.snapshots import (
    ResourceSnapshotsUnavailable,
    SavedResourceResolver,
)
from flareward.programs.authoring import (
    ProgramConflict,
    ProgramDraft,
    ProgramIssue,
    ProgramIssueCode,
    ProgramPage,
    ProgramPresentation,
    ProgramResourceSelection,
    ProgramSummary,
    ProgramValidation,
    RevisionPage,
    RevisionSummary,
)
from flareward.programs.contracts import ProgramContracts
from flareward.programs.domain.models import (
    ApplicationDefinition,
    BodyPath,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
    ProgramDefinition,
    ProgramRef,
    ProgramRevision,
    ProgramTarget,
)
from flareward.programs.interfaces import BindingContractError, InterfaceContract
from flareward.programs.ports import ProgramRepository
from flareward.programs.registry import ApplicationDescriptor, ApplicationRegistry
from flareward.services.identity.domain import Identity


class ProgramAccessDenied(PermissionError):
    """The caller does not own the requested program."""


class ProgramContractError(ValueError):
    """A safe authoring/publication diagnostic without private configuration data."""

    def __init__(
        self,
        message: str,
        *,
        code: ProgramIssueCode = ProgramIssueCode.CONFIGURATION,
        path: tuple[str | int, ...] = (),
    ) -> None:
        self.issue = ProgramIssue(code=code, message=message, path=path)
        super().__init__(message)


class ProgramService:
    def __init__(
        self,
        repository: ProgramRepository,
        applications: ApplicationRegistry,
        elements: ElementRegistry,
        configuration: ConfigurationSecrets,
        resource_snapshots: SavedResourceResolver | None = None,
    ) -> None:
        self._repository = repository
        self._applications = applications
        self._bundles = ElementBundleResolver(elements)
        self._contracts = ProgramContracts(elements, applications)
        self._configuration = configuration
        self._resource_snapshots = resource_snapshots

    def implementations(self) -> list[ApplicationDescriptor]:
        return self._applications.describe()

    @staticmethod
    def authorize(definition: ProgramDefinition, caller: Identity) -> None:
        if not caller.owns(definition.owner):
            raise ProgramAccessDenied(definition.program_id)

    async def draft(self, program_id: str, caller: Identity) -> ProgramDraft:
        draft = await self._repository.get_draft(program_id)
        self.authorize(draft.definition, caller)
        return ProgramDraft.model_validate_json(draft.model_dump_json())

    async def list(self, caller: Identity, *, after: str = "", limit: int = 50) -> ProgramPage:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid program pagination")
        drafts = await self._repository.list_drafts(caller, after=after, limit=limit)
        summaries = tuple(
            ProgramSummary(
                program_id=draft.definition.program_id,
                name=draft.definition.name,
                kind=draft.definition.implementation.kind,
                draft_version=draft.version,
            )
            for draft in drafts
        )
        return ProgramPage(
            programs=summaries,
            next_cursor=summaries[-1].program_id if len(summaries) == limit else None,
        )

    async def revisions(
        self, program_id: str, caller: Identity, *, before: int | None = None, limit: int = 50
    ) -> RevisionPage:
        await self.draft(program_id, caller)
        if not 1 <= limit <= 100 or (before is not None and before < 1):
            raise ValueError("Invalid revision pagination")
        revisions = await self._repository.list_revisions(program_id, before=before, limit=limit)
        return RevisionPage(
            revisions=tuple(
                RevisionSummary(program=revision.reference, content_digest=revision.content_digest)
                for revision in revisions
            ),
            next_cursor=revisions[-1].revision if len(revisions) == limit else None,
        )

    async def save(
        self,
        definition: ProgramDefinition,
        caller: Identity,
        *,
        expected_version: int = 0,
        presentation: ProgramPresentation | None = None,
        resource_selections: tuple[ProgramResourceSelection, ...] = (),
    ) -> ProgramDraft:
        definition = ProgramDefinition.model_validate_json(definition.model_dump_json())
        self.authorize(definition, caller)
        try:
            previous = await self._repository.get_draft(definition.program_id)
        except KeyError:
            previous = None
        if previous is not None:
            self.authorize(previous.definition, caller)
        if expected_version < 0 or (previous.version if previous else 0) != expected_version:
            raise ProgramConflict("Program draft changed; reload before saving")
        selections: dict[BodyPath, list[ProgramResourceSelection]] = {}
        for selection in resource_selections:
            try:
                target = definition.body_at(selection.body_path)
            except ValueError:
                raise ProgramContractError(
                    "Resource selection identifies an unavailable owned body"
                ) from None
            if not isinstance(target.implementation, GraphDefinition):
                raise ProgramContractError("Saved resource blocks require a visual composition")
            selections.setdefault(selection.body_path, []).append(selection)
        definition = await self._protect_body(definition, caller, (), selections)
        return await self._repository.save_draft(
            definition,
            expected_version=expected_version,
            presentation=presentation
            if presentation is not None
            else previous.presentation
            if previous
            else ProgramPresentation(),
        )

    @staticmethod
    def _calls(
        body: ProgramBody,
    ) -> Iterator[tuple[str, ProgramTarget, tuple[str | int, ...]]]:
        implementation = body.implementation
        if isinstance(implementation, GraphDefinition):
            for index, step in enumerate(implementation.steps):
                if isinstance(step, ProgramCallStep):
                    yield step.uid, step.program, ("implementation", "steps", index, "program")
        else:
            for name, target in implementation.children.items():
                yield name, target, ("implementation", "children", name)

    async def _protect_body[Body: ProgramBody](
        self,
        body: Body,
        caller: Identity,
        path: BodyPath,
        selections: Mapping[BodyPath, Sequence[ProgramResourceSelection]],
    ) -> Body:
        for name, schema in (("input", body.input_schema), ("output", body.output_schema)):
            try:
                InterfaceContract.check_schema(schema)
            except SchemaError, BindingContractError:
                raise ProgramContractError(f"Invalid program {name} schema") from None
        calls: dict[str, ProgramTarget] = {}
        for name, target, _ in self._calls(body):
            calls[name] = (
                await self._protect_body(target, caller, (*path, name), selections)
                if isinstance(target, ProgramBody)
                else target
            )
        body = body.with_program_calls(calls)
        implementation = body.implementation
        if isinstance(implementation, GraphDefinition):
            resources = implementation.resources
            if scoped := selections.get(path):
                if self._resource_snapshots is None:
                    raise ResourceSnapshotsUnavailable("Saved-resource library is not configured")
                resources = await self._resource_snapshots.materialize(
                    resources, tuple(scoped), caller
                )
            protected = tuple(
                [
                    await self._configuration.protect_resource(
                        resource, caller, allow_incomplete=True
                    )
                    for resource in resources
                ]
            )
            implementation = implementation.model_copy(update={"resources": protected}, deep=True)
        else:
            registration = self._applications.get(
                implementation.implementation, implementation.version
            )
            try:
                config = await self._configuration.protect_draft(
                    registration.config_schema, implementation.config, caller
                )
            except ValueError:
                raise ProgramContractError(
                    f"Invalid configuration for application program {implementation.implementation}"
                ) from None
            implementation = implementation.model_copy(update={"config": config}, deep=True)
        return body.model_copy(update={"implementation": implementation}, deep=True)

    async def revision(self, reference: ProgramRef, caller: Identity) -> ProgramRevision:
        revision = await self._repository.get_revision(reference)
        self.authorize(revision.definition, caller)
        return ProgramRevision.model_validate_json(revision.model_dump_json())

    async def validate(
        self, program_id: str, caller: Identity, *, expected_version: int
    ) -> ProgramValidation:
        draft = await self.draft(program_id, caller)
        if draft.version != expected_version:
            raise ProgramConflict("Program draft changed; reload before validation")
        try:
            await self._validate_publication(draft.definition, caller)
        except ProgramContractError as error:
            return ProgramValidation(version=draft.version, issues=(error.issue,))
        return ProgramValidation(version=draft.version)

    async def publish(
        self, program_id: str, caller: Identity, *, expected_version: int
    ) -> ProgramRevision:
        draft = await self.draft(program_id, caller)
        existing = await self._repository.get_publication(program_id, expected_version)
        if existing is not None:
            self.authorize(existing.definition, caller)
            return existing
        if draft.version != expected_version:
            raise ProgramConflict("Program draft changed; reload before publication")
        await self._validate_publication(draft.definition, caller)
        return await self._repository.publish(draft)

    async def _validate_publication(self, definition: ProgramDefinition, caller: Identity) -> None:
        await self._validate_body(definition, caller, (), {}, ())

    async def validate_revision(self, revision: ProgramRevision, caller: Identity) -> None:
        """Recheck a frozen revision's application contracts before execution preparation."""
        self.authorize(revision.definition, caller)
        await self._validate_publication(revision.definition, caller)

    async def _validate_body(
        self,
        body: ProgramBody,
        caller: Identity,
        ancestors: tuple[ProgramRef, ...],
        validated: dict[ProgramRef, ProgramRevision],
        path: tuple[str | int, ...],
    ) -> None:
        for name, schema in (("input", body.input_schema), ("output", body.output_schema)):
            try:
                InterfaceContract.check_schema(schema)
            except SchemaError, BindingContractError:
                raise ProgramContractError(
                    f"Invalid program {name} schema", path=(*path, f"{name}_schema")
                ) from None
        try:
            body.implementation.validate_executable()
        except ValueError as error:
            raise ProgramContractError(
                str(error), code=ProgramIssueCode.TOPOLOGY, path=(*path, "implementation")
            ) from None
        implementation = body.implementation
        if isinstance(implementation, GraphDefinition):
            try:
                self._bundles.validate_snapshot(implementation.resources)
                for step in implementation.steps:
                    if not isinstance(step, ProgramCallStep):
                        self._bundles.resolve(step.element, implementation.resources)
                for condition in implementation.conditions:
                    self._bundles.resolve(condition.condition, implementation.resources)
            except ValueError, KeyError:
                raise ProgramContractError(
                    "Missing or invalid construction resources",
                    code=ProgramIssueCode.CONSTRUCTION,
                    path=(*path, "implementation", "resources"),
                ) from None
        elif isinstance(implementation, ApplicationDefinition):
            try:
                registration = self._applications.get(
                    implementation.implementation, implementation.version
                )
                configuration = registration.configuration(implementation)
                self._bundles.validate_embedded(configuration)
            except ValueError:
                raise ProgramContractError(
                    "Invalid configuration or missing required program dependencies",
                    path=(*path, "implementation", "config"),
                ) from None
        children: dict[str, ProgramBody] = {}
        for name, target, source in self._calls(body):
            if isinstance(target, ProgramBody):
                await self._validate_body(target, caller, ancestors, validated, (*path, *source))
                children[name] = target
            else:
                try:
                    children[name] = (
                        await self._validate_dependency(target, caller, ancestors, validated)
                    ).definition
                except ValueError, KeyError, PermissionError:
                    raise ProgramContractError(
                        "Referenced program is unavailable or recursive",
                        code=ProgramIssueCode.REFERENCE,
                        path=(*path, *source),
                    ) from None
        try:
            self._contracts.validate(body, children)
        except BindingContractError as error:
            raise ProgramContractError(
                str(error), code=ProgramIssueCode.BINDING, path=(*path, *error.path)
            ) from None

    async def _validate_dependency(
        self,
        reference: ProgramRef,
        caller: Identity,
        ancestors: tuple[ProgramRef, ...],
        validated: dict[ProgramRef, ProgramRevision],
    ) -> ProgramRevision:
        if reference in ancestors:
            raise ValueError("Recursive published program dependency")
        if reference in validated:
            return validated[reference]
        revision = await self.revision(reference, caller)
        await self._validate_body(
            revision.definition, caller, (*ancestors, reference), validated, ()
        )
        validated[reference] = revision
        return revision
