"""Application-owned source persistence scenarios shared by memory and Mongo tests."""

import asyncio
from datetime import UTC, datetime, timedelta

from mas.application.events import EventSourceConflict, EventSourceStore, StoredEventSource
from mas.application.execution.models import PreparedExecution
from mas.core.identity import Identity
from mas.domain.execution.events import ProgramEventSource
from mas.domain.programs.models import ProgramRef


class MemoryEventSources:
    def __init__(self) -> None:
        self.rows: dict[str, str] = {}
        self.revoked: set[str] = set()

    async def create(self, registration: StoredEventSource) -> None:
        if registration.definition.source_id in self.rows:
            raise ValueError("Source already exists")
        self.rows[registration.definition.source_id] = registration.model_dump_json()

    async def get(
        self, source_id: str, owner: Identity | None = None, *, active_at: datetime | None = None
    ) -> StoredEventSource:
        registration = StoredEventSource.model_validate_json(self.rows[source_id])
        source = registration.definition
        if (owner is not None and not source.owner.owns(owner)) or (
            active_at is not None and (source_id in self.revoked or source.expires_at <= active_at)
        ):
            raise KeyError(source_id)
        return registration.model_copy(
            update={"definition": source.model_copy(update={"revoked": source_id in self.revoked})}
        )

    async def list(self, owner: Identity, *, after: str, limit: int) -> list[ProgramEventSource]:
        sources = [(await self.get(identifier)).definition for identifier in sorted(self.rows)]
        return [value for value in sources if value.owner.owns(owner) and value.source_id > after][
            :limit
        ]

    async def revoke(self, source_id: str, owner: Identity) -> None:
        await self.get(source_id, owner)
        self.revoked.add(source_id)

    async def rotate(
        self, source_id: str, owner: Identity, expected_revision: int, digest: str, *, now: datetime
    ) -> None:
        registration = await self.get(source_id, owner, active_at=now)
        if registration.credential_revision != expected_revision:
            raise EventSourceConflict("Event source credential revision is stale")
        self.rows[source_id] = registration.model_copy(
            update={"secret_sha256": digest, "credential_revision": expected_revision + 1}
        ).model_dump_json()


def source_registration(
    source_id: str = "a" * 32, *, owner: Identity | None = None, expired: bool = False
) -> StoredEventSource:
    now = datetime.now(UTC) - timedelta(hours=2 if expired else 0)
    prepared = PreparedExecution(format="test/1", payload_json='{"frozen":true}')
    return StoredEventSource(
        definition=ProgramEventSource(
            source_id=source_id,
            name="Event source",
            owner=owner or Identity.user("owner"),
            approved_by=Identity.user("owner"),
            approved_at=now,
            expires_at=now + timedelta(hours=1),
            program=ProgramRef(program_id="program", revision=1),
            event_type="issue@1",
            input_schema={},
            prepared_sha256=prepared.content_digest,
        ),
        prepared=prepared,
        secret_sha256="b" * 64,
    )


async def assert_event_source_store_contract(store: EventSourceStore) -> None:
    registration = source_registration()
    owner = registration.definition.owner
    await store.create(registration)
    assert await store.get(registration.definition.source_id, owner) == registration
    # Readers never receive a mutable handle into persisted approval/preparation.
    loaded = await store.get(registration.definition.source_id, owner)
    loaded.definition.input_schema["changed"] = True
    assert (await store.get(registration.definition.source_id, owner)).definition.input_schema == {}
    team = source_registration("c" * 32, owner=Identity.team(owner.id))
    await store.create(team)
    with_id = await store.list(owner, after="", limit=1)
    assert [value.source_id for value in with_id] == [registration.definition.source_id]
    assert await store.list(owner, after=registration.definition.source_id, limit=1) == []
    for action in (
        store.get(registration.definition.source_id, team.definition.owner),
        store.revoke(registration.definition.source_id, team.definition.owner),
    ):
        try:
            await action
        except KeyError:
            pass
        else:
            raise AssertionError("Source ownership must include identity type")
    before = await store.get(registration.definition.source_id, owner)
    outcomes = await asyncio.gather(
        *(
            store.rotate(registration.definition.source_id, owner, 0, digest, now=datetime.now(UTC))
            for digest in ("1" * 64, "2" * 64)
        ),
        return_exceptions=True,
    )
    assert sum(outcome is None for outcome in outcomes) == 1
    assert sum(isinstance(outcome, EventSourceConflict) for outcome in outcomes) == 1
    rotated = await store.get(registration.definition.source_id, owner)
    assert rotated.credential_revision == 1 and rotated.secret_sha256 in {"1" * 64, "2" * 64}
    assert rotated.definition == before.definition and rotated.prepared == before.prepared
    await store.revoke(registration.definition.source_id, owner)
    await store.revoke(registration.definition.source_id, owner)
    assert (await store.get(registration.definition.source_id, owner)).definition.revoked
    try:
        await store.rotate(
            registration.definition.source_id, owner, 1, "3" * 64, now=datetime.now(UTC)
        )
    except KeyError:
        pass
    else:
        raise AssertionError("Revoked sources must not rotate")
    for registration in (before, source_registration("d" * 32, expired=True)):
        if registration.definition.source_id not in {before.definition.source_id}:
            await store.create(registration)
        try:
            await store.get(registration.definition.source_id, active_at=datetime.now(UTC))
        except KeyError:
            pass
        else:
            raise AssertionError("Revoked/expired sources must not authorize delivery")
