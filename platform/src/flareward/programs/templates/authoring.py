"""Native async authoring preserves identity, editing semantics, and protected configuration."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from flareward.elements.construction.secrets import ConfigurationSecrets
from flareward.programs.templates.contracts import (
    BlueprintAuthoringRepository,
    BlueprintData,
    BlueprintDocument,
    BlueprintPage,
)
from flareward.programs.templates.exceptions import BlueprintConflictError
from flareward.programs.templates.metadata import validate_metadata_keys
from flareward.programs.templates.models.prompt_shortcuts import PromptShortcuts
from flareward.resources.references import RefWalker
from flareward.services.identity.domain import Identity


class BlueprintAuthoringService:
    def __init__(
        self,
        repository: BlueprintAuthoringRepository,
        draft_schema: type[BaseModel],
        configuration: ConfigurationSecrets,
    ) -> None:
        self._repository = repository
        self._draft_schema = draft_schema
        self._configuration = configuration

    def schema(self) -> dict:
        return self._draft_schema.model_json_schema()

    async def create(
        self, spec: BlueprintData, caller: Identity, *, metadata: BlueprintData | None = None
    ) -> BlueprintDocument:
        metadata = metadata or {}
        validate_metadata_keys(metadata)
        protected, references = await self._prepare(spec, caller)
        now = datetime.now(UTC)
        document = BlueprintDocument(
            blueprint_id=str(uuid4()),
            identity=caller,
            created_at=now,
            updated_at=now,
            spec_dict=protected,
            rid_refs=references,
            metadata=metadata,
            version=1,
        )
        await self._repository.create(document)
        return document

    async def get(
        self, blueprint_id: str, caller: Identity, *, expected_version: int | None = None
    ) -> BlueprintDocument:
        document = await self._repository.get(blueprint_id)
        if not caller.owns(document.identity):
            raise PermissionError("The caller does not own this blueprint")
        if expected_version is not None and expected_version != document.version:
            raise BlueprintConflictError()
        return document

    async def list(
        self, caller: Identity, *, skip: int = 0, limit: int = 100, sort_desc: bool = True
    ) -> BlueprintPage:
        if skip < 0 or not 1 <= limit <= 1000:
            raise ValueError("Invalid blueprint pagination")
        return await self._repository.list(caller, skip=skip, limit=limit, sort_desc=sort_desc)

    async def update(
        self,
        blueprint_id: str,
        spec: BlueprintData,
        caller: Identity,
        *,
        expected_version: int | None = None,
    ) -> BlueprintDocument:
        previous = await self.get(blueprint_id, caller, expected_version=expected_version)
        if "prompt_shortcuts" not in spec and "prompt_shortcuts" in previous.spec_dict:
            spec = {**spec, "prompt_shortcuts": previous.spec_dict["prompt_shortcuts"]}
        protected, references = await self._prepare(spec, caller)
        return await self._replace(previous, spec_dict=protected, rid_refs=references)

    async def delete(
        self, blueprint_id: str, caller: Identity, *, expected_version: int | None = None
    ) -> None:
        previous = await self.get(blueprint_id, caller, expected_version=expected_version)
        if not await self._repository.delete(previous):
            raise BlueprintConflictError()

    async def set_metadata(
        self,
        blueprint_id: str,
        metadata: BlueprintData,
        caller: Identity,
        *,
        expected_version: int | None = None,
    ) -> BlueprintDocument:
        previous = await self.get(blueprint_id, caller, expected_version=expected_version)
        validate_metadata_keys(metadata)
        return await self._replace(previous, metadata={**previous.metadata, **metadata})

    async def set_shortcuts(
        self,
        blueprint_id: str,
        prompts: list[dict],
        caller: Identity,
        *,
        expected_version: int | None = None,
    ) -> BlueprintDocument:
        previous = await self.get(blueprint_id, caller, expected_version=expected_version)
        shortcuts = PromptShortcuts.parse(prompts)
        spec = {**previous.spec_dict, "prompt_shortcuts": shortcuts.to_storage()}
        return await self._replace(previous, spec_dict=spec)

    async def _prepare(
        self, spec: BlueprintData, caller: Identity
    ) -> tuple[BlueprintData, list[str]]:
        try:
            draft = self._draft_schema.model_validate(spec, by_name=True)
        except ValidationError:
            raise ValueError("Invalid blueprint configuration") from None
        references = sorted(set(RefWalker.external_rids(draft)))
        return await self._configuration.protect(draft, caller), references

    async def _replace(self, previous: BlueprintDocument, **changes) -> BlueprintDocument:
        updated = previous.model_copy(
            update={**changes, "version": previous.version + 1, "updated_at": datetime.now(UTC)},
            deep=True,
        )
        if not await self._repository.replace(previous, updated):
            raise BlueprintConflictError()
        return updated
