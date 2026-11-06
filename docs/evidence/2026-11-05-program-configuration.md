# Shared Program configuration and saved-resource selection

Recorded 2026-11-05. This is a configuration/authoring checkpoint toward the thin
Engineering UI journey, not acceptance of that whole journey or a replacement
execution workbench.

## Behavior and ownership

- `components/schema/SchemaValue` renders local schema references, nested objects,
  arrays, enums, booleans and scalar fields. Optional omission remains distinct from
  explicit values. Array rows retain identity across local removal. Complex,
  unresolved and deeply recursive shapes use the existing JSON editor. This is
  presentation assistance; backend validation remains authoritative.
- The JSON editor and local-reference resolver moved out of the Programs feature
  into shared schema components. Old implementations/import paths were removed.
- `SavedResourcePicker` owns owner/team-scoped paginated catalog selection.
  Graph `ResourcePicker` retains graph-specific replacement/adoption semantics over
  that selector. Backend configuration composes a separate bundle-capture adapter;
  the generic schema renderer has no API, credential or construction dependency.
- `ResourceBundleField` explicitly calls the existing protected snapshot endpoint
  with the selected source revision. Redacted catalog configuration is never copied
  into a bundle. Display shows the selected name and closure size, not credential
  references or configuration contents. Later edits require explicit recapture.
- Pending capture locks draft editing, publication and library navigation to prevent
  a late response from overwriting newer edits. View replacement aborts the request
  and guards state updates. This does not roll back server work already committed.
- Existing `ExecutionSelectionFields` supplies approved profile/named-environment
  choices, including unavailable saved names. No engine-specific placement settings
  or SDK contracts were added to the UI.

No scheduler, construction pipeline, backend operation or execution policy was added.
The interim runner only received the shared JSON-editor import. Its lifecycle and
raw invocation input remain interim behavior awaiting convergence.

## Verification

From `ui/`:

```sh
npm run typecheck
node tests/run-api-contracts.mjs contracts
NODE_ENV=production node tests/build-placement-browser.mjs /tmp/unifai-program-fields-browser
```

All pass. The contracts include production server-rendered nested schema fields,
optional omission, array controls, reference resolution, recursive/complex fallback,
escaped user content and no input mutation, plus the existing graph/session contracts.
They do not replace interactive browser checks. Final fixture build: **4.48s**;
Vite reports the existing circular vendor chunks and large-chunk warnings.

Native production client gate, using the dedicated UnifAI services:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  'multi-agent/tests/integration/ui/test_editor_client.py::test_existing_typescript_editor_clients_use_native_services[api]' \
  'multi-agent/tests/integration/ui/test_editor_client.py::test_existing_typescript_editor_clients_use_native_services[programs]' \
  --ui-clients -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**2 passed in 12.57s**, no skips or reported warnings. This exercises actual API
clients and native persistence/execution contracts, not React interactions. Later
changes in this checkpoint were presentation-only and received the final checks
above and browser verification below. The underlying client/capture contracts were
unchanged. Ruff check/format of the changed Python fixture and skill validation pass.

## Actual browser/API/process journey

Started the maintained `support.program_browser` runner with the final built assets,
dedicated Mongo/Redis and its isolated signed-cookie identity. The actual production
App/provider tree and MAS routes were used. External identity/settings and installed
test operation/Program behavior were controlled peers. No paid provider was called.

Observed through browser controls:

1. Create `placed_operation`, name the Program, and select the approved `process`
   placement using the reused placement control.
2. Select Saved text operation and capture it. The fixture delays the actual native
   capture by two seconds. During that request, `Program name` is disabled and
   `Publish program` is disabled; the library and configuration controls are locked.
3. Capture reports the saved operation and its three-resource dependency closure.
   Publish revision 1 through the normal draft/publication endpoints.
4. Invoke with `{"text":"browser configured placement"}`. Authoritative observation
   changes from running to completed. The result contains
   `"text":"typed:saved-middle:browser configured placement"`, the actual execution
   ID `20b83ff5-e967-4584-b52d-998c69260cd7`, and invocation key `work`.
5. Reload and reopen from the library. The captured closure summary and process
   preference remain saved, with revision 1 available independently of the draft.
6. Open the existing graph editor. Its shared catalog still offers saved operations
   and its distinct shared-resource replacement/adoption checkbox.
7. Start another delayed capture and switch from Personal to Team. After the delayed
   request, the replacement view contains neither the old capture summary nor the
   old Program heading. Returning to Personal shows the library with no leaked editor.
   This is an owner-view lifetime check, not complete team membership/navigation proof.

The final visible configuration is recorded in the
[screenshot](assets/2026-11-05-program-configuration.jpg).
The fixture does not serve the separate administration service: browser/server logs
include `GET /api4/admin_config/access.check` 404s, plus a favicon 404. MAS routes
in this scenario completed normally; no administration acceptance is claimed.

Closed owned tabs and stopped both fixture runs. Final API and identity logs each
confirm `Application shutdown complete`. The final runner removed its unique database
`unifai_program_browser_983471225de8434c92c399224057d6db`; the preceding run also
confirmed removal of its own database. Signed-cookie cleanup uses the owned fixture
context. Shared Mongo/Redis services were retained. The initial restricted attempt
failed before starting an API because loopback/Mongo access was denied; the later
permitted runs above supply the evidence.

## Source identity and remaining acceptance

[The focused manifest](2026-11-05-program-configuration-source.json) records 27 source
files, the screenshot hash and final built workspace script hash. Source aggregate:
`939e2c698af94cdeb24a0b6e3eeef27a607013d12b8da0030b57f63101cbec5f`.
This is not a complete dependency/image manifest. No remote images or companion
Run Engine sources were changed.

Pinned structured invocation, shared execution hierarchy/review/artifact inspection,
the actual Engineering browser journey, live coding/production verification, broad
accessibility/responsiveness, complete owner-switch and concurrency matrices, remote
environments and final editor/runner retirement remain required. No full JSON Schema
renderer, live-model acceptance, scalability claim or overall completion is implied.
