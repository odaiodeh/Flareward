from abc import ABC, abstractmethod
from typing import Any

from flareward.programs.templates.contracts import BlueprintDocument, BlueprintSummary
from flareward.programs.templates.models.blueprint import BlueprintDraft
from flareward.programs.templates.models.prompt_shortcuts import PromptShortcuts
from flareward.services.identity.domain import Identity


class BlueprintRepository(ABC):
    # ────────────────────────────── Writes ──────────────────────────────
    @abstractmethod
    def save(
        self,
        identity: Identity,
        spec: BlueprintDraft,
        rid_refs: list[str],
        metadata: dict[str, Any],
    ) -> str:
        """Persist *spec* owned by *identity* and return the generated blueprint_id."""

    @abstractmethod
    def update(self, *, blueprint_id: str, spec: BlueprintDraft, rid_refs: list[str]) -> bool:
        """Replace an existing draft.  Return True if a document was modified."""

    @abstractmethod
    def set_metadata(self, *, blueprint_id: str, metadata: dict[str, Any]) -> bool:
        """Merge keys into the metadata sub-document (key-level upsert, not full replace)."""

    @abstractmethod
    def set_prompt_shortcuts(self, *, blueprint_id: str, shortcuts: PromptShortcuts) -> bool:
        """Persist prompt shortcuts for a blueprint. Empty shortcuts clear the stored value."""

    # ────────────────────────────── Reads by ID ─────────────────────────
    @abstractmethod
    def load(self, blueprint_id: str) -> BlueprintDocument:
        """Load a blueprint document by its globally-unique ID or raise `KeyError`."""

    @abstractmethod
    def delete(self, blueprint_id: str) -> bool:
        """Delete by ID.  Return `True` iff a document was removed."""

    @abstractmethod
    def exists(self, blueprint_id: str) -> bool:
        """Return `True` if that ID is present in the store."""

    @abstractmethod
    def load_many(self, blueprint_ids: list[str]) -> list[BlueprintDocument]:
        """Load multiple blueprint documents by their IDs in a single operation."""

    # ────────────────────────────── Listings / Stats ────────────────────
    @abstractmethod
    def list_ids(
        self,
        *,
        identity: Identity | None = None,
        skip: int = 0,
        limit: int = 100,
        sort_desc: bool = True,
    ) -> list[str]:
        """Return blueprint IDs, optionally scoped to *identity*, with pagination."""

    @abstractmethod
    def list_docs(
        self,
        *,
        identity: Identity | None = None,
        skip: int = 0,
        limit: int = 100,
        sort_desc: bool = True,
    ) -> list[BlueprintDocument]:
        """Return blueprint documents, optionally scoped to *identity*."""

    @abstractmethod
    def list_summaries(
        self,
        *,
        identity: Identity | None = None,
        skip: int = 0,
        limit: int = 100,
        sort_desc: bool = True,
    ) -> list[BlueprintSummary]:
        """Return lightweight blueprint summaries (no full spec)."""

    @abstractmethod
    def list_direct_usage(self, rid: str) -> list[str]:
        """Return blueprint IDs whose catalogue entries contain *rid* directly."""

    @abstractmethod
    def count_usage(self, rid: str) -> int:
        """Count how many blueprints reference a given resource ID *rid*."""

    @abstractmethod
    def count(self, identity: Identity | None = None) -> int:
        """Total blueprint count, optionally scoped to *identity*."""

    @abstractmethod
    def name_exists_for_identity(
        self,
        identity: Identity,
        name: str,
        *,
        exclude_blueprint_id: str | None = None,
    ) -> bool:
        """Return True if *identity* already owns a blueprint with this *name*.

        When *exclude_blueprint_id* is given the check ignores that document
        (used during rename/update so a blueprint doesn't conflict with itself).
        """

    @abstractmethod
    def delete_by_identity(self, identity: Identity) -> int:
        """Delete all blueprints owned by *identity*.  Returns the count of deleted documents."""
