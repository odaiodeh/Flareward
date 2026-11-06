---
name: debug-program-composition
description: Diagnose UnifAI program-library authoring, pinned composition, Map/Repeat/Choose/Wait, native replay and the Programs UI.
---

# Diagnose program composition

Read [current composition contracts](../../../docs/program-platform-development.md#core-composition-programs)
and selected [evidence](../../../docs/evidence/README.md#historical-lookup).
Start/resume with [current status](../../../docs/status.md) and [the active plan](../../../docs/plan.md);
read relevant guide/archive sections only. Graph and
application are internal implementation kinds, not separate public libraries.
Map/Repeat/Choose/Wait are installed,
versioned application programs, not a third workflow runtime. A reusable definition
becomes a child when another execution calls it; operations need no child wrapper
for ordinary graph/code invocation.

Trace authored configuration → `ApplicationRegistration.configuration` → pinned
revision → prepared request → runtime ports. Core registrations are installed by
`bootstrap.programs`; workers preload the same core module. New implementations
must use the existing registry, publication and engine path, not compiler branches.

Binding readiness now uses application `ProgramContracts` / `BindingProjection` and
reports `INVALID_BINDING` with authored locations. A missing required binding is a
publication error; runtime contract tests must instead supply malformed dynamic
values through an admissible mapping. Check owned/pinned interfaces, actual input
aliases and serialized result schemas. `ProgramService` takes the element registry
and composes its stateless validators. The compiler repeats revision validation
before native preparation. Do not bypass this by constructing a structural revision.

Bundled schema navigation lives in application `interfaces.InterfaceContract`;
`graph_data.GraphDataScope` resolves graph input/results without transplanting
reference documents. Unknown/nonindexed/unreachable producers, self-result reads,
unordered reads and provably disjoint public JSON types reject publication.
Pydantic coercion stays separate from strict published JSON types. `active`/`all`
graph join preferences freeze in revisions and lower to public engine policies.
Use `test_graph_data_contracts.py`, the value-binding native policies and production
client read-order correction journey. Application `GraphFlow` additionally rejects
acyclic active-path reads when a consumer can activate without its producer. Use
shared `support/graph_routes.py`, application/native `test_graph_flow.py` and branch-
local child observations. It analyzes declared outcomes without executing conditions
or folding plugin configuration. Cycles/activation expansions above 256 retained
terms defer to runtime; reachability caches retain at most 64 source sets per flow.
Do not claim general cyclic availability, arbitrary mutable state schemas or accepted-work proof.

Static projection is conservative: unknown/open/dynamic paths retain runtime
checks. Keep nested `$id` scopes unknown unless their context is modeled correctly;
never resolve every fragment against an unrelated root. Recursive static analysis
must terminate. Interface schemas use Draft 2020-12 and bundled references, with
no URL retrieval during validation/execution. Use a schema-aware resource traversal
so `$ref` strings in enum/default/example values remain ordinary data. Reject
unknown dialects safely instead of evaluating them under different semantics.
Exercise `application/test_binding_contracts.py`, restored-revision adapter checks,
thread/process alias and dynamic-error scenarios, root-input HTTP privacy and the
production client readiness/correction journey. These do not prove graph-wide
data availability, general static type compatibility or arbitrary Python call shapes.

Backend configurations may implement `ChildContracts.child_contracts()`, mapping
required aliases to application-owned `ChildContract` declarations. The same
validator checks their request projections/scopes and consumed child results against
owned/pinned public and installed interfaces. No scope schema means normalized
installed input (when declared), otherwise public input. `inputs=None` passes the
scope; `{}` sends an empty object. Map/Repeat scope models also construct runtime
requests; Choose checks all branches. Open/unknown values retain runtime checks.
When `result_model` describes the whole returned model, `outputs` must project its
required fields, not just the field used in a branch. Publication validates that
projection against the model. Use a narrower result model for a deliberately
partial projection. `coding_feature@1` declares the required result shape and
validates the complete runtime value. Optional defaults need not become required
paths: its graph/backend publication test covers an omitted optional review.
Use `application/test_child_contracts.py`, shared typed/custom-coordinator fixtures,
Local controls/model scenarios and the production readiness/correction journey.
Declarations are trusted implementation contracts, not static proof of arbitrary
Python or another persisted orchestration language. Whole-value projections use the
same checks; do not claim arbitrary graph-state/data availability or remote/replay proof.

Owned `ProgramBody` targets are supported in graph calls/backend child aliases.
They have no owner/library ID; use the enclosing published reference/digest plus
the stable UID/alias `body_path`. Save/protect/publish recursively. A published
reference resets the source address; paths must not traverse it. Resource source
selections carry the graph scope's `body_path`. Inline profile defaults inherit,
published defaults remain independent, and environment imports stay explicit.
Compilation uses the existing native child/runtime path. Keep prepared payloads
scope-local instead of copying the enclosing revision into every child. Current
entrypoint/prepared formats are `unifai-program-v5` / `runengine/request-v10`.
Exercise `application/test_owned_programs.py`, `domain/test_program_bodies.py`,
`domain/test_execution_source.py`, `adapters/run_engine/test_owned_compilation.py`
and shared Local composition/client scenarios. UI inline authoring and remote
recovery are still outstanding; focused compilation is not a remote cleanup proof.

Installed backend models are enforced centrally by application `ApplicationInvoker`.
Published input schemas check raw submitted intent; installed input models normalize
the implementation request. Installed result models normalize output before the
published output schema checks it. Preserve canonical serialized names/computed fields,
finite portable JSON and safe errors. `ApplicationCall` groups installed function/model
references in adapter payloads; no live registry crosses that boundary. Use shared
`support/typed_programs.py`, application invocation, Local model and production client
tests. RootModel arrays work directly and through graph/backend calls; separately
observed normalized inputs remain unfinished. Validators,
serializers and defaults must be pure/deterministic; effects use runtime ports. Local
checks do not establish replay or current-image remote acceptance.

`Projection` selects one complete path/literal value or constructs named fields.
Call inputs and graph return values support arrays/scalars/null; named graph channel
updates remain objects. `input` is the original graph invocation JSON. `results[uid]`
is the latest actual typed-operation/Program result, not occurrence history. Parallel
keys merge independently. Mapping/resume writes to these scopes reject. State-based
nodes do not index their entire state. Graph-state contract is `unifai-graph-state-v3`.
Use domain binding, application literal/read-only, adapter scope and Local value-binding
tests, shared `support/value_operations.py` factories and the production array journey.
Application `ProgramState` owns existing channel schemas and safe updates.
`StateContracts` checks graph initialization, output targets, installed channel
access and overlapping declared writers. Ordered writers require acyclic ordering;
explicit reduce uses existing reducers, some with overwrite semantics. Conditions
cannot declare writes. Actual returned node changes must fit declared writes and
concrete channel types. Use application `test_program_state.py` /
`test_state_contracts.py`, shared `support/state_nodes.py` and native
`test_state_contracts.py` for privacy, prepublication refusal and thread/process
dynamic failures. These are cooperative contracts, not a sandbox for arbitrary
Python. Keep cyclic/complex-flow availability, arbitrary state schemas and history/
retention work open. Canonical publication rejects mixed ordinary/conditional source
modes. The canvas guides explicit removal/labeling; it never silently drops an edge.
Blueprint `after` links to declared branch targets are metadata, not extra ordinary
edges; unmapped conditional dependencies reject conversion. Exercise both redundant-
after and branch-only imports through real process conditions. `END` requires a
declared destination like every label. There is no per-node race-join API here.

Authoring uses `{definition, expected_version, presentation?, resource_selections?}` and returns a
`ProgramDraft` envelope. Zero creates; edits carry the loaded version. Publication
requires that observed version and retries the same source idempotently, even after
a later edit. Program draft versions and published revision numbers are different
identities. Mongo publication counters can have gaps; do not guess the next number.
Keep presentation out of executable revisions. The shared memory/Mongo assertions
live in `support/program_store_contracts.py`; migrate callers rather than adding
old-format aliases or optional publication fences.

Drafts may retain unfinished graph entry/exit, connections and dependency bindings.
Unique identities, typed configuration and private-field protection remain
mandatory. `POST /programs/{id}/validation` carries `{expected_version}` and returns
versioned readiness with safe code/message/path/severity issues. Validation is
read-only; publication repeats the same checks. `ProgramRevision` independently
rejects incomplete structure on construction/restore. Readiness does not certify
profile/environment admission, concrete values or native engine plan acceptance.
Schema-aware incomplete model configurations now save through `ConfigurationDraft`
and the same secret service. Preserve schema metadata rather than constructing fake
runtime models. Supplied shape/constraints/field validators still apply; full model
semantics and embedded construction are publication/compilation gates. Nested
aliases, unions, collections, private-field declarations and owner-scoped opaque
references share this path. Ambiguous nonempty variants fail closed. Bundles may
be structurally valid while registered resource configuration is incomplete: never
skip the resolver's embedded/snapshot validation. Factory revalidation must accept
canonical names after alias normalization. Use `test_configuration_drafts.py` in
application/Local integration, shared `support/draft_configuration.py`, Mongo secret
contracts and the production client journey. An in-memory authoring secret store
does not supply credentials to a separate process receiver: use the normal encrypted
Mongo/receiver fixture for that proof. The interim editor still requires entry/exit;
do not grow another editor merely to expose this backend slice.

Use `domain/test_program_publication.py`, `application/test_draft_validation.py`
and the shared memory/Mongo store contracts. `support/program_authoring.py` owns
one public HTTP lifecycle assertion for ASGI-memory and actual TCP/Mongo APIs:
save/reopen, invalid validation/publication, complete, execute, edit incomplete,
and retain/retry the old published revision. Tests use real thread/process work.
The production TypeScript program suite checks the validation client independently
of new screen work. The current goal prioritizes backend foundations/Engineering
before substantial unified UI work; use small client/browser probes along the way.

Saved-resource blocks send `ResourceSourceRef` markers, not browser configuration.
`SavedResourceResolver` captures the authorized transitive closure through the
application-owned source port; `ResourceAuthoringService` preserves native
visibility, caller overlays and private-field policy. It rechecks every captured
generation, then the normal protection path persists ordinary frozen resource
definitions. Changed shared snapshots require explicit `replace`; equivalent
normalized configurations reuse protected references. Configuration adoption does
not change existing placement. A source marker is neither historical retrieval
nor execution authority. Missing/hidden sources are 404, conflicts 409 and an
unconfigured library 503; no partial draft should be saved.

Construction traversal is iterative, preserving dependency order and bundle
digests. Source capture has 1,000-resource/depth-64 bounds. Check actual longest
paths, including cached/shared dependencies: selecting every dependency as a root
must not bypass depth admission. Reuse `support/construction_values.py` for deep
chains, `support/resource_snapshots.py` for application source ports and
`support/library_resources.py` for native seeds. The focused contracts live in
`application/test_resource_snapshots.py`, `domain/test_deep_bundles.py` and
`integration/mongo/test_resource_snapshots.py`. These are construction limits,
not aggregate execution budgets.

- `ChildContracts` declares statically required aliases and call contracts. Drafts can precede
  binding; publication checks missing aliases, revision ownership, immutable pins and environment
  imports. A configured name is not authorization to invoke an arbitrary program.
- Map's concurrency counts outstanding child calls, not physical workers. It
  bounds items before dispatch, returns input order and cancels outstanding owned
  calls on failure/cancellation. Draining its transient tasks does not claim
  physical environment cleanup; Run Engine owns that lifecycle.
- Repeat uses stable `iteration-N` child keys, recorded next state and a strict
  boolean predicate. `limit_reached` is an explicit unsatisfied result, even when
  the coordinator execution completed. Do not replace it with acceptance.
- Choose starts one declared child after validating its label. Unknown values
  cannot be echoed in diagnostics or select a fallback implicitly. Model decisions
  belong to invoked effects with recorded/validated outputs, not replay-time I/O.
- Wait calls native receive/deadline and returns `received` or `timed_out`.
  Business Human Review has separate authorization, persistence and reconciliation;
  generic event data is not human approval.
- Keep construction dependencies, value bindings, ordering and placement distinct.
  Sharing compute does not grant shared agent state. Published child imports
  remain authoritative; coordinator code cannot silently grant environments.

Application policy tests use runtime/child port doubles. Shared installed child
programs and definition helpers live in `tests/support/composition.py`; transport
and workers stay in infrastructure support. Run focused checks, then actual hosts:

```sh
.venv/bin/python -m pytest multi-agent/tests/application/test_composition.py multi-agent/tests/integration/run_engine/test_composition.py multi-agent/tests/architecture -q
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 .venv/bin/python -m pytest multi-agent/tests/adapters/test_program_repository.py multi-agent/tests/integration/mongo/test_program_repository.py multi-agent/tests/application/test_publication.py -q
UNIFAI_TEST_TEMPORAL_ENDPOINT=127.0.0.1:7234 .venv/bin/python -m pytest multi-agent/tests/integration/temporal/test_composition.py -q
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 .venv/bin/python -m pytest multi-agent/tests/integration/ui/test_editor_client.py -k programs --ui-clients -q
```

Require real graph → Map → graph → operation results on thread/process receivers,
input ordering and actual observed child IDs. The Temporal suite also checks
nested Map/Repeat, Wait worker restart and root/descendant native replay. It does
not establish Map worker-loss, remote cleanup or production-scale behavior.

For the actual App, build `ui/tests/build-placement-browser.mjs` using
[the existing browser workflow](../debug-session-ui/SKILL.md), then run:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 PYTHONPATH=multi-agent/tests:multi-agent/lib:multi-agent/adapters:multi-agent:multi-agent/plugins .venv/bin/python -m support.program_browser --assets /tmp/unifai-program-browser-assets --directory /tmp/unifai-program-browser-run
```

Use a fresh directory and the printed test login URL. The fixture installs the
shared deterministic backend programs and a published graph body. In Programs,
create from `greeting`, configure Prefix, save, reopen from the library, publish
and run `{"name":"standalone"}`. Create another program with `Build a workflow`,
select that saved program by name and choose its explicit published revision.

Add a program block; bind its `name` from state `user_prompt`, its whole output to
state `values`, program `user_prompt` from public input `name`, and public result
from state `values`. Publish/run. Publish a new greeting revision and require the
unchanged caller to retain its earlier pin/result. Inspect actual native results.
For Map, bind `body` to `browser-map-body` using the named picker and select revision
1; configure child `name` from `item` and run three items with explicit bounds.
Close the tab and stop the owned runner; confirm its unique database/session are
removed. MAS APIs are real; external identity/settings are synthetic test peers.

Invocation now fetches the selected published revision and opens the shared
`/executions/:id` workbench; `ProgramRun` was removed. The fixture also installs
`typed_program`: publish with Multiplier 2, save a draft with Multiplier 3 and a
changed input title, then run revision 1. Its old input form/result must remain
pinned. Exercise optional Tags/add/remove, invalid JSON view-switch refusal and
422 correction under the same execution ID. Uncertain responses freeze the original
intent/input. Local uncertain intents still do not survive browser reload.
The workbench supports actual child/root/parent links and cancellation; test a
`waiting` Program, cancel and reload its same URL. Do not infer verified task
acceptance from a completed engine phase or add a second result panel to the editor.

The same fixture seeds a saved operation with a transitive dependency and process
preference. Add it from the saved-element palette, bind `text` from state
`user_prompt`, map its whole result to `values`, bind program `user_prompt` from
public `name`, and return `values.text`. Save/reopen/publish/run and check the
dependency-derived result and retained process placement. Later source changes
must leave the old revision unchanged; adoption is explicit. Production TypeScript
client tests exercise source conflicts/replacement independently of the browser.

Backend configuration uses shared `components/schema/SchemaValue` fields. Local
references resolve against the root schema; complex/unresolved schemas retain JSON.
`ProgramConfiguration` adds resource-bundle and existing placement field adapters;
the generic form must not acquire API, construction or execution policy. For bundle
fields, `SavedResourcePicker` selects a source and `ResourceBundleField` explicitly
POSTs protected capture. Never copy redacted `cfg_dict` into an executable bundle.
Graph adoption remains in its own wrapper over the same catalog picker.

In the browser fixture, create `placed_operation`, choose process, capture Saved
text operation, publish and run `{"text":"browser configured placement"}`. Expect
the dependency-derived text and actual invocation ID. Reload and reopen; the captured
three-resource summary and profile must survive. The fixture delays capture by two
seconds: check editing/publishing/navigation lock while pending, and switch owner
views to confirm late completion cannot enter the new view. Aborting observation
does not roll back an already-committed server capture. Check the ordinary graph
palette still exposes its explicit shared-resource replacement choice. This is not
live coding, full Engineering/workbench acceptance or complete team navigation proof.

The browser fixture also provides `Routing example`: work blocks and the rejoin
are saved, with no route yet. Select `score`, expand Conditional routing, select
the saved threshold, add `true → yes` and `false → no`, then save/reload/publish/run.
Check the condition's process profile is separate from its source block placement;
the completed result visits score/yes/finish, never no. Remove/re-add a branch and
check exactly two configuration-adoption controls remain (work + condition).
The selected-block section owns the React key/lifetime; duplicate sibling keys
previously accumulated stale controls despite green transport contracts.
Removing the entry clears its selection and blocks save until replaced. Discard
must restore the saved graph without modifying its published revision.

`features/programs/graph-authoring.ts` owns pure graph-edit transformations. Edge
identity includes the condition label; removing one label must preserve another
label and any ordinary edge sharing its target. Removing a block never silently
rewires paths. Drop unreferenced pending source selections, but do not reconstruct
or prune dependency snapshots from browser configuration. The production UI
contracts check these edits against both plain data and actual branch execution.

Check invalid JSON blocks save and still triggers the unsaved-changes guard.
Mutable drafts must not be replaced by background focus refetches. Scope all
query keys by owner and authenticated human; abort requests on view replacement.
Use the existing `dark-inputs` parent class for this workspace: global theme CSS
otherwise forces dark input text even when a Tailwind text utility is supplied.
Verify visible contrast in the browser rather than relying on class names.

The Programs workspace supports library save/edit/reload and canonical program-call
canvas projections and saved-resource blocks. It is not the completed canonical
workflow editor: inline controls, typed visual ports, definition expansion and occurrence/
attempt inspection remain open. Advanced bindings/environments use JSON. Snapshot
polling must be authoritative; uncertain starts retain the same identity/input,
and unmounted or previous-workspace requests cannot update the new view.

The target evolves the existing blueprint builder into one program workspace;
incorporate this interim screen rather than preserving a separate workflow UI.
Expose controls inline and keep element resources/program revisions distinct.
Definition expansion inspects a pinned revision; editing publishes a new revision
for explicit caller adoption. Runtime drill-down follows actual occurrences and
observed code-program calls. Neither view may silently modify execution semantics
or invent an editable graph for arbitrary Python.
