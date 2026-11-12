# Coordinator configuration resource capture — 2026-11-11

Step A progress in the [coordinator milestone](../architecture/coordinator-programs/README.md).
This advances C3; it does not complete the milestone or full platform target.

## Implemented behavior and boundaries

`ProgramResourceSelection.configuration_path` addresses a coordinator's declared
`ElementBundle` field. `body_path` still addresses its enclosing owned Program body;
it never traverses a pinned revision. Graph selections omit `configuration_path`.
Names/dictionary keys and integer array indexes remain distinct, with a 64-segment
configuration-path bound. Missing object fields can be supplied; array positions
must already exist. Ordinary incomplete drafts remain supported.

`ConfigurationResources` belongs to Element construction and knows no Program,
HTTP, database or engine types. It uses the actual Pydantic configuration structure,
including aliases and selected union variants, rather than trusting schema titles
or treating arbitrary JSON as a capability. Existing schema-aware secret protection
normalizes configuration before captures and protects portable results afterward.

The shared `SavedResourceResolver` retains authorized transitive collection, source
revision rereads, construction validation, existing protected references and explicit
adoption. It now accepts an existing bundle for replacement checks. Canonical fields
and aliases identify the same destination. Changed roots or dependencies require
`replace`; duplicate field selections are rejected, including alternate aliases.
Each configuration bundle has its own construction scope; graph replacement still
applies to that graph's shared resource scope. Older publications remain unchanged.

The existing UI picker retains protected previews and now queues source/destination
commands for save-time revalidation. `resource-selections.ts` owns pending selection
identity across graph/custom scopes. Local preview digests discard stale selections
when configuration changes or array items move; the digest is removed before API
submission. No alternate authoring or execution endpoint was introduced.

## Tested source

Lumora HEAD: `54d0a42a8141b878b85248deec6c7742c4bb4274`, with uncommitted changes.
Source/test delta SHA-256: `02922f19e37486a7e8d8cdcfb920a3b2dad1005b788b6ce29fe4a9a387be1599`.
Digest method: `git diff --binary -- platform/src platform/tests ui/client ui/tests`,
then sorted untracked paths, NUL and file bytes in those directories.
Run Engine remains `60393440efd3876cd6c81e0b013e8bf6d9167659`; no engine edits.

## Verification

From the repository root:

```sh
.venv/bin/python -m pytest platform/tests/domain platform/tests/application platform/tests/adapters/run_engine platform/tests/architecture -q --tb=short --maxfail=3
```

**930 passed.** Includes 19 new configuration-capture cases: aliases/nested paths,
list/dictionary/optional/union targets, owned-body isolation, duplicates, explicit
root/dependency adoption, stale/foreign sources, protected secrets and invalid fields.
Existing draft, graph snapshot and architecture tests remain green.

```sh
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest platform/tests/integration/mongo/test_resource_snapshots.py 'platform/tests/integration/ui/test_editor_client.py::test_existing_typescript_editor_clients_use_native_services[programs]' --ui-clients -q --tb=short --maxfail=2
```

**9 passed.** Shared graph/custom lifecycle scenario runs on actual Local thread and
process invocation runners with real Mongo. It saves a transitive closure, publishes,
changes a source dependency, runs the old publication, rejects implicit replacement,
adopts explicitly, executes the new revision and reruns the older pinned revision.
Other cases preserve private built-in overlays. These tests use an ASGI transport
and explicit identity fixture; the production TypeScript journey separately uses
real TCP FastAPI and its existing signed-session harness. Its coordinator save now
supplies a resource-selection command instead of relying on an embedded preview.

From `ui`, all passed:

```sh
pnpm --config.verify-deps-before-run=false run typecheck
pnpm --config.verify-deps-before-run=false run test:contracts
pnpm --config.verify-deps-before-run=false run build
```

UI contracts cover typed path conversion, escaped dictionary keys, scope-aware
selection replacement and stale array/preview removal. The production build retains
the existing warning for chunks above 500 kB. Changed Python files pass Ruff
`I,F821,F822,F823,E9`; `git diff --check` passes.

An intermediate alias-replacement failure exposed canonical/alias duplication and
was corrected before the passing gates. A TypeScript fixture typing error was also
corrected. No unresolved failure remains in this scoped verification.

## Remaining scope

Full browser interaction, nested canvas authoring and unsupported schema-form
variants remain part of the UI milestone. Owned configuration capture is verified
at the application boundary here, not a new remote owned-child lifecycle claim.
No paid provider call, Temporal recovery gate, image rebuild or Kubernetes/OpenShell
matrix ran. Those remain batched acceptance work; existing remote images do not
certify the current source. No commit or push was performed.

Next: finish configured-interface/dependency declarations and audit Step A, then
continue review composition/generic routing, observation/UI and current-source
remote acceptance in the agreed order.
