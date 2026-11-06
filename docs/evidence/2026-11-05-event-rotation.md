# Event source credential rotation

Human owners can rotate a source's bearer credential using an expected revision.
The compare-and-swap updates its hash and revision atomically under owner, active,
expiry and Mongo-clock conditions; the source ID, pinned preparation, consent and
event deduplication identity remain unchanged. A stale revision fails with 409.
Settings expose the revision; the new credential is returned only by the no-store
rotation response. If that response is lost after a commit, inspect the revision
and rotate again: the lost secret cannot be recovered. No plaintext is stored.

Authentication begun after a committed rotation rejects the old credential. A
delivery authenticated before rotation can still proceed; rotation is not an
atomic stale-attempt fence on subsequent admission or external effects.
Prototype Mongo source documents without `credential_revision` are not migrated;
recreate those sources in this fresh platform before relying on them.

Focused application, consent, access and architecture tests: 49 passed. Dedicated
Mongo, real HTTP and production TypeScript-client tests: 4 passed, covering
compare-and-swap, source lifetime, human access, secret privacy, old-key rejection,
and deduplication. Lost-response recovery was exercised with an application-owned
store double, not an injected Mongo network failure. Strict mypy passed for four
production modules; Ruff and UI typecheck passed. No heavy remote matrix ran.

The 11 changed Python/TypeScript source and test files have aggregate SHA-256
`79316c7c8a40cc5833e427db85ddd64e0836cffbe8d160ebfe4fae835bed59fc`,
over a sorted compact JSON path-to-file-hash map.
