# Program platform development

This describes the implemented foundation. The full migration is still in progress.
Start/resume with [current status](status.md) and [the active plan](plan.md), then
search headings and read the relevant guide sections. Detailed verification lives
in [focused evidence records](evidence/README.md); archives are opt-in reference.
Do not load this entire guide or historical records into routine working context.
The [target architecture](architecture/README.md) defines the agreed destination,
including typed operations, one composable Program model, UI contracts, plugin
boundaries, and engine-backed human review. Proposed capabilities there must not
be read as already implemented behavior here.

Fresh-platform decision (2026-11-01): old code, stored formats, workers, import
aliases, and dual APIs are not compatibility requirements. Convert useful behavior
to the target and remove superseded implementations, tests, dependencies, and
misleading guidance. Earlier old-worker retention and migration/drain requirements
are superseded. Safe cancellation and cleanup of current owned work still apply.

## Environment

From the repository root, use Python 3.14 or newer:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -e ../run-engine -e ./global_utils -e './multi-agent[dev]'
.venv/bin/python -m pytest multi-agent/tests -q
```

Use the committed Run Engine baseline
`60393440efd3876cd6c81e0b013e8bf6d9167659` (or a verified compatible successor).
It includes mapping arguments, accepted-child observation, OpenShell TLS/policy,
native execution-generation identity, ACTIVE graph joins and strict unknown-label routing. No companion patches
are required. Verify the source commit: package version `0.2.0` alone is insufficient.
The OpenShell extension requires SDK 0.0.104 or newer.

UnifAI defaults to active-path joins; a graph may explicitly select all-predecessor
joins. The compiler lowers its application-owned `join_policy` to the engine's
public policy. `UnknownLabelPolicy.ERROR` remains mandatory.
Earlier serialized plans without these policies retain ALL/IGNORE behavior.
Strict routing validates the entire result and fails with `UNKNOWN_CONDITION_LABEL`
before scheduling successors. Safe diagnostics do not remove return values from
native invocation histories; keep private values outside routing output. Older UnifAI prototype payloads and histories are outside the fresh-platform
contract. Rebuild matched coordinator/receiver images
before remote deployment; historical remote test results do not validate new SDK
source. See [integration status and recovery notes](../integrations/README.md).

## Canonical model and current consolidation

The [public model](architecture/README.md#canonical-public-model) is Element,
Resource, Program and Execution. Operation is an executable Element. Graph and
registered backend coordination are internal Program implementations. Both use
ProgramService, ExecutionService, the engine adapter and the shared execution view.

`mas.application.programs.state.ProgramState` owns generic data channels, including
structured JSON output. `graph_state.AgentProgramState` adds MAS channels only when
node/condition capabilities require them. Engine state binding uses corresponding
`ProgramGraphState` and `AgentProgramGraphState` adapters. Operation-only graphs do
not acquire chat/workspace/branch state. Bind operation requests directly from
`input` or prior `results`, rather than staging everything through `user_prompt`.

Sessions default to `interaction: "data"`, retain a portable `state` mapping and
allow arbitrary input/output bindings. `interaction: "conversation"` selects the
MAS conversation projection (`graph_state`, absent for ordinary data Sessions).
`SessionProjection` owns that mapping; the Session execution facade does not own
MAS channel validation. Existing blueprint-to-chat creation selects conversation
explicitly; all turns still invoke published Programs through ExecutionService.

The UI's single Programs library opens a canvas for a new visual composition or
schema configuration for an installed implementation. Import an existing blueprint
using **Import a workflow template**; it becomes a normal editable Program draft.
The superseded workflow authoring page/canvas and its private hooks are removed.
Read-only MAS flow views and template-backed chat/schedule integrations remain;
the complete live occurrence/attempt workspace remains a later UI milestone.

Receiver contracts are Program v6, graph state v4 and elements v4. Rebuild installed
receivers before remote gates; old prepared requests/workers are not migrated.

## Typed operations: first implemented slice

An operation is registered in the existing element catalog with category
`operations`, a configuration schema/factory, and Pydantic `input_schema` and
`result_schema` model classes. Its instance implements `BaseOperation.execute`.
`OperationInvoker` validates requests and portable results with safe contract
diagnostics. Implementations receive `OperationContext`, not graph state or an
engine SDK handle.

Generic `BaseElementSpec`, operation contracts, catalog and construction can be
imported/initialized without loading graph state. State-based nodes/conditions
specialize `GraphElementSpec` in `mas.application.programs.graph_elements`; channel
reads/writes and step/state protocols belong there, not to every element. Existing
node/condition adapters still use graph state intentionally. Abstract specification
bases are excluded from discovery/installation; concrete declarations are validated.

Portable invocation payloads have an explicit `key`. Typed operations carry no
graph step context and never receive automatic `set_context` graph injection.
Graph calls require explicit step context matching their key. The graph adapter
owns input/output mappings; backend Programs no longer fabricate graph context
for typed operations. Receiver contract is `unifai-elements-v4`, with prepared
format `runengine/request-v10`; earlier prototype snapshots are not migrated.

The existing `ElementBundleResolver` and `ElementBundleBuilder` construct its
transitive dependencies and release the owned scope. There is no separate
operation registry or scheduler. Native catalog details now expose operation input
and output JSON Schemas without constructing a provider client.

Graph programs use `OperationStep(kind="operation")` with an operation ResourceKey,
an input projection, named output bindings, execution selection, and retry policy. The engine
adapter projects graph values into the operation request and maps its result back
to declared channels. The operation itself never receives ProgramGraphState.
OperationStep identifies the explicit typed invocation contract. Remaining
node-state integrations are conversion/removal targets, not compatibility promises.

Custom programs use the same `ProgramRuntime.invoke_element(bundle, inputs,
key=..., execution=...)` port and receive the operation's structured JSON result.
Its optional application-owned `ExecutionSelection` selects an approved profile
or a declared named environment. Existing node-style invocation still
receives/returns application graph state and remains a conversion target.

Both graph and custom program definitions declare owned environments. Custom
programs declare `child_environment_imports` separately from behavioral config;
the compiler validates parent names and freezes these bindings into child
requests. Runtime code cannot widen them. Children borrow the engine's environment
grant; they do not acquire ownership or delete the parent's receiver. Concrete
runner settings stay in adapter payloads, outside the application runtime port.
The coordinator freezes installed approved profile choices at preparation time.
Tenant-specific policy admission remains unfinished.

Adapter payloads retain a category/type-to-installed-specification catalog.
Dispatch selects only the invoked bundle's exact transitive closure; it never
imports unrelated vendor plugins at a remote receiver. This is the same
selection path for graph and custom-program calls. A receiver still needs all
implementations actually used by its bundle installed.

Tests cover actual thread/process invocation, HTTP catalog/publication/execution,
separate Temporal workers, and native replay using a registered deterministic
operation with transitive dependencies. These checks do not establish a complete visual typed-port editor or the Human
Review program. The newer coding and managed-blob components are described below;
remote artifact transfer is a separate acceptance milestone. See the active migration queue.

## Core composition programs

The core registry installs `map@1`, `repeat@1`, `choose@1` and `wait@1` by default.
They are ordinary registered application programs; the program kinds remain graph
and application. Static ordering, dependencies and parallel graph regions keep
using `GraphDefinition` and Run Engine graph execution. There is no second
scheduler, custom replay store or integration-specific compiler branch.

`bootstrap.programs.installed_applications` composes the core registrations with
explicit extension modules into one `ApplicationRegistry`. Workers preload the
same core module before executing/replaying histories. Extensions still register
installed async functions and Pydantic configuration through
`ApplicationRegistration`. A configuration can implement the narrow
`ChildContracts.child_contracts()` interface, declaring child aliases, request
projections/scopes and consumed result mappings. Publication and compilation check
those contracts without knowing the particular Program implementation. Incomplete
bindings may still be saved as drafts.

| Program | Inputs/configuration | Result and control semantics |
| --- | --- | --- |
| `map@1` | Input `items` and optional `context`; declared child alias `body`, `concurrency` 1–128, `max_items` 1–10,000 and optional child input bindings | Starts at most the declared concurrency, preserves input order, returns each index/actual child execution ID/value. All items must succeed; a failure cancels outstanding owned calls and drains transient coordination tasks. Empty input returns no items. Oversized input fails before dispatch. |
| `repeat@1` | Input `state` and optional `context`; declared body, `max_iterations` 1–10,000, optional input bindings, result `state`/`until` bindings | Each iteration gets `{state, iteration, context}`. Recorded child results supply the next state and a strict boolean predicate. Returns `satisfied` or `limit_reached`, iteration count, last state/result and child execution ID. Reaching the bound never means accepted work. |
| `choose@1` | Declared label → child-alias map, selector binding and optional child input bindings | Starts exactly the selected declared child. Unknown/non-string selections fail before admission; diagnostics omit the returned value. Returns the selected branch, actual child execution ID and result. No implicit default/fan-out. |
| `wait@1` | Execution-scoped channel and finite timeout | Calls the runtime's native receive/deadline. Returns `received` with its JSON value or `timed_out`. This is generic event coordination; business approval uses the separately authorized/persisted Human Review program. |

Map's default body input is `{item, index, context}`; Repeat's is
`{state, iteration, context}`. An optional `inputs` projection builds named fields
or selects one complete `PathBinding`/`LiteralBinding` value, as graphs do. Omission passes the scope;
an explicit empty mapping passes `{}`. Each body is a pinned Program reference or
an owned inline graph/backend body, so it can contain operations, review,
verification or further composition.
Occurrence keys are stable `item-N` and `iteration-N` within their parent run.
Child identity, isolation, timers, replay and environments remain Run Engine's
responsibility. Parent/child environment imports still use the published bindings.

The coordinator performs no direct database, provider, HTTP, filesystem or wall-clock
I/O. Pure result projections can compute branches; model/provider decisions must
come from recorded invoked results. Native execution completion and these control
results do not replace trusted verification/ADLC acceptance.

### Owned inline Program bodies

`ProgramBody` contains implementation, input/output schemas and an optional
execution-profile default. `ProgramDefinition` adds the named library identity and
owner. Graph `ProgramCallStep.program` and backend `children[alias]` accept either
an immutable `ProgramRef` or a `ProgramBody`. A full independent definition cannot
silently become an inline body. There is no separate inline library, publication
or owner, and no synthetic Program IDs.

Save protects configurations/resources recursively using the normal construction
and secret services. Publication validates the whole owned tree and authorized
pinned dependency closure. Incomplete nested topology remains draft-only. An edit
anywhere in the owned body changes the enclosing revision digest; old publications
remain unchanged. A new revision may call an older revision of the same Program
because revision identity, rather than the unversioned Program ID, defines cycles.

Saved-resource selection commands optionally carry `body_path`, a sequence of
graph call UIDs/backend child aliases (empty means root). Source capture resolves
that owned graph scope using the existing authorized transitive snapshot resolver.
Paths never traverse published references. Invalid/non-graph scopes reject the
save. Resource keys are local to each graph's construction scope.

Compilation lowers both kinds of target through the same compiler, runtime ports
and native child execution path. An inline body inherits the enclosing resolved
profile unless it declares its own default. A published call retains its own
default. Neither target gains parent environments through containment: environment
imports remain explicit and borrowing preserves parent ownership.

Observed records expose enclosing `program`, immutable `content_digest` and stable
`body_path`, alongside actual execution/parent/root identities. Map items and
Repeat iterations share a body address but have different native executions. A
published call resets the source address to its own revision and empty path.
Source fields participate in persisted request identity; output/status changes do
not. Root submissions invoke published references, not arbitrary body paths.

Private prepared requests carry selected-scope contracts, mappings/configuration,
compiled child requests and source addresses instead of copying the entire source
revision into every child payload. Installed entrypoint contract is
`unifai-program-v6`; prepared format is `runengine/request-v10`. There is no old
prototype-payload migration. Rebuild matched images at the next remote milestone.

Local thread/process and production TypeScript→FastAPI→Mongo checks prove this
backend slice. The interim UI preserves/labels owned targets and can explicitly
replace them with published references; it does not yet author or expand inline
controls. Current-source Temporal/remote/recovery and visual builder proof remain
open. Schema-aware incomplete configuration is described below; deeper static
binding compatibility and the remaining platform target are still unfinished.

### Program discovery, saved library and authoring

**Target UI clarification (2026-11-03):** the standalone Programs editor/run panel
is an interim integration surface. Its useful capabilities must converge with the
existing blueprint builder, resource configuration and session views. The target is
one authoring workspace and a shared execution workbench with structured invocation,
optional conversation and authoritative live nested-execution visualization. It
preserves capabilities while allowing substantial visual/interaction improvements.
See [the agreed UI direction](architecture/README.md#unified-ui-and-live-execution-experience).
The descriptions below record current behavior, not completion of that target.

Program invocation now loads the selected immutable revision's input schema and uses
the shared schema fields, with JSON editing available. Draft edits do not change that
contract or the selected implementation configuration. Unparsed JSON blocks submission
and view switching. Uncertain starts preserve identity/input; a definite 422 permits
correction while retaining the execution ID, so existing admission conflict checks
still prevent a different request from replacing accepted work.

Accepted starts open `/executions/:id`, the shared owner-scoped execution workbench.
It shows observed phase/submission, actual immediate child links, root/parent/session
relationships, cancellation, inputs/results and owner-visible reviews. Observation
failure remains explicit alongside any last observed data. Inbox and execution views
reuse `ReviewDetail` and the same schema fields as configuration/invocation; the old
embedded runner and scalar-only review renderer were removed. Session stream hooks
retain the exact observed session/execution reference and link to this route.
Invocation now offers owner-filtered, issuer-described workflow permissions. Selection
is explicit; editing permission scopes resets the approval checkbox. Accepted starts
freeze the requested scopes with the invocation. The workbench shows that recorded
approval without credential material. Shared artifact inspection is described below.
Child lists are not yet transport-paginated; operation/attempt history, live flow,
complete Session browser proof and broader authoring/workbench convergence remain
unfinished. Local unconfirmed submission intents do not yet survive a browser reload.

Authenticated `GET /api/catalog/programs` returns installed key/version, display
metadata, configuration JSON Schema and optional input/result schema metadata.
It exposes neither executable functions nor backend configuration/credentials.
`ProgramService.implementations()` owns this view; the HTTP router is thin.

The actual App's **Programs** workspace at `/programs` lists saved programs in one
owner-scoped, paginated library. Users create, reopen, edit, save and publish through
the same contracts. An installed implementation supplies schema-driven primitive/
enum controls, local schema references and explicit JSON editors for complex values.
Program dependencies are selected by saved name and explicit published revision,
with interface inspection and paginated older revisions. No separate graph/code
library or manual revision-ID verification is required.

The same editor has a canonical graph projection: add saved operation/node blocks
or pinned program-call blocks, connect execution ordering, choose entry/exit, edit
data bindings and persist positions separately from executable definitions. Resource
selection is paginated and sends only source references; the server resolves and
protects the dependency closure. Selected blocks expose input/output contracts,
profile/environment selections, and explicit adoption of current saved configuration.
New blocks capture the resource's saved profile preference into caller-owned step
placement. Selected blocks can author conditional routes from saved condition
resources, map symbolic labels or explicit labels to destinations, and independently
select condition placement. Sources without a conditional route use ordinary
connections; routed sources use their branch targets. Publication rejects mixed
source modes, and the canvas guides users to labeled routes. Branch
labels sharing a destination retain separate identities when edited/deleted.
Advanced bindings/imports remain JSON rather than visual ports. Graph join policy
is configurable and persists with the published definition.

Block removal deletes incident ordering/conditional connections without inventing
replacement flow. Removing the entry or exit requires an explicit replacement
before saving. Removed roots no longer retain pending source selections; existing
frozen construction snapshots are preserved rather than pruning dependencies from
browser display data. Selection-scoped panels own their component lifetime so
switches and repeated edits cannot accumulate stale resource controls.

Invalid JSON remains editable and blocks form submission. Switching programs or
reloading requires explicit discard of unsaved edits. Mutable drafts load afresh on
explicit open/reload rather than replacing edits on window focus. Query caches and
request lifetimes are scoped by owner and authenticated human. Publication retries
retain the observed source version. Unknown run delivery retains the same execution
identity/input; authoritative snapshot polling observes completion and cancellation.
Submission acceptance is displayed separately from execution completion.

This is not the completed nested workflow editor. Inline Flow/Choose/Repeat/Map/Wait
authoring, visual typed connections, placement
preview, pinned-definition expansion and occurrence/attempt inspection remain open.
The older blueprint builder also remains; merge its useful capabilities and retire
the replaced path before claiming one final authoring experience. Current graphs
can call the published registered programs, which can call pinned graph bodies.

### Unfinished drafts and publication validation

The canonical `ProgramDefinition` can retain unfinished graph topology, unbound
declared Program dependencies and missing required configuration fields. It remains
authoring data, not an executable revision. Block/route identities stay unique;
supplied configuration shapes, field constraints and applicable field validators
are checked. Saving still authorizes ownership, checks the observed draft version,
and protects private resource and registered-Program configuration, including owned
bodies. No runtime model is fabricated from incomplete data.

`ConfigurationDraft` is an internal schema-bearing authoring tree. Complete values
use normal Pydantic validation; missing model fields retain their original field
metadata for protection. Nested object models, aliases/alias paths, discriminated
or unambiguous unions, lists, tuples and mappings with typed values retain declared secret
metadata. Supplied secrets use the existing owner-scoped store and opaque
references; repeat saves verify ownership and reuse those references. An ambiguous
nonempty variant is refused instead of guessing which fields are private. Empty
unselected variants can remain drafts. Unsupported incomplete shapes fail closed;
this is not an arbitrary-Python partial-validation mechanism. Semantic checks
that require complete model values still run before publication/execution.

Embedded bundles/resources follow the installed resource schemas as well. A
structurally valid bundle is not evidence that its embedded resources are complete.
Draft save protects supplied credentials and recomputes structural digests;
publication/compilation require canonical, complete construction through the normal
resolver. All authored graph resources are validated once as a snapshot, including
unused entries. Alias-normalized canonical field names survive factory revalidation.

`POST /api/programs/{id}/validation` takes `{expected_version}` and returns
`{version, valid, issues}` for that exact saved draft. Each issue has a stable
`code`, safe `message`, source `path` and `severity`. Current codes are
`INVALID_TOPOLOGY`, `INVALID_CONFIGURATION`, `INVALID_CONSTRUCTION`,
`INVALID_PROGRAM_REFERENCE` and `INVALID_BINDING`. Validation reads and checks; it does not persist
defaults, publish a revision, allocate compute or invoke providers. Stale source
versions return 409; ordinary owner authorization still applies before validation.

Publication uses the same application checks and independently rechecks them;
a prior successful validation response is not publication authority. The
`ProgramRevision` model also enforces executable structural completeness, so
repository writes, restored payloads and compiler reparsing cannot turn an
unfinished graph into executable work. Existing source-idempotent publication
and pinned older revisions remain valid after later incomplete draft edits.
Placement preview explicitly requires complete topology.

`valid` means the current publication rules passed. Execution still performs
profile/environment admission, concrete input validation and engine plan checks;
the report is not a claim of effective placement or successful execution.
Configuration must satisfy complete installed schemas and embedded construction
contracts before publication. The interim UI still has entry/exit and some form
requirements; production clients exercise the new backend contract, while full
unfinished-form/builder integration remains part of UI convergence.

### Binding admission and interface schemas

Publication and frozen-revision preparation share application-owned graph contract
checks. `ProgramContracts` composes installed catalog interfaces, authorized owned/
pinned child definitions and `BindingProjection`; it does not construct capabilities
or schedule work. `ProgramService` receives the installed element registry and owns
its stateless construction/contract validators. Pinned revisions are memoized only
within one validation request, retaining immutable identity and caller authorization.

Drafts may retain missing/invalid bindings. Readiness/publication reject missing
declared invocation inputs, closed destination fields that do not exist, invalid
fully literal model requests, literal values violating a known JSON destination
contract and paths impossible in declared input/result interfaces. Diagnostics use
`INVALID_BINDING` with the authored path and safe messages. Graph input mappings
are checked against the public input schema; operation and Program result mappings
use declared result interfaces. Owned and pinned calls follow the same rules.
Canonical names, simple aliases and alias-path roots remain accepted for installed
model inputs. Index segments are nonnegative integers; booleans and fractional/
negative indices are malformed authoring values.

These checks are conservative, not a proof that every runtime path/value exists.
Open interfaces, dynamic graph state, optional values and unsupported static schema
combinations retain concrete runtime checks. Scoped resources with nested `$id`
remain fully validated for concrete values; static projection intentionally stays
unknown instead of resolving them under the wrong scope. Recursive analysis is
bounded and avoids repeatedly expanding shared references. Whole literal model
requests use actual Pydantic validation; partial requests do not pretend to execute
model semantics with unknown values. Catalog result schemas describe serialized
canonical output, including computed output fields.

Interface documents use JSON Schema Draft 2020-12. References must resolve within
the bundled schema document, including bundled resource IDs/anchors; validation
and execution do not retrieve schema URLs. Reference-looking values inside enum/
default/example data remain data. Runtime Program validation uses a non-retrieving
registry and returns safe contract errors. This follows the library's
[registry-based reference handling](https://python-jsonschema.readthedocs.io/en/stable/referencing/).

The compiler rechecks restored revision contracts before native preparation.
Concrete malformed root inputs are rejected before creating an execution record;
bad values arriving dynamically still fail at the ordinary operation boundary.
Production client checks cover invalid draft readiness, refused publication,
correction, publication and actual execution through the same API.

Graph-local input/result checks and explicit graph join policies are described below.
Existing writable-channel contracts and writer policies are described below.
Remaining foundation work includes richer compatibility, cyclic/complex-flow
availability and lifecycle/retention limits. Current checks do not establish
those broader capabilities.

### Declared backend child-call contracts

Backend configuration models may implement application-owned `ChildContracts`.
Each alias maps to a `ChildContract`: optional input projection and local scope
schema, consumed output bindings and optional model for those projected results.
`inputs=None` passes the scope unchanged; an explicit empty mapping passes `{}`.
An absent scope schema means the implementation's normalized input interface,
falling back to published input when no installed input model is declared.
Declarations are installed application metadata, not another saved workflow format.

The shared `ProgramContracts` validator now handles graph calls and declared backend
calls. It checks required aliases, owned/pinned child interfaces, required model
fields and aliases, known scope/result paths and literal values. Pass-through checks
reject required fields that cannot exist and guaranteed fields that the destination
forbids. Unknown/open/optional structures retain concrete runtime validation; this is
not general JSON Schema subtyping or static analysis of arbitrary Python behavior.
Diagnostics identify the authored child alias with `INVALID_BINDING`. Readiness,
publication and restored-revision preparation use the same path.

Map and Repeat use named scope models both to construct runtime requests and to
describe admission contracts. Map's scope is `{item, index, context}`; Repeat's is
`{state, iteration, context}`. Repeat declares its consumed state/boolean mappings.
Choose checks every configured branch against its request projection or pass-through
input interface. These controls need no implementation-key branches in the validator.
Custom backend coordinators can use the same optional interface. Implementations
remain responsible for honoring their declarations and validating dynamic values;
Run Engine remains responsible for actual child scheduling and lifecycle.

Application, actual Local child execution and production TypeScript-client tests
cover refusal/correction, aliases, owned/pinned calls, consumed output paths and
normalized custom-coordinator input. Temporal/replay and current remote images
remain milestone checks; this evidence does not establish remote cleanup or full
graph-state compatibility.

### Installed backend Program invocation

`ApplicationRegistration` is the installed backend specification: versioned identity,
configuration model, async entrypoint, optional input/result models and catalog metadata.
It rejects malformed registrations. `ApplicationInvoker` owns configuration and
declared input/output model enforcement in the application layer; implementations
do not repeat this boundary plumbing. Use cohesive coordinator classes for related
orchestration behavior behind the registered entrypoint. Add a factory only when
construction needs actual dependency assembly, not to mirror element filenames.

Published input schemas validate submitted input. The installed input model then
validates and normalizes the JSON passed to the implementation, including aliases,
defaults and custom validators. Result models validate and normalize returned JSON;
published output schemas validate that normalized result. Catalog output schemas
use serialization mode and canonical names, including computed fields. Model and
schema failures produce safe contract diagnostics without invocation values.
Program boundaries reject non-JSON data and nonfinite numbers rather than silently
turning them into null. A result model does not change the entrypoint's JSON return
contract: implementations returning Pydantic objects must serialize them first.

Prepared adapter requests carry installed function/model references together in
`ApplicationCall`, not live registries or application instances. The inbound adapter
resolves them and delegates to the application invoker. Run Engine still owns
scheduling, recorded effects and replay. Configuration/input/result validators,
serializers and default factories must be pure and deterministic; effectful work
belongs behind runtime ports. This is a programming contract, not a sandbox for
arbitrary nondeterministic Python.

Execution records retain submitted input intent; implementations receive normalized
input. A separate observed normalized-input snapshot is still outstanding. RootModel
arrays work for standalone, backend and graph calls through the same invocation path.
Focused Local and production client evidence does not prove current-source Temporal
replay, remote dispatch or environment cleanup. Rebuild matched images and run those
gates at the planned execution milestone.

### Whole-value projections and graph data scopes

`Projection` is either named `Bindings` or a single `PathBinding`/`LiteralBinding`.
Operation/Program call inputs, graph return values and Map/Repeat/Choose child
inputs use it. Empty `{}` builds an empty object; `{"kind":"path","path":[]}`
selects the complete source value. A literal may be any portable finite JSON value,
including an array, scalar or null. Projection returns detached JSON containers;
missing paths and nonportable values have safe contract diagnostics.

Typed operations accept JSON through `ProgramRuntime.invoke_element` and normalize
through their installed Pydantic input/result models, including RootModel arrays
and scalars. They still use ordinary specifications, factories, builders and owned
construction. There is no array-specific runner or fake graph context.

Every graph invocation has two platform-owned data scopes:

- `input`: the original invocation JSON, initialized independently of legacy named
  state mappings. It may be an array, object, scalar or null.
- `results`: latest completed typed-operation/Program results keyed by authored step
  UID. Distinct parallel calls merge their separate keys. A repeated graph occurrence
  replaces that UID's current result; this is not attempt/occurrence history. Legacy
  state-based nodes do not copy their entire state into this result index.

For example, a root array can reach an operation with
`inputs={"kind":"path","path":["input"]}`. A graph returns its array result with
`outputs={"kind":"path","path":["results","work"]}`. A later call can build named
inputs by selecting fields from earlier results. An empty call output mapping writes
no legacy state channels but still retains the actual result in its indexed scope.

Graph initialization and per-call output mappings remain named channel updates.
Publication rejects writes to `input`/`results`; receiving adapters and native resume
updates preserve their platform ownership. State-based nodes cannot replace those
scopes through their normal return contract. These are cooperative dataflow rules,
not a security sandbox against arbitrary installed Python.

Whole-value literal requests/results use the same publication checks as named
mappings. Dynamic values still validate at invocation. Richer schema compatibility,
cyclic/complex-flow availability, arbitrary per-graph state schemas, indexed-result retention/
payload limits and authoritative occurrence inspection remain unfinished.
Current graph-state contract is `unifai-graph-state-v4`. Matched images and Temporal/
remote/replay evidence remain queued for the execution milestone.

### Graph-local interfaces and join policies

Application `GraphDataScope` resolves `input` and `results.<uid>` using each original
schema document. It does not copy child `$defs`/references into an unrelated graph
schema. Installed result interfaces and public output schemas both constrain result
paths. Unknown/nonindexed producers, unreachable producers, self-result reads and
reads without a producer-to-consumer ordering path reject readiness/publication.
Whole graph state and the result index are objects; the root invocation value is
selected through `input`. Named legacy state channels remain dynamically checked.

`InterfaceContract` now lives in `mas.application.programs.interfaces`; graph scope
navigation lives in `graph_data`, while `ProgramContracts` composes call/catalog/
publication checks. Current callers import those owners directly. The shared
projection validator rejects provably disjoint public JSON types, preserving
integer/number overlap and deferring uncertain unions, nullable values, scopes and
unsupported structure to concrete validation. Installed Pydantic coercion is not
incorrectly treated as strict JSON-schema assignability. This is conservative
overlap checking, not general schema subtyping.

`GraphDefinition.join_policy` uses an application-owned enum: `active` (default)
waits for the selected active paths; `all` requires static predecessors. It is
saved/published immutably and compiled through the public native graph policy.
Nested graph bodies can choose different policies without per-node engine options
or another scheduler. The current engine does not expose per-node race/first-result
joins through this contract. All-predecessor routing can leave a successor unexecuted
when a required predecessor was not selected; selecting a policy does not prove
exit reachability or accepted work.

Reachability follows the engine's routing precedence: a source's conditional route
selects its successors instead of also following that source's ordinary edges.
Use an explicit fork before conditional work for an always-active parallel branch.
Canonical graphs may save mixed source modes as drafts, but cannot publish them.
The canvas blocks adding ordinary edges to a routed source and requires removing
ordinary outgoing connections before adding routing. It does not silently delete
or reinterpret edges. Blueprint import recognizes `after` links to declared branch
targets as branch metadata; unmapped outgoing conditional dependencies reject
conversion. Valid branch-only Blueprints and redundant branch metadata use the
same canonical graph representation.

Application `GraphFlow` owns bounded static reachability/activation analysis. For
acyclic active-path graphs, result reads must have an ordering path and the consumer
must not activate on a route that skips its producer. A consumer inside the producer's
branch is valid; reading that producer after a conditional convergence is refused
when another branch can activate the consumer alone. Ordinary parallel predecessors
remain valid. Analysis uses declared routing, including empty/multiple selections;
it does not evaluate a condition or inspect plugin-specific configuration to choose
an outcome. Scheduling, selected decisions and recorded effects remain native.

Activation expressions retain at most 256 minimal routing terms per node; a flow
caches at most 64 reachability sets. Cyclic graphs and expressions exceeding the
activation bound defer the unresolved guarantee to runtime. Structural/source/schema
checks still apply. Under all-predecessor joins an ancestor must finish before a
consumer can run, but an unselected predecessor can prevent the exit from running.
Native tests confirm missing cyclic values and unreachable required results fail
as contract errors rather than becoming accepted work. General cyclic first-
iteration availability and arbitrary per-graph mutable state schemas remain open.

Every condition label requires a declared destination. `END` is an ordinary label,
including the direct router's no-recipient outcome; there is no generic terminal
exception. Explicit empty selections retain their native no-successor semantics.

Focused application/native/client checks cover refusal/correction, scoped references,
type overlap, repeated use of the same published Program and both native join-policy
plans. They do not establish Temporal/replay or current-image remote acceptance.

### Writable channels and writer policies

Application `ProgramState` owns graph invocation/result scopes, existing writable
channel schemas, portable updates and safe validation errors. It extends the shared
UnifAI `GraphState`; the thin Run Engine state adapter combines it with native
state/reducer integration. Generic operations continue to receive typed JSON and
operation context, never graph state.

Publication checks graph initialization and call output mappings against writable
channel schemas. Installed node/condition specifications must refer to known
channels. Conditions return routing outcomes and cannot declare state writes.
`input` and `results` remain platform-owned. Receiving adapters validate actual
returned node changes against declared writes and validate concrete channel values.
Unknown, read-only, undeclared and ill-typed updates fail with safe contract errors
without echoing supplied values.

`GraphWritePolicy.ORDERED` is the default: overlapping declared channel writers
require a proven ordering in the acyclic topology. `REDUCE` explicitly selects
existing declared channel reducers, including stable overwrite for some channels;
it does not guarantee commutativity or make arbitrary concurrent mutations safe.
The policy is graph-wide, independently configurable in nested graphs. Cyclic
ordering is not statically proven. Blueprint conversion explicitly preserves its
existing reducer behavior. Ordinary typed dataflow should use indexed results
instead of competing writes to shared channels.

This is validation of existing channels, not a new state DSL or scheduler.
Per-channel overrides, arbitrary graph-local variable schemas, authoritative
occurrence history and current-image remote/replay validation remain open.

### Saved resource selection and frozen construction

Native resource reads/listing include `source: {key, revision}` when the element's
implementation is installed. This is an owner-scoped optimistic revision marker,
including configuration/implementation version, built-in publication metadata and
caller overlay generation. It does not retrieve historical library documents.
Published program revisions provide immutable execution snapshots.

`SaveProgramDraft.resource_selections` accepts entries shaped as
`{source: {key: {category, rid}, revision}, adoption: "reject" | "replace"}`.
The default adoption policy is `reject`. `SavedResourceResolver` depends on the
application-owned `ResourceSnapshotSource` port; `ResourceAuthoringService` supplies
authorized native async reads and existing visibility/overlay/encryption policy.
Typed references discover the transitive closure. The shared bundle resolver checks
cycles, construction contracts and implementation versions. A second authorized
read checks source revisions before protection/persistence. Selection is bounded
to 1,000 resources and depth 64; these are construction bounds, not run-tree budgets.

Save protects private fields through `ConfigurationSecrets`, then stores ordinary
`ResourceDefinition` snapshots in the program. Source markers are save commands,
not execution payloads. Browser display/redacted configuration is never copied into
those snapshots. Workers continue to use existing bundles, factories, category
builders and the ordinary operation/node invocation pipeline.

Edits without new selections keep frozen configuration. Selecting changed content
that collides with an existing resource/dependency returns 409 unless the caller
explicitly chooses `replace`; replacement affects all uses of that key in the draft.
Equivalent normalized content reuses existing protected references rather than
creating duplicate credential records. Older published revisions stay unchanged.
Root source changes invalidate a pending selection; dependency revisions are captured
at save and checked for changes during collection. Missing/hidden dependencies are
404, an unavailable library is 503, and neither case persists a partial draft.

Placement remains separate: source selection resolves construction data; clients
author step execution selections independently. The UI captures saved defaults for
new blocks and preserves explicit overrides. Configuration adoption does not silently
rewrite existing step placement. Binding saved resources into registered-program
configuration fields remains open; the resolver itself is independent of graphs.

Target clarification: evolve the existing blueprint builder into one program
workspace, incorporating the useful behavior from this interim screen. Element
resources and published programs remain distinct reusable library types. Present
Map/Repeat/Choose/Wait as controls inside the builder, independently of their
registered-program lowering. Definition expansion shows a pinned program's graph
and interfaces; execution drill-down shows its actual child runs, invocations,
items, iterations and attempts. Editing a reusable definition creates a new draft/
revision, with explicit caller adoption. Registered Python programs expose public
contracts and observed calls without requiring an editable graph representation.
See [the target authoring model](architecture/README.md#unified-program-builder-and-reusable-libraries).

## Optional Git source operations

The platform does not require Git or artifact publication. Ordinary operation
schemas define their own inputs/results, including plain data, immutable source
references, reports or other integration-specific values. `GitRevision` is a small
ADLC value (`repository`, full immutable `commit`), separate from `BlobArtifactRef`.
Generic program/runtime/compiler contracts do not import it.

Enable the installed optional plugin on the API/coordinator using
`UNIFAI_ELEMENT_MODULES='["mas_plugins.git.specification"]'`. Install the same
package and Git CLI on receivers that execute these operations. Operator settings
bind logical repository IDs to transport locations and explicitly admitted owners:

```sh
export UNIFAI_GIT_REPOSITORIES='{"product":{"location":"/srv/repositories/product","owners":[{"type":"user","id":"developer"}]}}'
export UNIFAI_WORKSPACE_ROOT=/srv/unifai-workspaces
export UNIFAI_GIT_TIMEOUT_SECONDS=120
```

Locations currently support an absolute local repository path or credential-free
HTTPS. Local paths must exist on the selected receiver. This slice does not
implement private Git credentials, SSH, submodules, LFS filters or remote image
installation. Repository bindings and locations stay outside authored definitions
and portable execution results. Owner admission distinguishes user/team identities
and fails closed for absent bindings or owners; it is not a general tenant policy
or protection against hostile code sharing the receiver's OS identity.

Use these normal resource/specification contracts:

| Resource type | Configuration | Input | Result |
| --- | --- | --- | --- |
| `providers/git_repository` | Logical `repository` ID | — | Constructed source capability |
| `operations/resolve_git_revision` | `source: ProviderRef` | `reference` (default `HEAD`) | `GitRevision` |
| `operations/checkout_git_revision` | `source: ProviderRef`, workspace name/mode | `revision: GitRevision` | `GitWorkspace` (initial revision and relative workspace) |

Resolution accepts `HEAD`, a full `refs/heads/...` or `refs/tags/...` name, or a
complete lowercase object ID. It fetches and peels annotated tags to a commit,
recording a 40-character SHA-1 or 64-character SHA-256 identity. SHA-256 repositories
set `object_format: "sha256"` in the operator binding. Moving branches must be
resolved before handing candidates to later stages. Detached checkout fetches that
exact commit; it never substitutes a newer branch head. Both operations use the
existing dependency builder and operation invoker from graph or code programs.

Checkouts stage privately on the workspace filesystem and publish through pinned,
execution-scoped parent handles. An existing destination is a conflict, including
an existing pristine checkout: a retry does not erase uncommitted work. Uncertain
publication reconciliation is still required before claiming idempotent checkout.
The returned revision describes the initial checkout, not its contents after an
agent edits it. Changes must become a new immutable candidate before verification.

The adapter uses owned, bounded, native async Git subprocesses, disables inherited
Git configuration/templates/hooks/credential helpers, denies unrelated transport
protocols and submodule recursion, discards raw diagnostics, and cleans staging on
ordinary failure, timeout and cancellation. Hard-crash staging collection and
repository size quotas remain acceptance work. A commit reference is durable only
while the repository retains and serves the object; managed retention or protected
publication refs must precede a durability claim. No merge/push/deploy operation or
trusted verification receipt is implied by a successful checkout.

## Verification plans and trusted evidence admission

Enable `UNIFAI_VERIFICATION_ENABLED=true` with `UNIFAI_STORAGE=mongo`. Verification
uses the existing application database and native async Mongo connection; memory
storage is rejected for this feature. `program_verifications` stores bounded
whole-plan records with majority-acknowledged writes and revision-checked updates.
There is no additional database, scheduler or operation registry.

`UNIFAI_VERIFICATION_POLICIES` maps versioned policy IDs to admitted owners, a
`subject_kind`, required check IDs/allowed verifier IDs, and a deadline (60 seconds
to 30 days). For example, the JSON value of a single policy can be:

```json
{
  "owners": [{"type": "user", "id": "developer"}],
  "subject_kind": "build-image@1",
  "requirements": [{"check": "tests@1", "verifiers": ["ci"]}],
  "timeout_seconds": 3600
}
```

`UNIFAI_VERIFICATION_AUTHORITIES` maps verifier IDs to `credential_sha256` (the
lowercase SHA-256 digest of a separately provisioned high-entropy bearer credential)
and explicit owner identities. The verifier retains the credential; the API
configuration stores its digest. Distinct verifier identities require distinct
credential hashes. Policies must refer to configured verifiers. These are evidence
issuers, with no general user-session or workflow authority. Keep the raw verifier
credential in its trusted CI integration, outside agent/workflow configuration and
history; use HTTPS for nonlocal evidence submission. Native tests use loopback HTTP.

| API | Authority | Behavior |
| --- | --- | --- |
| `POST /api/verifications` | Native session or scoped workflow capability | Admit a stable `key`, policy ID and exact subject; freeze required checks/deadline |
| `GET /api/verifications/{plan_id}` | Owning native session or scoped read capability | Authoritative state, receipts, revision and derived outcome |
| `POST /api/verifications/{plan_id}/cancel` | Owning native session or scoped cancel capability | Cancel an incomplete plan and fence new evidence |
| `POST /api/verification-evidence` | Verifier bearer plus `X-Verification-Authority` | Admit one immutable receipt for an allowed check and owner |

The opt-in `VerificationSubject(kind, identity)` belongs to evidence correlation;
ordinary operation outputs retain their own schemas. It does not impose Git,
managed artifacts or a universal reference registry. Its bounded JSON identity
has a canonical fingerprint including the versioned kind. Object-key ordering
does not change identity; booleans, integers and floats remain distinct. A checker
must validate and interpret its own candidate schema. This mechanism identifies
the subject attested to; it does not itself prove the referenced resource exists.

A plan ID is stable for an owner/type/root/key. Repeating the same intent recovers its
persisted state. Changing its candidate or policy is a conflict. Required checks
are frozen at admission, so retries and inspection do not silently adopt a changed
operator policy. Each receipt includes its check, authenticated verifier, exact
subject fingerprint, external check-run ID, verdict and server admission time.
The request repeats the subject; mismatches are rejected before receipt lookup.

Acceptance requires every frozen check to have a passed receipt. Failed checks
produce `rejected`; check infrastructure errors produce `error`. Incomplete plans
without those failures become `expired` at their deadline. Cancellation yields
`cancelled`. The deadline limits admission of new evidence; an already accepted
plan remains accepted afterward. Quality freshness/revocation policies are separate
future work. Identical receipt retries remain acknowledged after expiry/cancellation;
conflicting verdicts, different run IDs and replacement issuers cannot overwrite a
receipt. Rerunning a failed check uses a new verification-plan intent.

The application owns admission, matching, cancellation and acceptance. Mongo owns
atomic persistence; HTTP owns credentials/transport. There are no verification
branches in the compiler/runtime or changes to Run Engine. Native restart tests
use separate API processes, actual signed cookies/Redis, actual Mongo, and an
independent executable source-content check against an exact Git checkout. Both
passing/failing results persist, while ordinary sessions cannot attest and verifier
credentials cannot become user sessions. This proves the evidence-ingress contract,
not a production CI executor or complete implementation/testing/review workflow.

Workflow capabilities and reusable wait Programs are described below. GitHub
dispatch/reconciliation and operator-pinned verifier Programs provide check runners.
Required report provenance and basic owner-authorized UI inspection are implemented;
complete software verification, remote and broader UI acceptance remain open.
The control plane/database
and admitted verifier are trusted. This credential boundary does not establish
isolation from malicious code sharing their OS identity or database authority.

### Operator-pinned verifier Programs

`UNIFAI_PROGRAM_CHECKS` registers a check runner backed by an ordinary published
Program. The private operator binding contains `policy`, `program_owner`, immutable
`program` reference, exact `content_digest` and `max_result_bytes` (default 65,536).
Program and GitHub runner names cannot collide. Internal verifier identities cannot
also accept external evidence credentials. Every policy/check/subject-kind binding
is validated at deployment; Program checks require durable artifact storage.

`ProgramCheckRunner` depends on narrow application execution/revision ports. It
uses the existing ProgramService/ExecutionService implementations, never an engine
SDK, separate scheduler or sandbox manager. The selected verifier's own definition
controls placement, dependencies and composition. A graph or backend Program can
implement the same check contract. Installation of a Program alone grants no
attestation authority: the operator must pin that exact revision and digest.

The verifier receives `CheckProgramInput` (`intent_id`, `plan_id`, `check`, `subject`,
optional `artifact`). Metadata-only requests omit the optional field.
It returns `CheckProgramResult` (`subject_fingerprint`, `verdict`, optional JSON
`details`). The runner validates the execution owner, reference, digest, actual
input and exact candidate fingerprint before admitting a verdict. Operational
completion alone is insufficient. Failed/cancelled verifier executions report an
error with safe phase metadata, not raw failure diagnostics. Malformed, oversized,
unknown or foreign observations cannot attest. Reports are bounded JSON, hashed and
collected through the existing immutable report/artifact pipeline.

The execution ID is stable for the admitted check intent. Lost submission
acknowledgements are reconciled by that ID; a missing execution never authorizes
another submission. Reports reconstruct from persisted execution results rather
than process-local provider state. Changing the operator binding cannot reinterpret
an older admitted check. API reconstruction after completed thread/process checks
has [native proof](evidence/2026-11-05-program-checks.md).

Verifier jobs are independent executions under the configured verifier owner,
similar to external CI jobs; they do not counterfeit Engineering child ancestry or
inherit its workflow credentials. Candidate owners receive admitted evidence/reports,
not access to another owner's full execution. Input provenance is not authority to
read candidate content: checker-specific adapters need separately scoped access
or the bounded input transport described below.

This bridge does not itself execute untrusted code or certify a verifier's logic.
Operators must select trusted, bounded checker Programs and appropriate isolation,
input transfer and private bindings. Cross-root capacity accounting, in-flight Temporal recovery and current-image Kubernetes/
OpenShell acceptance remain required. Native cases cover JSON values and controlled
Python source; they are not live-agent or isolated software-verification acceptance.

### Verifier-job retirement and cancellation

Owned check registrations explicitly provide a `CheckJobControl` port. Their
persisted `job_state` progresses `active` → `retiring` → `closed`; unmanaged/borrowed
providers have null state and are excluded from this controller. This is job
ownership metadata, separate from the last provider observation and check verdict.

`CheckJobMaintenance` joins the existing application reconciliation loop. It pages
indexed current-state records, limits each pass to five seconds, advances past
unavailable items and retries across reconstruction. Plan cancellation/expiry,
recorded evidence, or an authoritatively closed owning root initiate retirement.
A pending plan belonging to a closed root is cancelled through VerificationService.
Unknown root authority is not permission to cancel. New indexes/projections are
validated against stored data; old prototype rows need replacement/migration rather
than an implicit compatibility reader.

Retirement intent commits before a provider cancellation call. An unclaimed ready
intent can close atomically and fence dispatch. In-flight/uncertain jobs stay
retiring until the exact admitted verifier execution is observed terminal. Missing
jobs, changed bindings and unavailable observations remain pending; cancellation
acknowledgement alone does not close them. Late acknowledgements cannot restart
retired work or attest new evidence. Exact receipts committed before a lost check
acknowledgement are recovered, including while other plan requirements are pending.
Existing receipts remain immutable.

Program checks use normal ExecutionService cancellation under their configured
verifier owner. They never kill a different owner's process from the API or adopt
another job. The current SDK's thread/process pools drain an already running
invocation: cancellation does not promptly interrupt its separate event loop.
Finite operation bounds therefore remain necessary. Native tests prove eventual
terminal cancellation, actual child reaping and directory collection after bounded
draining; they do not prove immediate preemption. The [engine capability request](../integrations/run-engine-invocation-cancellation-request.md)
records the inspected behavior and requested cooperative cancellation contract.

See [the lifecycle checkpoint](evidence/2026-11-05-check-lifecycle.md) for exact scope.
The [Kubernetes checkpoint](evidence/2026-11-05-checker-placement.md) adds current-image
bounded remote cleanup. Full remote/recovery coverage, unavailable binding restoration
and cross-root capacity/fairness remain final-acceptance work.

### Python function checks and bounded candidate transport

For a small blob candidate, an operator Program-check binding can set
`input_artifact_max_bytes` (1–1,048,576). This is permitted only for a canonical
`blob-artifact@1` subject. The runner validates its policy/owner, reads through the
existing ArtifactService as the candidate owner, bounds the stream and supplies an
`InlineArtifact`: the exact reference plus base64 content verified by length and
SHA-256. Corrupt, oversized, noncanonical or unavailable input never starts a checker.
This optional transport puts bounded source data in the verifier execution's stored
inputs/history. It is not suitable for large repositories; ordinary reference-based
check Programs remain available. It grants the receiver no artifact credential.

Install `mas_plugins.testing.specification` in the normal element catalog to expose
`operations/python_function_evaluate`. Its resource specifies a function name and
a 0.1–300-second timeout (default 10). Normal specs/factories/builders construct it.
Its input is the exact inline artifact plus 1–32 argument sets. It returns bounded
actual values or a typed evaluation failure, never a verification verdict.

Install `mas_plugins.testing.program` in the application registry for the backend
`python_function_check@1` Program. Configuration contains the captured evaluator
bundle, expected cases and an explicit execution selection. The coordinator keeps
expected answers, validates the exact candidate fingerprint and invokes only that
evaluator bundle with source/arguments through `ProgramRuntime.invoke_element`.
Check-plan metadata, verification capabilities and expected answers are not evaluator inputs.
Comparison stays outside the candidate receiver when placed on an isolated profile.
The former combined check operation was removed without compatibility aliases.
The full controlled Engineering native/browser journey also uses this production
checker through `program@1`, with a separately owned pinned verifier. Candidate
owners inspect admitted reports, not the verifier's private execution. The old
transient Python-check API peer was removed; see the
[integration checkpoint](evidence/2026-11-06-engineering-program-checks.md).

Case data and evaluator results are bounded to 64 KiB. The comparator checks result
schema, count and JSON types; `true` cannot satisfy expected `1`. A candidate-returned
verdict or extra fields cannot attest success. Exceptions, malformed/excessive output
and deadlines become explicit errors without raw subprocess diagnostics. Runtime
cancellation and infrastructure failures retain their normal execution semantics.
This uses the public Program model, with no compiler branch or sandbox manager.

The child gets a minimal environment, its own process group and a temporary working
directory, with no artifact token. stdout and stderr are independently bounded to
64 KiB. Acquisition, cancellation, process-group termination/reaping and directory
collection are owned by the adapter and drained before cancellation propagates.
Python `-I -S` isolates imports/configuration, not operating-system access.
The evaluator retains only receiver-local proxy/certificate transport settings in
addition to its minimal PATH. OpenShell's allowed traffic needs those injected
settings; stripping them makes direct child networking unreachable. Coding and
evaluation adapters share the outer `mas_plugins.subprocesses.network_environment`
helper. Provider keys, workflow settings and `RUNENGINE_PARAMS` are excluded from
the evaluator child environment. Policy still belongs to the execution profile.

Factory execution defaults to disabled. Only receiver/operator settings may enable
`UNIFAI_PYTHON_CHECK_EXECUTION_ENABLED=true`; optional
`UNIFAI_PYTHON_CHECK_DIRECTORY` must be absolute. Authored resource configuration
cannot enable it or select a shell command. Enable only on an appropriately isolated
profile for live/untrusted source. The flag declares operator authorization; it does
not prove physical isolation. A same-UID subprocess on a trusted host is not a
hostile-code sandbox. Installed test cases are also only the verification specified,
not a proof of arbitrary software correctness or protection against malicious code.

The [Python-check checkpoint](evidence/2026-11-05-python-checks.md) uses deliberately
controlled source in native thread/process tests. It proves independent comparison,
input/report ownership, bounded subprocess behavior and completed-state API restart.
The [Kubernetes checkpoint](evidence/2026-11-05-checker-placement.md) additionally
proves current-image passing/failing checks, bounded cancellation, retained placement
and physical Job/pod cleanup. Receivers use a token-free service account; descriptive
namespace context no longer depends on mounting a service-account token. The SDK
adapter observes actual namespace/image and host/secret mount settings independently.
That checkpoint predates the separated comparator described above. Minimal child
environment alone cannot prevent same-UID access to receiver parent process data;
the evaluation receiver must therefore contain no expected answers or verification
authority. Actual profile isolation and network restrictions remain required.
The [separated-checker checkpoint](evidence/2026-11-05-checker-boundary.md) proves
the current protocol through a real receiver-parent environment recovery attempt,
with candidate evaluation disabled on the trusted API host.
Prompt interruption and full live Engineering/browser acceptance remain open.
The later [normal OpenShell checkpoint](evidence/2026-11-06-normal-openshell.md)
proves real candidate allow/deny/offline behavior and a separate live two-Codex smoke.
Full live Engineering/verifier/browser integration remains unfinished. Strict
Landlock filesystem enforcement is an optional profile/test guarantee, not required
for normal OpenShell execution.

### Workflow capabilities and reusable waiting

Native sessions manage `/api/verification-access`: POST issues a credential once,
GET lists public metadata with pagination, and DELETE `/{grant_id}` revokes it.
GET `/self` requires the workflow bearer and returns only its grant metadata.
Issuance records the owner and acting human separately, including team-owned grants.
Mongo persists a credential hash, expiry, revocation and explicit scope: one root
execution ID, permitted policy IDs and `create`/`read`/`cancel`/`run_check` actions. There is no
evidence-submission action. Invalid bearer credentials never fall back to a cookie.

Review and verification workflow grants additionally require execution-bound
authority, described below. A valid hash, future expiry and `revoked=false` do
not by themselves establish that a workflow credential is currently usable.

`VerificationActor` carries this authority into the application service. Creating
a plan derives its root from the grant, and read/cancel checks enforce the same
root, policy, action and owner. Owning a different plan under the same user is not
enough to access it with a scoped grant. Native owners retain their authorized
inspection/control. A shared opaque-credential helper supplies nonce/hash mechanics
for artifact and verification capabilities; their scopes and policies stay separate.

Install `mas_plugins.verification.specification` through `UNIFAI_ELEMENT_MODULES`
and `mas.application.verification.program` through `UNIFAI_APPLICATION_MODULES`
(append them to other required modules). Receivers need the same installed code.
The plugin registers these normal resources through existing specifications,
factories, provider references and the shared operation invoker:

| Type | Input | Result |
| --- | --- | --- |
| `providers/verification_service` | Protected credential reference or operator binding | Root-scoped service connection |
| `operations/request_verification` | `subject`, `policy` | `VerificationView` |
| `operations/inspect_verification` | `plan_id` | `VerificationView` |
| `operations/cancel_verification` | `plan_id` | `VerificationView` |
| `operations/start_verification_check` | `plan_id`, `runner` | `CheckRun` |
| `operations/refresh_verification_check` | `intent_id` | `CheckRun` |

The request operation derives an intent key from execution/call identity. Retries
recover the same plan; a repair needs a new logical occurrence. The HTTP adapter
validates owner/root/policy and returned plan/candidate identity, uses bounded
responses/deadlines, closes each owned client, and preserves safe retryable
infrastructure failures. Protected preparation redacts messages/codes while keeping
failure category and retryability. Artifact storage failures now use that same
application-owned failure contract instead of losing their transport classification.

Configure `UNIFAI_VERIFICATION_ENDPOINT` as an HTTPS origin. For operator-bound
credentials, set an absolute `UNIFAI_VERIFICATION_ACCESS_DIRECTORY`. Provision a
private regular file named by `verification_credential_key(owner, root_execution_id)`
with the capability for that owner/root. This permits concurrent roots using the
same published resource without replacing one global token. Symlink/nonregular or
nonprivate credential files are rejected. The alternative `access_token: SecretStr`
uses the existing protected configuration/secret-reference path. Credentials are
not program inputs, operation results or prepared engine payloads. Tests explicitly
enable loopback HTTP with `UNIFAI_VERIFICATION_ALLOW_INSECURE=true`.

The registered `await_verification@1` code program takes `plan_id`. Its configuration
contains an inspection operation bundle, placement selection, polling interval and
positive poll bound. Graph or code programs can call it as an ordinary child. Each
inspection is a short operation; between inspections it calls `ProgramRuntime.sleep`,
which Run Engine implements with its native timer. Control follows recorded
inspection results on replay. There is no additional scheduler or waiting invocation
worker. Waiting ends with an explicit result: `reason=resolved` plus the business
outcome, or `reason=poll_limit` plus the still-pending verification. Neither program
completion nor poll exhaustion means accepted work. A later waiter can use the same
plan ID. Cancelling a waiter does not cancel the borrowed plan; an authorized caller
uses the explicit cancel operation when appropriate.

### Trusted external checks and uncertain dispatch

`CheckRunService` coordinates a verification plan with an operator-admitted check
runner. The domain owns dispatch status and observations; the application owns
authorization, one intent per plan/check, immutable configuration admission, and
evidence submission. `MongoCheckRunRepository` reuses the native application
database. `mas_plugins.ci.github` implements the external provider contract.
Run Engine still owns all scheduling and durable waiting.

The workflow APIs are:

- `POST /api/verification-checks` with `plan_id` and an admitted `runner` ID.
- `GET /api/verification-checks/{intent_id}` reads the authorized persisted view
  without contacting the provider; scoped readers need only plan-read authority.
- `POST /api/verification-checks/{intent_id}/refresh` to reconcile provider state
  and commit trusted evidence after completion.

Native owners or a root/policy-bound workflow grant need authority to inspect the
plan; workflow grants additionally require `run_check` for both operations.
Creating or reading plans alone does not authorize spending CI resources. The
operator binding further restricts owner, verification policy, check and subject
kind. The public operation does not accept a verdict, provider token, executable
command, workflow URL or arbitrary dispatch parameters.

Set `UNIFAI_VERIFICATION_ENABLED=true` and supply `UNIFAI_GITHUB_CHECKS` privately on
the **API server only**. Its map keys are versioned runner IDs. Each binding has:

| Field | Meaning |
| --- | --- |
| `policy.owners` | Explicit permitted owner identities |
| `policy.policies` | Permitted verification-policy IDs |
| `policy.check` | The one check this runner can satisfy |
| `policy.verifier` | Its internal trusted verifier identity |
| `policy.subject_kind` | `git-revision@1` for this adapter |
| `repository` | GitHub `owner/repository` hosting the trusted workflow |
| `source_repository` | Logical repository identity accepted from `GitRevision` |
| `workflow_id` | Numeric workflow ID |
| `workflow_ref` | Operator-controlled branch/tag used for dispatch |
| `workflow_commit` | Exact expected workflow run `head_sha` |
| `token` | Operator-only GitHub token, represented as `SecretStr` |
| `timeout_seconds` | Request and whole-reconciliation deadline, default 20 seconds |
| `reconciliation_pages` | Bounded search, default/max ten pages of 100 runs |
| `report_names` | Exact required GitHub artifact names, default empty, maximum 16 |
| `report_max_bytes` | Per-report archive bound, default 16 MiB, maximum 64 MiB |
| `archive_hosts` | Explicit HTTPS download-host names or `*.suffix` patterns |

The verifier must appear in the corresponding verification policy. It must not
also appear in `UNIFAI_VERIFICATION_AUTHORITIES`: the internally admitted runner,
rather than an external evidence bearer, owns this authority. Settings reject
conflicting roles, missing policies and incompatible checks. Credential rotation
preserves the configuration digest; changing the admitted workflow/policy binding
requires restoring that binding to reconcile an existing run.

Configure the trusted workflow to accept four string inputs: `unifai_intent`,
`unifai_plan`, `unifai_check`, and `candidate_commit`. Its run name must be:

```yaml
run-name: unifai-${{ inputs.unifai_intent }}-${{ inputs.candidate_commit }}
```

The workflow must materialize the exact full candidate commit from its fixed,
operator-approved source repository and run its admitted checks. It must report
success only if those checks actually pass. A matching run name binds the candidate
input to the observed run; the platform still trusts the operator-controlled
workflow's implementation. A successful unrelated or agent-controlled workflow is
not evidence. Protect the workflow/ref and its execution authority accordingly.

The adapter uses GitHub's [workflow dispatch endpoint](https://docs.github.com/en/rest/actions/workflows?apiVersion=2022-11-28)
with `return_run_details=true` under API version `2022-11-28`. Record a returned
run ID before inspecting it. Subsequent observations validate repository, workflow
ID, workflow commit, event, exact intent/candidate title, and attempt number one.
The [workflow run API](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28)
supports lookup and bounded reconciliation. `success` becomes passed; `failure`
becomes failed; other completed conclusions become error. Reruns are distinct
work and cannot overwrite the original occurrence's evidence. Evidence records
the namespaced provider run/attempt ID and the plan's exact subject fingerprint.

Persist `uncertain` **before** submitting. Only the successful revision claimant
may issue the POST. A timeout, cancellation, invalid acknowledgement, API-process
death, or lost database acknowledgement never authorizes another POST. Recovery
searches for the exact intent/candidate title; absence, multiple matches, provenance
mismatch or a truncated search remains unresolved. A known refusal is `rejected`.
This prevents automatic duplicate submission, but cannot guarantee delivery when
the process dies between reserving and sending. Automatic compensation and proof
that a permanently absent dispatch was never sent remain future work. Do not label
this exactly-once external execution.

Native human owners can use `POST /api/verification-checks/{intent_id}/resolve`
with an idempotency `key`, `expected_revision`, an existing provider `external_id`
and a reason. This attaches a provider-confirmed run to the current uncertain
intent. It records the actual human, reason, provider ID and timestamp; concurrent
identical retries acknowledge that resolution, while stale/conflicting decisions
fail. The provider must independently confirm the exact original workflow and
candidate. This action cannot supply a verdict, force acceptance or issue another
dispatch. Scoped workflow capabilities cannot call it, including with a human
cookie supplied alongside the bearer. This is CI intervention, distinct from the
separate reusable Human Review business program.

### Durable check reports and provenance

`CheckRequirement.requires_reports=true` freezes a requirement for nonempty durable
report evidence in the verification plan. It is optional: ordinary operation
results and other checks need no blob wrapper. Server admission rejects a bound
runner that cannot provide the required reports. Report-enabled bindings require
`UNIFAI_ARTIFACT_DIRECTORY`; the existing artifact service owns publication,
integrity, owner access and content streaming. No second blob store is introduced.

`GitHubCheckReports` selects the configured names from the already validated,
completed workflow run. Missing, duplicate, expired, oversized or mismatched
artifacts cannot satisfy the check. It verifies run identity and workflow commit,
then freezes a `CheckReportSource` manifest with provider object ID, name, media
type, byte count and digest before downloading. A repeated refresh uses that frozen
manifest rather than silently choosing a replacement provider object.

The [GitHub artifact API](https://docs.github.com/en/rest/actions/artifacts?apiVersion=2022-11-28)
provides artifact identity/digest metadata and a short-lived archive redirect. The
transport accepts only HTTPS locations matching the explicitly configured
`archive_hosts`, with no URL user information, fragments or alternate ports. It
sends a fresh credential-free request to that host, forwarding neither API tokens,
cookies nor inherited client authorization, and follows no further redirects.
Actual streamed bytes must match the admitted size and SHA-256 before the existing
artifact repository commits them. Archives remain opaque bytes; this path does
not extract files or execute content. Signed download URLs are not stored in
programs, check records or evidence.

`CheckReportCollector` publishes under stable owner/intent/source identities in
the `verification-reports` namespace. If publication commits but the check-record
acknowledgement is lost, retry recovers those bytes without reopening a now-expired
provider archive. Partial transfers close their source and release staging on
failure/cancellation. The completed report set must match the admitted manifest.

Only then can the check record its evidence. The immutable receipt carries the
exact subject fingerprint, namespaced provider run/attempt, admitted configuration
digest and `CheckReport` references to verified local bytes. Evidence admission
checks report ownership/reference identity and rechecks the deadline after report
authorization I/O. Duplicate receipts remain acknowledgements; changing report
provenance or configuration under that receipt conflicts. Artifact read authority
is separate from verification-plan authority: a workflow verification capability
does not itself grant report downloads.

These guarantees establish byte identity and trusted-run association. They still
trust the admitted workflow's implementation of the actual check, and do not prove
that arbitrary report contents are correct. Report absence/invalid provenance
fails refresh; infrastructure retries follow the caller's execution policy rather
than being silently treated as a passed check. Live provider validation, external
job cancellation, report retention policy and review/report UI remain open.

The registered `await_check_run@1` program takes `intent_id`. It reuses the bounded
inspection configuration with a `refresh_verification_check` operation bundle.
Each refresh is short; waits use native runtime timers. `resolved` means refusal
or completed **recorded evidence**, while `poll_limit` may retain uncertainty.
An individual passed check does not imply the entire verification plan is accepted.
Cancelling the waiter/plan does not cancel an external GitHub job; cancellation
policy and a reconciled provider-cancellation operation remain open.

Deterministic tests cover concurrent submission, acknowledgement loss, provenance
denial, API restart, exact-subject evidence and graph/code composition through real
thread/process receivers, native HTTP processes, Mongo and Redis. The GitHub peer
is an explicitly identified protocol fixture; these results do not establish live
GitHub execution, remote receiver parity or a complete
ADLC acceptance workflow. No GitHub credential is placed in a program, invocation
bundle, workflow capability or execution result.

Native tests cover graph -> request -> reusable code waiter on thread/process
runners, accepted and cancelled plans, scope/role denial, and safe retryable service
failures. Separate-worker Temporal scenarios observe a real timer, stop the worker,
admit evidence while it is absent, restart it, and replay root/child histories.
Workflow capabilities remain outside those histories. These are local receiver
proofs; matched Kubernetes/OpenShell verification placement remains open.

Capability issuance/provisioning/rotation is currently explicit. Opt-in bounded
renewal and authentication-time root-lifetime enforcement are implemented below.
Automatic run-admission binding, private-file collection, per-call delegation
and stale-attempt fencing remain required production work. Bounded upkeep now
persists terminal/expired grant retirement, including fixed-expiry grants.
Default directory binding shares one admitted capability within a root; it does
not establish per-node least privilege or hostile-process isolation. Bound grant
lifetimes to the intended waiting duration and rotate bindings through a trusted
operator/controller; reusable waits do not renew their own authority.

## Durable artifacts: implemented API/storage foundation

Configure an absolute `UNIFAI_ARTIFACT_DIRECTORY` on the API server, outside worker
or sandbox filesystems. `UNIFAI_ARTIFACT_MAX_BYTES` bounds each publication (default
64 MiB). The filesystem implementation targets durable POSIX storage. Application
policy depends on the `ArtifactRepository` port; domain/application code imports
no filesystem or HTTP integration.

Authenticated `POST /api/artifacts` streams the body and takes a JSON-encoded
`PublishArtifact` in the `X-Artifact-Metadata` header: stable `key`, logical `name`,
`sha256`, `size_bytes`, optional `namespace` (default `default`), `media_type`
and input blob references. The
server derives ownership from authentication. `GET /api/artifacts/{artifact_id}`
inspects metadata; `/content` streams bytes. Unicode header metadata must use ASCII
JSON escapes. Retrying the same owner/namespace/key/content returns its prior publication;
changing content or metadata under that identity conflicts. Foreign reads are 404.

A domain `BlobArtifactRef` contains identity/hash/size, never a worker-local path or
credential. Workload-local path metadata is `WorkspaceArtifact`; it has no durable
storage guarantee. Atomic staging publishes only complete, verified content and
metadata. Consumers must complete verification before accepting streamed downloads.
The API/storage component survives API restart. Native user sessions issue scoped
transfer credentials with `POST /api/artifact-access`; read/list/revoke management
uses user authentication. The credential is returned once with no-store caching;
persistence stores its hash. Bearer credentials authenticate only artifact transfer
and `/api/artifact-access/self`, never ordinary platform routes or grant management.
Grants constrain owner, read/publication actions, explicit namespaces or blob IDs,
per-transfer bytes and expiry. Revocation persists across API restart; existing
admitted streams finish under their admitted limits. These manually issued grants
are separate from the managed root-bound workflow capability below.

Normal streaming transfer uses `providers/artifact_store`,
`operations/publish_artifact`, and `operations/materialize_artifact`. Factories,
provider dependency references, async preparation and receiver cleanup are shared
with other elements. Configure receiver-only `UNIFAI_ARTIFACT_ENDPOINT` as the
platform server origin and use a protected `access_token` resource field or a
private absolute `UNIFAI_ARTIFACT_ACCESS_FILE` binding. Manual file bindings must be
regular, private, owned by the receiver OS user, and at most 4096 bytes; symlinks
are refused. HTTPS is required by default;
`UNIFAI_ARTIFACT_ALLOW_INSECURE=true` is an explicit local-test option. URLs and
credential-file paths stay outside behavioral resource configuration. The provider
checks that its credential belongs to the invocation owner and does not follow
redirects. Its HTTP client closes with the constructed element scope.

For managed workflow transfer, enable `UNIFAI_ARTIFACT_WORKFLOW_ENABLED=true`
with artifact storage, Mongo, recoverable issuance/encryption and the existing
private workflow credential directory. Use the same purpose settings on scheduled
admission workers. Request `artifact@1` in normal `workflow_access`, for example
`scope={"actions":["read","publish"],"namespaces":["project"]}` with a bounded TTL
and optional renewal horizon. The submission derives the root and freezes human
approval. The scope supports explicit blob IDs and a per-transfer `max_bytes`,
which cannot exceed the operator's `UNIFAI_ARTIFACT_MAX_BYTES`.

The shared reservation/delivery/retirement path provisions private material;
Mongo purpose records retain hashes and use atomic renewal plus API/database-clock
expiry fences. Authentication requires an active owned root and rechecks the grant
after root observation. Terminal/expired/revoked authority retires private material
through the existing cleanup outbox. Reduced operator byte limits revoke broader
grants. Retrying uncertain issuance preserves the original scope and credential.

With a managed source installed, the normal artifact factory resolves only
`artifact@1` for its owner/root and verifies the returned grant before transferring.
Unavailable managed material never falls back to an operator token file. Explicit
protected resource credentials remain a separate operator-configured authority.
The HTTP client disables environment proxy discovery and redirects. Artifact grant
management uses the same human-principal guard as review/verification: a bearer
cannot obtain human authority even alongside a valid human session.

This is trusted Local delivery. Isolated Kubernetes/OpenShell delivery, credential
rotation, full recovery combinations and atomic fencing of already admitted effects
remain separate acceptance work. An active stream is not revoked transactionally.

Workspace file access uses the receiver's `UNIFAI_WORKSPACE_ROOT`, default
`/tmp/unifai-workspaces`. A shared domain layout gives coding and transfer the
same isolated/shared binding semantics. Transfer pins directory handles, rejects
symlink escapes and special-file sources, and scopes paths to the root execution.
Materialization verifies bytes in private staging, creates an atomic destination,
retains identical retry results, and refuses to overwrite different content.
Downloads enforce authorization and scoped byte admission before response headers,
and use attachment/no-store/nosniff/restrictive CSP headers for untrusted content.

The deterministic local proof runs the production coding plugin, publishes its
file from a graph, deletes the complete source workspace, restarts the API, and
restores through a separate code program on thread/process runners. It makes no
model calls. The newer [coding repair checkpoint](evidence/2026-11-05-coding-repair.md)
adds workflow-integrated executable fixture checks and restored repair inputs.
The [production-checker integration](evidence/2026-11-06-engineering-program-checks.md)
extends that journey through the actual App. Full live Engineering, Kubernetes/
OpenShell handoff, retention policy and hard-crash staging recovery remain open.
Credentials in a receiver-private file are not isolated from arbitrary hostile
code running as that same OS user. Tenant/profile admission and a stronger transfer
boundary remain production-hardening work; see the [scoped file-I/O investigation](../integrations/run-engine-environment-file-io-request.md).

### Commits and other output references

The managed-blob component is optional. An operation may return ordinary typed
data, a Git repository/commit reference, an image digest or any other validated
result model. For committed source, use a pinned repository revision and bind test,
review and deployment evidence to it; do not require a second snapshot upload by
default. `BlobArtifactRef` specifically describes managed bytes, including
uncommitted patches and reports. Optional Git resolution/checkout and the native
verification-plan/evidence APIs are implemented above. Workflow check orchestration,
source publication/retention and remote candidate handoff remain in the active queue.

## Execution-bound workflow authority

Review and verification access services require the application
`ExecutionGrantAuthority` port. Production composition supplies
`ExecutionGrantAccess` over the existing `ExecutionService`; there is no optional
permissive production fallback. Authentication checks the actual owned root and
native liveness without submitting/recovering work or expanding its child tree.
Missing, foreign, child-scoped, cancelled or terminal roots cannot authenticate
workflow grants. Unknown/unavailable native authority fails closed with a safe
503 rather than accepting cached authority or falling back to a human cookie.
Descendants may use a grant bound to their actual root; a child execution ID
cannot be substituted for that root identity.

Humans may pre-provision an admitted policy/root grant before the root exists,
but that credential cannot operate until the actual root is active. Issuance for
an existing closed/cancelled/foreign root is refused. Native completion is checked
even before a submission acknowledgement settles or a stored running projection
is refreshed. Requested cancellation also denies authority immediately through
the execution service. Existing human inspection/decision authority remains
separate. Manually issued retained artifact access has its own lifetime; managed
`artifact@1` capabilities are root-bound as described above.

After completion, use the authenticated human session to inspect retained review/
verification results. Workflow credentials cannot be kept alive for reporting.
Grant metadata retains its issuance and revocation audit; effective
authority additionally depends on the root. Do not reuse execution identities or
interpret unexpired metadata alone as proof of liveness.

Verification E2E workflows now publish/start through the same native API that
issues their grants. Their root and child records are durable Mongo records,
not an unrelated test-local coordinator. Receiver endpoint/directory bindings
remain private. The Temporal scenario now pins that API to the worker's actual
host configuration; restart/replay verification remains at the planned milestone.

This is an authorization-time liveness check, not an atomic stale-attempt fence
on every external effect. A request admitted before termination still needs the
appropriate resource-specific fencing/idempotency rules. Automatic provisioning,
rotation, managed secret delivery and secret-file retirement remain open;
this change does not replace those requirements or introduce a new scheduler.

## Bounded workflow credential renewal

Human issuance of review/verification access accepts optional
`renewable_for_seconds`: an absolute renewal horizon measured from issuance,
not an extension added on each maintenance pass. It must cover the initial
`ttl_seconds` and cannot exceed 30 days. Omitting it retains fixed expiry.
The returned grant carries safe `renewal` metadata (`ttl_seconds` and
`renewable_until`); the opaque credential is returned through human issuance.
Opt-in keyed retries below recover the original credential after response loss.

The existing API reconciler invokes the narrow `CredentialMaintenance` port.
Each purpose service visits bounded indexed pages of unrevoked grants, rechecks
current policy and actual root authority, and renews during the final third of
the lease. Renewal
changes only expiry, capped by the original horizon. Token hash, owner, scope,
human issuer and issuance audit remain unchanged. A pending root cannot renew;
known closed roots or withdrawn policy revoke grants even before renewal is due.
Unknown native
authority preserves the original expiry without extending authority. Expired
credentials never resurrect, including after a slow authority lookup or an API
restart. Authentication independently requires the actual live root.

Mongo compares the original stored document/expiry and revocation state before
updating. Its server-clock expiry fence prevents an API process with a stale
clock from renewing an already-expired grant. Concurrent renewal has one winner;
a renewal cannot overwrite explicit revocation. The storage helper owns this
atomic mechanism, while purpose services own authorization. Reconciliation starts
after service composition and drains before its clients close. Configure upkeep
cadence and page capacity for the requested lease lengths; an outage or a backlog
can allow a lease to expire, and does not authorize recovery of the old token.

The native Human Review test keeps the original credential usable beyond its
initial expiry while waiting, then verifies refusal after the root completes.
The wait retains no element invocation. This is same-token bounded renewal,
not token rotation, automatic admission provisioning or private remote delivery.
Secret-file collection and current-image Temporal/Kubernetes/OpenShell renewal
evidence remain separate milestones. Recoverable human issuance/private material
retirement and pre-provisioning API restart are described below; running-root
API/worker restart renewal is not established by that proof.
Owner-bound retained artifact access is unaffected.

### Persisted terminal and expiry retirement

Review/verification upkeep includes fixed-expiry grants. A pre-provisioned root
that is not yet present stays pending; known terminal/cancelled/foreign or invalid
roots revoke their grants on the next bounded visit. Current policy withdrawal
also revokes grants whose issuance requires that policy. Verification read/cancel-
only access retains its separately scoped authority over frozen plans; it does
not admit creation or check dispatch. Authentication checks actual root liveness, so
metadata reconciliation is not required to deny a terminated root's bearer.
Unknown native authority preserves an otherwise-valid grant's original expiry.

Expired grants retire without a native lookup. Expiry retirement compares the
observed expiry and uses Mongo's clock as well as application time. A stale
snapshot cannot revoke a concurrently renewed lease, and an API clock running
ahead cannot retire a lease that Mongo still considers valid. Terminal/policy
revocation is irreversible regardless of renewal races. Stored grant issuance,
scope and credential hash remain available for audit; retirement never deletes
these records or reissues a token.

`MongoCredentialLifecycle` owns the shared bounded unrevoked-record index and
expiry CAS mechanisms. Purpose services own authorization and their independent
scan cursors. Revoked grants leave the scan, avoiding repeated native lookups.
Persisted retirement is eventual under upkeep capacity/outages; this is not an
atomic fence for external effects already admitted before termination. Operator-
owned credential files are still not collected automatically, and automatic
admission provisioning, managed private delivery and rotation remain unfinished.

## Recoverable human workflow credential issuance

`UNIFAI_RECOVERABLE_CREDENTIAL_ISSUANCE=true` enables encrypted issuance reservations
for review/verification services. It requires Mongo, at least one enabled purpose
service and a valid existing `UNIFAI_CREDENTIAL_ENCRYPTION_KEY` Fernet key. Key
format is checked before client allocation. The private store is distinct from
immutable reusable configuration secrets and is maintained while this feature is
enabled; disabling it also stops its material-retirement reconciler.

Send `Idempotency-Key` (1–128 characters) to the existing human
`POST /api/review-access` or `POST /api/verification-access` endpoint. The same
authorized owner/purpose/key, request and human issuer recover the original grant
and token, including after an API response loss/restart. Changing the root, scope,
TTL/horizon or human approval conflicts (409) when otherwise admitted. Current
authorization is rechecked; revoked/expired/closed issuance cannot rejuvenate.
Supplying a key without configured private storage fails unavailable (503).
Ordinary explicit issuance without a key keeps its fresh-grant/hash-only behavior.
Successful human responses use `Cache-Control: no-store`.

A shared HTTP `HumanPrincipal` guard rejects any supplied bearer on human-only
grant management and reviewer endpoints, even alongside a valid human cookie.
The real API test exposed verification issuance accepting that combination;
issuance/list/revoke now share the guard. Team ownership and the acting human
remain distinct. Workflow bearer authentication never obtains human authority.

Purpose services own authorization and typed scopes. Shared domain `WorkflowGrant`
owns their common issuance/lease invariants. `CredentialIssuance` reserves immutable
original metadata plus encrypted material before purpose-grant registration.
Mongo insert-if-absent recovers partial/uncertain registration without overwriting
renewal/revocation. Scope, issuer, original time, TTL and horizon remain fixed;
an authorized retry observes current renewal state with the same credential.
Private material never enters Program definitions, prepared requests or profiles.
The new material store refuses plaintext cipher passthrough and invalid ciphertext.

The existing API upkeep performs bounded material retirement after observed grant
revocation, known root closure or a database-clock-fenced maximum lifetime.
Unknown native authority cannot extend authority or discard otherwise-valid
material. Retirement removes ciphertext and retains original audit metadata;
purpose grant records retain their hash/scope/issuance audit. This is logical
material retirement, with no second scheduler or environment manager.

Actual Mongo and signed-cookie TCP API tests cover concurrent retries, same-key
conflicts, API restart before root admission, native waiting/cancellation and
material retirement. They do not prove a running Local root survives API restart.
Credential rotation remains unfinished. Generic event starts and unattended
scheduled access use private consent described below; portable credential-user
tags cannot supply that proof.
See [current progress](status.md).

### Admitted workflow capabilities

Manual `POST /api/executions` and canonical Session
`POST /api/sessions/{session_id}/executions` accept optional `workflow_access`.
Each requirement names an installed versioned purpose, its typed purpose scope
and bounded lease/horizon. For example:

```json
{
  "purpose": "review@1",
  "scope": {"policies": ["release@1"], "actions": ["open", "read", "close"]},
  "ttl_seconds": 60,
  "renewable_for_seconds": 180
}
```

Root identity comes from the actual invocation, never the scope object. The
configured review/verification services validate their own schemas, actions and
current owner policy. Unknown purposes, invalid scopes and duplicate purposes
fail before private material is created. Managed admission requires recoverable
issuance and the [managed private binding](#managed-private-workflow-delivery);
missing configuration is 503.

Both HTTP paths require authenticated human authority for requested capabilities
and reject bearer-plus-cookie elevation. Application calls pass the human
explicitly; `credential_user_id` and context tags are not approval. A secret-free
`WorkflowAccessApproval` freezes owner, root, acting human, approval time, requested
scopes and a digest of the full invocation request. Session staging persists that
approval with its pending turn, before the existing reconciler can submit it.

`ExecutionService` depends on the narrow `WorkflowAccessAdmission` port. The
submission claim owner provisions approved purposes before native dispatch,
through the existing keyed purpose services, encrypted store and receiver source.
Recovery uses the persisted approval and stable issuance keys, not a newly derived
human identity or approval timestamp. A changed request cannot adopt that approval;
revoked/expired grants cannot revive. All purposes are reauthorized before any
material is created. Partial/uncertain provisioning stays recoverable under the
existing submission lifecycle. Cancellation during provisioning prevents dispatch.

Credential root authority observes application records/native status through
read-only ports, without depending on submission or recursively projecting child
runs. The general execution liveness method remains necessary for review's exact
child checks. No new scheduler, execution registry or environment owner is created.

Authenticated human `GET /api/catalog/workflow-access` returns installed issuer
descriptors filtered by the selected owner, with `Cache-Control: private, no-store`.
The application access registry asks each issuer for its own request schema; adding
an issuer does not require catalog conditionals. Root identity is omitted from
authoring scopes and supplied by actual admission. Review/check policy choices are
owner-filtered, artifact byte bounds reflect deployment limits, and no catalog read
authorizes or provisions a grant. Actual admission revalidates current policy.

Production TypeScript clients `startProgram` and `startProgramSessionTurn` support
the same declarations and expose the frozen approval. They receive no workflow
token. Manual Program invocation renders these issuer schemas through shared fields,
selects nothing implicitly, and requires explicit approval for the selected scopes.
Uncertain retries retain the frozen permissions and inputs. Full Session permission
authoring remains part of UI convergence. Scheduled access uses bounded, revocable source consent
below. [Generic event starts](#authenticated-event-driven-program-starts) now use
the same admission/provisioning path. Provider-specific ingress, rotation and
isolated remote delivery remain outstanding. Portable tags never supply consent.

### Multi-purpose admission and recovery

All requested purposes belong to the same root submission claim. Provisioning
can commit a grant before another purpose becomes unavailable, or lose an
acknowledgment after both grants commit. Neither permits native dispatch until
all purposes are confirmed. A replacement application service uses the persisted
approval, prepared settings and keyed reservations; it does not recreate human
consent, replace material or start another native identity. Current purpose policy
is checked again before recovery. Partial material remains subject to the normal
bounded retirement lifecycle.

Cancellation is checked before provisioning and again before dispatch. If a
purpose refuses because cancellation closed its root during issuance, the root
finishes cancelled rather than misclassifying cancellation as a policy failure.
An unrelated refusal retains its failure classification. This is submission
admission control, not an atomic fence for external effects already in flight.
Idempotency compares canonical JSON input encodings, preserving distinctions
between booleans, integers and floats while ignoring object-key order.

Real Mongo cases cover competing submissions, partial issuance, lost grant
acknowledgment, reconstructed services, policy withdrawal and cancellation before/
during recovery. A focused Temporal journey runs two concurrent roots with both
review and verification, restarts the API while the worker remains live, then
cancels one root and approves the other. Original human approval, native identity,
private-material isolation, independent cleanup and replay are checked. This is
trusted thread/process delivery, not remote sandbox or full ADLC acceptance. See
[the scoped recovery evidence](evidence/2026-11-05-admission-recovery.md).

### Managed private workflow delivery

Set `UNIFAI_WORKFLOW_CREDENTIAL_DIRECTORY` to an absolute private directory to
deliver keyed, human-approved review/verification grants to trusted local/shared
filesystem receivers. On the API this requires recoverable issuance and its vault
key. Receivers need the directory binding, not the vault key. This is a private
runtime setting; credentials and directory bindings are not added to Program
definitions or prepared invocation data.

Application-owned `CredentialDelivery` and `WorkflowCredentialSource` ports keep
issuance/retirement separate from receiver resolution. Bootstrap wires the file
adapter into the normal element build context. Existing review and verification
factories use that source; their HTTP gateways still validate actual root/grant
authority. A configured source failure cannot fall back to operator token files.
Source unavailability becomes a private, retryable infrastructure failure at the
gateway/receiver boundary rather than an ordinary application failure.
Explicit operator-owned bindings remain a distinct supported mode and are not
collected by managed cleanup.

Managed slots bind owner type/ID, root, purpose, original approval and destination.
Directories/files require current-user ownership and private permissions; bounded
reads refuse symlinks and nonregular files. Concurrent writers cannot replace
different material. More than one active grant for a root/purpose fails closed
instead of selecting the latest or combining permissions. Keep per-root entries
below the adapter's 512-entry scan bound, including token-free fences.

Ciphertext retirement atomically marks a durable Mongo `cleanup_pending` outbox.
The existing reconciler removes managed files and acknowledges cleanup separately.
Failures or lost acknowledgements retry after controller reconstruction, even
when ciphertext is already gone. An unconfigured destination stays pending.
Token-free slot markers remain to reject delayed delivery after retirement;
issuance audit is retained. This is logical collection, not backup/media erasure.

Native graph/backend Human Review and verification tests exercise thread/process
receivers without test-written token files. Mongo tests reconstruct the cleanup
controller after an actual file-collection failure. Those original tests restart
before native root admission. The newer multi-purpose recovery and generic event
tests add scoped running-root/API and worker-restart/replay proof; scheduled
consent has its own focused worker proof. None proves rotation or remote delivery. Do not
expose the all-root directory or vault key to an untrusted sandbox. Kubernetes/
OpenShell require separately scoped receiver delivery and matched-image proof.

## Owner-scoped execution profiles

`PlatformSettings.profile_access` (`UNIFAI_PROFILE_ACCESS`) configures which
installed profiles each user/team owner can select. Application
`ExecutionProfileAccess`, behind the `ProfileAccess` port, resolves one detached
safe catalog for discovery, placement previews and compilation. Unconfigured
policy retains the deployment catalog. A configured policy denies unmatched
owners unless it supplies an explicit default grant. An owner rule with no grant
explicitly denies that owner, even when a default exists. User/team identity types
are distinct; mutable display names do not affect ownership. Duplicate rules and
grants referencing uninstalled profiles fail startup.

For example, the following value permits one team and denies unmatched owners:

```json
{
  "owners": [{
    "owner": {"type": "team", "id": "engineering"},
    "grant": {"profiles": ["coding-sandbox"], "default_profile": "coding-sandbox"}
  }]
}
```

Profile names/capabilities come from installed deployment metadata; the policy
does not define SDK targets, images, secret settings or environment lifetimes.
Compilation checks workflow defaults, node/operation/condition selections, named
environment definitions and recursively owned/pinned Program scopes under the
execution owner. Static forbidden selections fail before execution records/native
dispatch. Backend Program payloads receive only the permitted target set; runtime
selection outside it fails with the application `PlacementRefused` contract error
(`placement_refused`) before invocation. Explicit child environment imports remain
required. This is the permitted capability ceiling, not a claim that every
included profile was used by the implementation.

`GET /api/catalog/execution-profiles` uses the authenticated request owner. The
resource form, workflow placement editor and interim Programs page share a query
that passes team scope and keys its cache by acting user plus owner type/id. The
server still authorizes every new preparation; client cache contents confer no
authority. Draft configuration may retain a choice that a later policy disallows.

Prepared snapshots and execution records expose `admitted_profiles`: safe allowed
names, default and retained-environment capabilities. Its identity is frozen with
the request, and actual child records use their own admitted default. Scheduled
template-to-tick admission now preserves both these profiles and work limits.
Cancellation before admission has no admitted catalog. These values describe
admitted authority, not observed placement for individual occurrences.

Changing deployment policy governs new preparations; it does not rewrite running
or published execution snapshots. Immediate grant revocation, tenant capacity/
fairness, credential lifecycle, stale-attempt fencing and remote/replay acceptance
remain open. Cooperative profile filtering does not sandbox arbitrary installed
Python or establish identity-provider membership on its own.

## Root-wide work admission

`PlatformSettings.work_limits` enables a durable allowance shared by a root and
all its descendants. It requires Mongo storage; no process-local fallback silently
weakens distributed enforcement. It is currently opt-in deployment policy, not
an authored Program configuration or a client-selected budget. For example:

```sh
export UNIFAI_WORK_LIMITS='{"max_dispatches":1000,"max_children":100,"max_depth":8}'
```

The compiler freezes the limits and installed admission reference into every
prepared Program scope. Prepared metadata and public execution records expose the
same limits, included in immutable request digests. Existing submissions retain
their admitted limits. Graph and backend Programs share `BudgetedOperations`,
which reserves work before delegating native invocation/child creation. It does
not schedule, retry, replay or manage environments. Root initialization and
reservations use recorded native invocations on the control-plane thread runner;
they do not allocate the selected sandbox or borrow a run environment.

Application `WorkBudgetRepository` is the atomic port. Domain `WorkLimits`,
`WorkBudget`, `WorkReservation` and `WorkUsage` own portable policy and invariants;
`MongoWorkBudgets` implements single-document atomic conditional admission.
Independent workers share counters. Duplicate reservations with the same identity
and fingerprint spend once; changed work, owner or policy conflicts. A root cannot
be implicitly recreated by a child when its ledger is missing. Depth starts at
zero for the root. The next child is checked before its native creation.

Dispatch allowance counts requested native invocations through the Program port,
including graph framework invocations. It does not count admission itself or the
published cancellation callback. Children count across the entire tree, rather
than independently per parent. Stable per-execution dispatch ordinals and native
child keys identify reservations; fingerprints bind their request and placement.
An admitted but refused/uncertain downstream call keeps its allowance: no refund
can safely assume the effect never happened. Exhaustion returns a contract failure
with `WORK_LIMIT_EXCEEDED`; unavailable storage fails closed as infrastructure.

Both counters are capped at 10,000 and depth at 128 to bound the retained root
document. Ledger lifetime currently follows retained application data; there is
no automatic active-ledger expiry. Do not delete an active root's reservations.
Admission clients are explicitly scoped per invocation; connection pooling/load
behavior has not been established. These cooperative contracts do not confine
malicious installed Python or replace tenant authorization.

This slice does not provide physical concurrency/provider-cost/token budgets,
physical delivery-attempt accounting, tenant fairness, stale-attempt fencing,
revocation, or admitted dynamic plans. Native per-run limits remain distinct.
Thread/process and production-client checks cover the new path; Temporal replay,
worker restart and current-image Kubernetes/OpenShell acceptance remain queued.

## Current architecture

```text
+----------------------------------------------------------------------------+
| UNIFAI APPLICATION                                                         |
+----------------------------------------------------------------------------+
|  +----------------------------------------------------------------------+  |
|  | Services and contracts                                               |  |
|  +----------------------------------------------------------------------+  |
|  | ProgramService | ExecutionService | ProgramSessionService            |  |
|  | Program definitions | element bundles | graph state and reducers     |  |
|  | Ports: ProgramRuntime | ProgramExecutionGateway | repositories       |  |
|  +----------------------------------------------------------------------+  |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| UNIFAI ADAPTERS AND COMPOSITION                                            |
+----------------------------------------------------------------------------+
|  +----------------------------------------------------------------------+  |
|  | Native API, execution adapters, and receiver services                |  |
|  +----------------------------------------------------------------------+  |
|  | FastAPI | compiler / gateway | Mongo records | Redis interactions    |  |
|  | Receiver: existing factories, credentials, channels, approval gate   |  |
|  | Worker setup: installed modules, settings, lifecycle ownership       |  |
|  +----------------------------------------------------------------------+  |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| RUN ENGINE INFRASTRUCTURE                                                  |
+----------------------------------------------------------------------------+
|  +----------------------------------------------------------------------+  |
|  | Execution and native ownership                                       |  |
|  +----------------------------------------------------------------------+  |
|  | Local host OR Temporal service and generic CoordinationWorker        |  |
|  | Graph traversal | child runs | invocations | environments | recovery |  |
|  | Selected backends execute installed UnifAI entrypoints               |  |
|  +----------------------------------------------------------------------+  |
+----------------------------------------------------------------------------+
```

The application packages import no engine or HTTP adapters. New execution paths
are async; synchronous legacy element calls and SDK construction run off-loop
under explicit ownership. Cancellation drains owned work before resource cleanup.
There is no request-side async bridge or nested event loop in this path.
Native async element calls are awaited directly. State-based elements can return
UnifAI's GraphState; application ProgramState validates their declared changes,
and the receiver binds these channels to the native engine state contract.

### Execution sequence and ownership

These arrows are runtime calls. Application services depend on their own ports;
the outbound adapter implements those ports and imports the engine SDK.

```text
+-----------------+  +-----------------+  +-----------------+  +-----------------+
| UNIFAI          |  | UNIFAI          |  | UNIFAI          |  | RUN ENGINE      |
| FastAPI adapter |  | App services    |  | Engine adapter  |  | Infrastructure  |
+--------+--------+  +--------+--------+  +--------+--------+  +--------+--------+
         |                    |                    |                    |
         |-- submit --------->|                    |                    |
         |                    | authorize, pin     |                    |
         |                    | program revision   |                    |
         |                    |-- prepare port --->|                    |
         |                    |                    | compile graph,     |
         |                    |                    | bundles, placement |
         |                    |<-- snapshot -------|                    |
         |                    | persist intent     |                    |
         |                    |-- start port ----->|-- start run ------>|
         |<-- accepted -------|                    |                    |
         |                    |                    |                    | schedule
         |                    |                    |                    | dispatch
         |                    |                    |                    |
         |-- observe -------->|-- inspect port --->|-- handle/status -->|
         |                    |<-- app result -----|<-- engine result --|
         |<-- app response ---|                    |                    |
```

The engine dispatches an installed UnifAI receiver into the selected environment.
Being inside an engine-managed pod or sandbox does not transfer ownership of
UnifAI's application behavior to Run Engine:

```text
+-----------------+  +-----------------+  +-----------------+  +-----------------+
| RUN ENGINE      |  | UNIFAI          |  | UNIFAI          |  | UNIFAI          |
| Infrastructure  |  | Receiver adapter|  | Application     |  | Codex adapter   |
+--------+--------+  +--------+--------+  +--------+--------+  +--------+--------+
         |                    |                    |                    |
         | acquire pod/       |                    |                    |
         | sandbox            |                    |                    |
         |-- invoke bundle -->|                    |                    |
         |                    |-- construct ------>|                    |
         |                    |                    | dependencies first |
         |                    |                    | factories/builders |
         |                    |                    | typed coding call  |
         |                    |                    |-- coding port ---->|
         |                    |                    |                    | run CLI
         |                    |                    |<-- typed result ---|
         |                    |<-- typed result ---|                    |
         |<-- engine state ---| release resources  |                    |
         | merge state        |                    |                    |
         | next graph step    |                    |                    |
         | release owned      |                    |                    |
         | environment        |                    |                    |
```

The receiver owns invocation-scoped construction and closes partially built
dependencies on failure. The Codex adapter owns its subprocess, CLI protocol,
private home and cancellation cleanup; it never provisions compute. Run Engine
owns the physical environment and any grants held by child programs. A named
environment survives its individual invocations until its owning run ends;
releasing an invocation does not destroy that shared environment. An externally
owned OpenShell sandbox instead remains its external owner's cleanup duty.

Node/token/approval events use the application interaction port and Redis adapter;
they are separate from engine lifecycle observation in the first sequence.
This separation gives services, construction and vendor execution distinct
responsibilities. Narrow ports preserve dependency inversion, while registered
specifications/factories let new elements reuse execution without compiler changes.
These are architectural mechanisms with boundary tests, not a claim that every
remaining legacy module has completed the migration.

### Profile persistence and authoring

Execution metadata is separate from an element's `config`. The saved resource
shape is `execution: {profile: "approved-name"}` alongside its configuration.
Nodes, conditions and operations accept that preference; a dependent LLM or tool is
constructed inside the invoking node's environment.

| Location | Stored meaning | Current authoring support |
| --- | --- | --- |
| Operator platform settings | Approved name -> concrete backend/image/policy; platform default | Deployment configuration |
| Library resource | Reusable `execution.profile` preference | Native resource API, persistence and resource-editor selector |
| Blueprint resource/reference | Optional override of that resource's preference | Typed blueprint authoring API; not the element's config |
| Blueprint workflow and plan | `execution_profile`, named `environments`, per-step `execution` and `condition_execution` | Workflow save dialog and typed blueprint API |
| Program definition/revision | Default `execution_profile`, step selections and named environments | Native program API; immutable revision on publication |
| Prepared execution record | Resolved concrete backend configuration for this execution | Persisted before submission and reused during recovery |

The resource editor now offers a Run environment selector for nodes and conditions.
Authenticated `GET /api/catalog/execution-profiles` exposes approved names,
the platform default, and the names supporting shared run environments. It never returns runner settings, images, mount paths,
network policies or environment values. Approval currently means deployment
configuration; this is not a per-user profile ACL system.

The generic configuration form combines only the resource name with the element
schema. Execution preferences stay beside `cfg_dict` throughout client mapping,
save/update and reload. An omitted preference preserves the saved value; an
explicit null profile restores inheritance. Updates carry the loaded version and
selected team scope. A profile-discovery failure preserves the existing selection;
a removed profile remains visible as unavailable rather than silently becoming
the default. Final approval and compatibility checks still happen before dispatch.

The workflow save dialog selects a workflow default, declares named environments,
and chooses placement independently for every node and its attached condition.
These settings survive save/reload, resource resolution and blueprint import.
Blueprint chat creation publishes a unique program snapshot containing them.
An explicit non-null default supplied to the program-import API overrides the
blueprint default; ordinary chat creation inherits the saved blueprint default.

Omitted/null step placement inherits the resolved element preference, then the
workflow and platform defaults. An explicit empty selection `{}` bypasses the
element preference and uses the workflow/platform default. A profile selection
overrides those defaults. An environment selection instead uses the declared
named environment. `condition_execution` follows the same rules and requires an
attached exit condition. Shared resources are not edited by these local choices.

Only profiles whose engine factory supports retained environments can be offered
for named reuse. Compilation rejects an unsupported named-environment profile
before dispatch. UnifAI does not implement environment provisioning or cleanup.
The editor asks the server to resolve resource preferences and validate current
placement. `POST /api/blueprints/draft/placement` inspects an unsaved draft;
`GET /api/blueprints/{id}/placement` first authorizes the saved blueprint. The
application-owned preview port returns profile names, environment names and binding
scope. It exposes no backend configuration. Shared compiler selection/capability
checks and dependency-closure validation are reused; inspection creates no engine
run, environment, program revision or secret record. Portable execution bundles
still reject unprotected literal credentials.

Preview requests are debounced and aborted when superseded/unmounted. Previous
results are hidden immediately when settings change. Query keys contain an
instance/generation identity rather than authored configuration, and preview cache
entries are discarded when no longer observed. Unavailable choices remain visible
rather than silently becoming another environment.

For example, two separately configured coding resources can share one run-owned
environment without merging their construction settings:

```yaml
execution_profile: trusted-worker
environments:
  coding: approved-coding-profile
nodes:
  - rid: $ref:coder
  - rid: $ref:tester
plan:
  - uid: implement
    node: $ref:coder
    execution: {environment: coding}
  - uid: verify
    node: $ref:tester
    after: implement
    execution: {environment: coding}
```

The profile must be deployment-approved and support retained environments. Coding
elements still need compatible workspace settings to access the same logical files;
sharing compute does not create shared CLI conversation history.

The production placement dialog and clients have been exercised in an isolated
browser fixture using real signed-cookie authentication, Mongo and Redis. This
proves the dialog's create/update/reload, inheritance and cancel behavior, not full
OAuth, team navigation or all application pages. The preview describes logical
invocation/run bindings, not a promise to delete pre-existing external compute.
Its result is not a persisted execution snapshot or a reservation: later execution
performs normal preparation and validation again. It currently covers blueprint
element/condition graphs, not arbitrary application-program behavior.

The UI submits application names, never arbitrary Kubernetes/OpenShell settings.
There is no chat run-only override. Any such override needs
to participate in the immutable submission identity rather than change a live
execution or retry silently.

A session pins its published program revision. Each turn prepares its own concrete
execution snapshot; retries of that execution reuse it. A deployment profile
change can therefore affect a later new execution, including another turn using
the same program revision, while leaving an existing prepared execution unchanged.
Named environment reuse is within an owning run and explicit child grants; it is
not implied across session turns.

### State, context and credential transport

| Value | Purpose | Transport/lifetime |
| --- | --- | --- |
| Graph state | Messages, outputs, IEM, threads and workspaces | Passed to invocations; UnifAI reducers merge changes through the engine |
| Execution context | Owner identity, acting credential user, session/root/current/parent IDs, scope and supported tags | Serializable engine payload; rebound to the actual run at installed entrypoints |
| Step context | Step UID, display metadata, neighboring element cards, branches and topology | Per-step invocation data; separate from reusable resource bundles |
| Element bundle | Validated root plus complete dependency specifications/references | Portable reusable configuration; no current state or credential service objects |
| Receiver runtime | Live auth/secret/tracing/interaction services and bindings | Constructed locally per invocation; never serialized into the engine request |

Ordinary nodes in one run retain the same execution identity. A program call gets
a child identity and parent/ancestor links while keeping the root, session, owner
and acting credential user. Parent/child business data travels through explicit
public input/output bindings, not an implicitly shared mutable state object.
Factories construct fresh dependency instances within an owned scope. The normal
node callable uses declared state channel access; this is an application contract,
not isolation from malicious Python plugins.

The signed login cookie is verified at FastAPI. The authenticator reads the
identity-session record, verifies expiry, resolves any selected team membership,
and derives the acting human server-side. Neither that cookie nor its login access
token is copied into normal execution context. For a team run, `identity` is the
team and `credential_user_id` is the authenticated human, not a team OAuth account.

Protected configuration fields become owner-scoped opaque references before
publication. The receiving environment reads its own deployment credentials and
decrypts the selected values locally. Dynamic OAuth providers receive a lazy auth
handle for the acting human/server pair; it obtains or refreshes credentials and
adds headers at the provider boundary. Codex can instead use its receiver-only
private API-key file. Kubernetes profiles carry Secret mount names and paths;
OpenShell profiles carry approved policy and connection configuration, not the
plaintext provider key. Native Mongo credential mode now requires an encryption
key at settings validation, matching the existing configuration-secret requirement.

The security model still trusts the control plane, installed plugins, workers and
receiver-local credential services. An identity ID in a serialized request is
metadata, not a signed credential or per-invocation secret capability. Receivers
must not accept arbitrary untrusted payloads or expose their credential stores as
public services. Declared secret fields are protected; a token manually pasted
into a prompt, state value or undeclared dictionary is not automatically scrubbed
from engine history. Existing plaintext OAuth records are not retroactively
encrypted by the new startup guard. The OpenShell mTLS/policy and private mounts
have targeted tests; the development stack does not prove production-wide TLS,
least-privilege secret access, revocation or authenticated browser hardening.

Built-in nodes now implement `async def run`; the base callable, packet handlers,
agent iterator/strategies, action execution, and LLM chat/stream contracts await
directly. Pure factories and state transformations stay synchronous. Model
`stream` returns an async generator; consumers own early closure with `aclosing`.
Tool-provider discovery is async and separate from pure factory construction.
The executor owns tool trace contexts across cancellation; agent completion uses
an async deadline. Tools expose one `async run` operation, and retrievers expose
`async retrieve`. Native APIs await directly; unavoidable blocking SDK work drains
inside its adapter before owned resources close. Approval gates await directly
and reuse the receiver's async Redis client. Pending ticket registration and
cancellation are owned, with payload-matched cleanup. Legacy channel transports
retain explicit offloading. Generic tool retry policies retry reads, while writes
require explicit application policy and idempotency. SDK agent nodes leave
configured dependency cleanup to their owner. Tool-level sandbox proxies are retired;
OpenShell execution placement remains an engine concern.

The `openai` and `gemini` extras provide the native SDKs. Their ordinary tests use
actual SDK parsing over in-memory HTTP/SSE transports, including early stream
closure, failure, cancellation, and bound-client ownership. GenAI's HTTPX response
scope compensates for nested SDK generators that do not close the response on
early exit; it keeps response lifetime inside the adapter and preserves borrowed
client ownership. See [the provider stream diagnostics](../.cursor/skills/debug-provider-streams/SKILL.md).

## Native reporting

`GET /api/reporting/overview` reports the selected authenticated owner's library
counts and last-observed active sessions. User and team IDs are distinct scopes.
Blueprint drafts, Program drafts, sessions and root executions remain distinct.
`GET /api/reporting/system` requires the acting human to satisfy application
`AdministratorPolicy`; selecting a team or supplying `userId` never grants authority.
Both endpoints reject bearer credentials, including bearer-plus-human-cookie requests.

The Mongo administrator directory reads `admin_users.value.admin_usernames` in
the configured admin database/collection on every authorization. Bootstrap
`UNIFAI_ADMIN_ALLOWED_USERS` applies only when that policy document is absent;
an empty persisted list explicitly denies everyone. Directory failure is unavailable,
never permission to fall back to bootstrap users. Reporting itself requires native
durable application storage; a memory-only deployment returns 503.

`ReportingService` owns time scope, authorization, pinned revision labels and
operational completion calculations. `ReportingReader` is its narrow query port;
the Mongo adapter aggregates without returning input, result or credential payloads.
Parallel query/label tasks are drained on failure and cancellation before the
request returns or its resource scope closes.
System metrics count root execution records, including submitting/unknown records,
not conversation sessions or every nested child. Time filters use request start
times and UTC; terminal completion is completed / (completed + failed + cancelled).
No terminal records means an unavailable percentage, not a zero success claim.
Average duration uses completed records with valid finish timestamps.

Owner detail uses `owner_offset` and `owner_limit` (1–100); top owners (8), pinned
Program revisions (10) and latest daily activity (366 UTC days) are bounded. A
truncated timeline has an explicit flag; totals still cover the selected period.
Names come from immutable executed revisions, not current drafts. These are stored,
eventually consistent observations, not refreshed engine state, verified acceptance,
an atomic multi-query snapshot or a capacity-tested analytics warehouse.

The existing dashboard/analytics clients now use these contracts. The old
`mas.statistics` service, Flask statistics routes and duplicate activity table are
retired. This slice does not complete the remaining admin/sharing/template migration.

## Curated resource administration

The existing Repository Management screen now uses native
`/api/administration/resources` routes for curated resource listing, protected
editing, creation, publication, dependency previews, deletion and editor leases.
List pages are limited to 100; the production client explicitly traverses them.
Resource execution defaults survive create/edit/detail state independently of
behavioral configuration; final dispatch still uses normal profile admission.
The normal resource service owns public reads, configuration schemas and personal/
team overlays. There is no second construction pipeline: both custom and curated
saves use `ResourceConfiguration`, installed element schemas and field protection.

Enable `UNIFAI_LIBRARY` and `UNIFAI_EDIT_LOCKS` with durable Mongo and Redis. Curated
mutations require transaction-capable Mongo (replica set/sharded deployment).
Standalone storage returns unavailable, never partial-write fallback. Administrator
authority uses the same application `AdministratorAccess` policy and persisted
directory as reporting; the directory adapter is `outbound.mongo.administrators`.
Human authority remains separate from selected workspace ownership. Bearers,
including bearer-plus-session requests, cannot manage the curated library.

`BuiltinAdministration` owns authorization, loaded-version checks, construction
dependency policy and intended changes through `BuiltinRepository`. The Mongo
adapter owns snapshot transactions and atomic resource/descriptor/overlay writes.
Publication validates a bounded acyclic dependency closure before mutation:
missing references, unsupported categories and inconsistent stored references fail.
Dependencies are published together, and public dependents prevent demotion.
Admin responses carry protected configuration; public projections remove reusable
ciphertext as well as plaintext. Caller-configurable secrets retain isolated overlays.

Mutations require the resource version loaded by the editor. Cooperating admins
also use Redis leases; unavailable or lost leases are not reported as acquisition.
Leases are cooperative UI coordination, not an atomic Redis/Mongo lock. The
transaction validates and writes the complete observed dependency set, including
already-public dependencies. `ResourceRecord.storage_revision` captures the internal
Mongo fence, so a dependency check prepared before a competing publication/demotion
cannot later commit a stale decision. It is distinct from authored resource version
and is absent from public views. A cancelled/uncertain commit requires reloading
actual state rather than blindly resubmitting an unversioned mutation.

The old `BuiltinResourceService`, Flask built-in endpoints and their update DTO are
removed. Sharing's retained cloner receives only its descriptor reader; it does not
construct or depend on the replaced administration service. The field-alias and
secret regression now exercises native overlays. Full AppContainer/old-resource
resolution retirement still depends on the remaining sharing/template migration.
Admin draft-provider probes, remaining credential administration, catalog-wide
concurrent authoring/deletion guarantees, transaction failover/capacity and actual
browser acceptance remain unfinished. See the focused evidence and diagnostic skill.

## Editor action discovery and execution

The native API supports authenticated `GET /api/actions/actions.list` and
`POST /api/actions/action.execute`. Existing UIDs, element form hints and the
camel-case request fields remain compatible. The application service validates
input/output contracts, filters metadata and dispatches registered async instances.
HTTP adapters translate missing actions, invalid input and execution failures
without exposing provider values. Cancellation propagates.

`mas.application.actions` owns contracts, metadata, dispatch and credential use
cases. `outbound.actions` owns MCP/A2A/RAG/Vertex probes and OpenAI configuration
discovery. `bootstrap.actions` explicitly composes these; missing optional external
SDKs omit their adapters. Internal import errors fail startup. There is no global
action registry, capability cache or subclass discovery. The removed `mas.actions`
package has no forwarding alias; these action classes are authoring operations,
not installed graph entrypoints or bundle references. The retained Flask endpoint
adapts the same service through its old bridge until the separate cutover.

Team ownership and credential identity remain separate. Authentication verifies
the selected team and provides the acting human; the service replaces an input
`user_id` with that human before calling a credential/provider action. Never trust
`inputData.user_id`, top-level `userId` or arbitrary context for credential scope.
Retained synchronous credential-store operations execute off-loop under ownership.
Native RAG probes own async HTTP clients per request and pass a per-request human
header; MCP uses async credential binding and A2A returns portable card data.

OpenAI model/reasoning dropdowns use admin configuration, not generation calls.
`UNIFAI_ADMIN_CONFIG_DATABASE` defaults to `config`,
`UNIFAI_ADMIN_CONFIG_COLLECTION` to `admin_config`; its document has key
`openai_model_capabilities` and a `value.capabilities` object. Both actions share
an injected 30-second cache per composition and use longest-prefix model lookup.
`UNIFAI_RAG_BASE_URL` defaults to the existing RAG service; `UNIFAI_HTTP_TIMEOUT`
also bounds these RAG probes. The async Mongo reader borrows the composition's
owned client; legacy composition uses its off-loop reader adapter.

To add an action, implement `BaseAction[Input, Output]` with top-level Pydantic
schemas, stable UID and metadata, async `execute`, and injected dependencies.
Register the instance in composition and preserve any existing form schema hints.
Use the application contract tests and real adapter fixtures rather than a second
dispatcher in tests. [Native action diagnostics](../.cursor/skills/debug-native-actions/SKILL.md)
contains focused tests, strict typing and the full App fixture procedure. This
does not complete share notifications, credential OAuth callbacks or all UI parity.

## Invitation notifications

`mas.domain.sharing` contains shared invitation/status/item/direction values.
`mas.application.sharing.notifications.ShareNotifications` owns list/detail policy
and decline/cancel decisions through its narrow async repository port. Native
Mongo borrows the composition's owned client and configured `UNIFAI_SHARES_COLLECTION`
(default `shares`); memory composition owns independent snapshots. The retained
legacy service uses the same domain models. Native imports do not initialize the
legacy `mas.sharing` package or its synchronous cloner.

Native endpoints preserve existing UI transports:
`GET /api/shares/shares.list`, `GET /api/shares/share.get`,
`POST /api/shares/share.decline` and `POST /api/shares/share.cancel`.
List supports direction, status and bounded skip/limit. Public views keep flattened
sender/recipient IDs and labels, timestamps, expiration and result mappings; the
internal authorized-owner pool stays private. Authentication verifies selected
`teamId`; application policy compares typed owners. Team IDs are exact and occupy
a different identity namespace from users. Team detail/decision clients must send
team scope explicitly. Repeated identical native decisions succeed; competing
pending outcomes return conflict. Stored accepted outcomes cannot be changed by
these native operations.

The reader accepts legacy ISO strings and BSON datetimes, normalizes UTC and sorts
converted creation time with a stable share-ID tie before pagination. No automatic
TTL migration or historical accepted-record deletion is introduced. Native decision
atomicity does not fix concurrent legacy acceptance: create/accept/team-copy and
their authorization, private-field treatment, dependency remapping and partial-copy
recovery remain migration work. They must be completed before default cutover;
the current full App fixture is not proof of complete sharing parity.

`NotificationContext` carries team scope, cancels replaced refreshes and guards
late action/refresh state by workspace identity. The real TypeScript `shares`
suite calls an isolated native API/Mongo fixture. The full App fixture also verifies
personal/team decline, reload and delayed team switching. See
[sharing diagnostics](../.cursor/skills/debug-sharing/SKILL.md) for tests and
boundaries. No external invitation or paid model call is required.

## Package boundaries

Status: the shared agent/domain extraction is implemented in `multi-agent`.
Messages, tool definitions, element-card values, agent steps, tasks, workspaces and
work-plan invariants live in `mas.domain`. Agent strategies, parsing, iteration,
tool execution, approvals, node capabilities and workload services live in
`mas.application`. LLM/tool/retrieval/tool-provider contracts live in
`mas.application.ports`. These packages have enforced inward imports and cold-import
tests that reject plugins, SDK clients and global infrastructure configuration.

Reusable agent strategies, workload services and shared capabilities now cold-import
without graph state. `WorkloadStorage` is an application-owned synchronous state
port; thread/workspace services receive it explicitly and do not construct concrete
storage. `mas.graph.workloads.GraphWorkloadStorage` supplies the graph-backed
implementation. Generic delegation policy filters caller-supplied candidate mappings;
the orchestrator plugin alone interprets finalizer topology.

Graph node integration is explicit in `mas.graph.capabilities`: `GraphWorkloadMixin`
binds workload services and streaming hooks; `GraphMessagingMixin` binds portable
IEM contracts to `mas.graph.messaging.GraphInterMessenger`. The old application
capability namespaces, core messenger factories/utilities, unused memory factory
and workload compatibility methods are removed. Packet/task values remain portable;
workload task threads are not engine child runs. Core interfaces import no graph.
`Channel` is an explicit typed enum for the base graph schema; custom Program state
continues to use validated string names.

Sending copies packets and checks the invocation's sender/adjacent destination,
including after middleware. Only the addressed recipient acknowledges a packet;
routing tests destination acknowledgment and expiry. Read results are detached,
and updates use declared channel writes. This is cooperative graph-local transport,
not an untrusted-code security boundary or a durable message broker. Program-level
waits/messages continue through `ProgramRuntime` and native Run Engine coordination.

Specifications, factories, validation/card contracts, catalog services, category
builders and owned construction now live in `mas.application.elements`. Portable
bundle values live in `mas.domain.element_bundles`. `ElementInstances` indexes
instances within a construction scope, whose lifetime is separate from a chat
session. The application registry has no discovery operation or global singleton;
`bootstrap.elements` composes installed discovery and configured plugin modules.
Discovery reads classes exported by actual modules. Missing optional dependencies
leave adapters unavailable; broken internal imports, incompatible installed SDK
imports and invalid declarations fail startup instead of silently removing plugins.

Current dependency direction (arrows show imports, not execution order):

```text
+----------------------------------------------------------------------+
| UNIFAI                                                               |
|                                                                      |
|  +----------------------------------------------------------------+  |
|  | ADAPTERS + COMPOSITION                                         |  |
|  +----------------------------------------------------------------+  |
|  | HTTP / native receiver / Run Engine / persistence adapters     |  |
|  | Installed plugin discovery and concrete element integrations   |  |
|  +----------------------------------------------------------------+  |
|                               | imports inward                       |
|                               v                                      |
|  +----------------------------------------------------------------+  |
|  | APPLICATION                                                    |  |
|  +----------------------------------------------------------------+  |
|  | Catalog, specification/factory contracts, category builders    |  |
|  | Owned bundle construction and async preparation                |  |
|  | Agent/tool/coding/workload behavior and application ports      |  |
|  +----------------------------------------------------------------+  |
|                               | imports inward                       |
|                               v                                      |
|  +----------------------------------------------------------------+  |
|  | DOMAIN                                                         |  |
|  +----------------------------------------------------------------+  |
|  | Portable bundles, messages, tool definitions and card values   |  |
|  | Tasks, workspaces and pure work-item invariants                |  |
|  +----------------------------------------------------------------+  |
|                                                                      |
+----------------------------------------------------------------------+
```

Program definitions, revisions, composition values and pure binding projection now
live in `mas.domain.programs`. SDK-free placement values live in
`mas.domain.execution_preferences`; shared step metadata and frozen boundary values
live in `mas.domain.metadata` and `mas.domain.models`. Authoring, publication,
registration, repository/runtime ports, graph-context preparation and the existing
blueprint importer live in `mas.application.programs`. The former `mas.programs`
package and `mas.core.execution_preferences` module are removed without forwarding
aliases. Domain imports do not initialize application services, plugins or SDKs;
the cold-import and retired-namespace architecture checks enforce that boundary.
The authoring DTOs reuse the shared strict frozen model rather than defining a
second identical base class. Serialized definition/revision shapes are unchanged.

Execution context, lifecycle records, request identity and safe placement values
now live in `mas.domain.execution`. Submission requests, prepared snapshots,
delivery claims, execution services/ports and the mutable receiver-local context
holder live in `mas.application.execution`. Portable context never imports its
mutable holder. The old execution package and core context module are removed
without aliases. Context requires explicit identity, rejects unknown fields, and
accepts JSON-only tags; missing identity no longer invents an `unknown` owner.
Prepared adapter snapshots stay application-owned rather than becoming domain data.

Further consolidation remains: session/resource services retain their existing
`mas.session`, `mas.resources` and related paths.
Concrete plugins and their schemas/factories remain in `mas.elements` for now.
Further application ownership and plugin thinning/relocation remain required;
Program consolidation does not complete the whole package migration.
The intended complete layout remains:

| Target area | Responsibility |
| --- | --- |
| `lib/mas/domain` | SDK-free values, messages, identity, tasks/workspaces, program/resource contracts, and pure policies/invariants. |
| `lib/mas/application` | Agent execution/strategies, program/session/resource use cases, ports, registry and element-construction services. |
| `adapters/elements` | Registered element plugins: thin node adapters and concrete LLM/tool/provider/retriever/condition integrations, with their schemas, factories, metadata, and SDK translation. OpenShell placement stays in Run Engine. |
| `adapters/inbound`, `adapters/outbound` | HTTP and engine ingress, execution/persistence/identity/interaction transports. |
| `bootstrap` | Install registrations, configure adapters, and inject application ports. |

Domain imports neither application nor adapters. Application imports domain and
its own contracts; it does not import installed element implementations or SDKs.
Adapters depend inward. A reusable agent service receives model/tool/retrieval
ports and returns domain results. Its registered graph node handles graph/IEM
integration and delegates to that behavior. ReAct/iteration/execution code belongs
outside an individual node plugin. Common messages and tool contracts now live
outside `elements/llms/common` and `elements/tools/common`. A test composes the actual
agent/LLM/streaming capabilities without a graph-node adapter to verify the agent
deadline; real registered-node behavior remains covered by saved-session E2E.

Tool argument validation uses the declared JSON Schema directly, without importing
global infrastructure settings. Tool-executor configuration snapshots its validator
list while borrowing the original validator/error-handler objects; deep-copying
ports can clone resource owners. Tool-definition construction validates JSON data
and detaches nested schema values. Workspace round trips restore typed artifacts,
and all convenience accessors read the same stored context. Retry budget checks are
work-item invariants rather than domain-to-service calls.

Keep plugins cohesive and easy to add: implementation, configuration schema,
factory, and registration stay together. Their shared registration/factory ports
and bundle-construction behavior are application-owned. Keep actual typed
resource dependencies; moving directories is not a replacement for building,
validating, and closing their transitive closure. Avoid extra wrapper hierarchies
or a new agent framework solely to obtain the desired folder layout.

Shared extraction removed the unreferenced duplicate agent runner, old parsing shim,
duplicate phase definition, obsolete work-plan service/retry wrapper, unused thread
utility and old standalone workload examples. Active phase/workload behavior remains
in its canonical implementation. No new agent orchestration framework was added.

Extract shared domain/application code first, then thin plugin adapters. Update
current callers and installed references, remove duplicates and superseded code,
and rebuild matched receivers. The fresh platform does not keep older workers,
serialized formats, or forwarding aliases. Test current-source replay and actual
remote delivery after module changes.

## Adding an element

1. Define a Pydantic configuration model. Use typed resource references for element
   dependencies; plain strings are not interpreted as dependencies.
2. Implement the element contract and its factory. The factory receives validated
   configuration, resolved dependency fields, and `ElementBuildContext`.
3. Define an element specification with category, type key, version, schema, factory,
   and declared state reads/writes. Register it in an application-owned catalog.
4. Resolve a bundle with `ElementBundleResolver`. It freezes the complete transitive
   closure and checks construction order and implementation versions.
5. Execute through the receiver. The existing category builders construct each
   dependency once per invocation and release owned resources in reverse order.

Native async elements can implement an async callable directly and compose shared
domain behavior. Keep synchronous and asynchronous callable contracts distinct
when choosing inheritance; changing a synchronous base method into an async method
changes the caller's contract. The deterministic async fixture demonstrates
composition and is verified in both thread and process backends.

The test fixtures demonstrate a node depending on a tool that depends on another
tool. Adding that dependency does not require changes to the graph scheduler.
Factories must clean up resources they allocate internally if they fail before
returning an instance. The construction scope owns successfully returned instances.

An element needing asynchronous metadata/acquisition before dependents can consume
it may implement `ElementPreparation.prepare_element()`. Native bundle construction
registers ownership first, awaits preparation on the invocation loop, then builds
dependents. Failure/cancellation releases owned instances in reverse order; private
configuration errors remain masked. Constructors and factories remain pure where
possible. This hook is not an async bridge for the retained synchronous workflow
builder; the native bundle scope owns the asynchronous path.

### Saved MCP tool resources

The `mcp_proxy` resource requires `provider: "$ref:<provider-rid>"` and `tool_name`.
Its factory creates a thin provider-backed tool adapter. Native preparation uses
the provider's async `get_tools` port and requires one exact matching tool before
constructing dependent agents. Agents bind the actual server schema, description
and access mode. The adapter borrows its provider/tool without closing them.
Missing or duplicate names fail construction explicitly.

The old factory passed an unsupported `mcp_client` argument and could not construct
these resources. Configurations containing only `tool_name` must add the typed
provider reference. Provider-discovered tools and selected resources use the same
MCP transport. Schema validation no longer invokes dynamic model generation or
global infrastructure settings; protocol-level failed tool results remain failures.

Tests use actual MCP client/server SDKs, then saved two-agent, two-turn sessions
through Mongo and thread/process receivers. Editing the saved provider after
publication does not alter the session's pinned snapshot. These tests make no paid
model calls. Remote MCP-agent placement still requires separate verification.

## Adding an application program

This section describes the registered backend implementation mechanism, not a
separate public program category. The [target authoring model](architecture/README.md#installed-implementations-and-configured-programs)
uses one Programs library and lifecycle for visual compositions and configured
registered implementations. Registry descriptors supply configuration/input/output
schemas, and the Programs workspace now configures registered implementations,
saves/reopens drafts and publishes reusable revisions. Full builder convergence
and nested authoring remain open as described above.

Define an installed async function accepting `(runtime, inputs, configuration)`.
`runtime` implements the application-owned `ProgramRuntime` protocol. Register the
function, its configuration schema, and its stable implementation key/version using
`ApplicationRegistry` in the composition root.

Create an `ApplicationDefinition` referring to that registration, save it through
`ProgramService`, and publish a revision. A graph calls it with `ProgramCallStep`.
Declare child targets (pinned revisions or owned bodies) explicitly; the runtime starts those prepared
children through Run Engine instead of importing repositories in coordination code.

`ApplicationRegistration` is the installed backend specification: identity,
configuration/input/output models, metadata and execution entrypoint. It follows
the same extension discipline as Element specifications without inheriting graph
metadata or an Element factory hierarchy. Use cohesive coordinator classes for
related behavior and injected collaborators; keep the installed entrypoint thin.
A dedicated factory is appropriate when coordinator construction/lifetime needs
one, not as a mandatory wrapper around an already registered callable. Dependency
wiring belongs in the composition root, not the registry or portable definition.

Declare `__runengine_contract__` in installed implementation modules and version it
when coordination behavior becomes incompatible with existing histories. Version
the application registration and configuration schema consistently. The platform's
entrypoint and typed-state modules already declare their compatibility contracts.

Use only serializable input/configuration and runtime ports for durable effects and
waits. A future agent orchestration can be added through this mechanism. This
foundation does not implement agent delegation or continuation state machines.

## FastAPI integration

Start the native API from the repository root:

```sh
UNIFAI_HOST='{"runner_type":"local"}' \
UNIFAI_STORAGE=memory \
UNIFAI_INTERACTIONS=disabled \
UNIFAI_AUTHENTICATION=development \
UNIFAI_DEVELOPMENT_USER=alice \
.venv/bin/mas-platform serve --host 127.0.0.1 --port 13457
```

This explicit development configuration uses one Local host and in-memory records.
Local runs do not survive process loss. Multiple HTTP workers require a shared
coordination host; the CLI rejects multiple workers with Local coordination.

`bootstrap.asgi:create_app` is also a Uvicorn factory. Its lifespan composition
root constructs and closes clients on the server event loop, starts execution and
session reconciliation, and stops those observers before closing their dependencies.
Use Mongo storage for persistent records. Settings use the `UNIFAI_` environment
prefix; structured host/profile settings use JSON. Registered application modules
export an `APPLICATION_PROGRAMS` sequence of `ApplicationRegistration` instances.

Session authentication validates the existing signed session cookie and Redis
session, then checks team membership through the identity service when requested.
It requires the same `SECRET_KEY` or `UNIFAI_SECRET_KEY` as the identity service.
Forwarded user headers require the configured internal token. Development identity
is an explicit alternative and requires a configured username.

Tests can provide prebuilt services to `inbound.http_api.app.create_app`, or provide
a lifespan services factory. Protected routers obtain identity and services through
typed FastAPI dependencies.

Native routes cover programs, revisions, executions, results, cancellation,
messages, execution events, child records, sessions, approvals, and stream replay.
Saving a program validates and normalizes its configuration, including schema
defaults. `PUT /api/programs/{id}` accepts `{definition, expected_version,
presentation?}` and returns `{definition, version, presentation}`. Version zero
creates a draft; updates must use the loaded version. Stale writes return 409.
Omitting presentation preserves it; supplied presentation replaces it. Callers
retain the returned definition, including opaque credential references, rather
than reconstructing private values from display masks.

`GET /api/programs` provides owner/type-scoped keyset pagination with `after` and
`limit`. `GET /api/programs/{id}` reads a draft. Published revisions have separate
identities: `POST /api/programs/{id}/revisions` requires `{expected_version}` and
publishes that observed draft snapshot. Retrying an already published source
returns the same revision even after a later draft edit. Unpublished stale sources
conflict. `GET /api/programs/{id}/revisions` pages newest-first with `before`/`limit`;
revision numbers may have gaps after competing Mongo publications. Layout metadata
is not executable definition data and is excluded from published revisions.
Session creation pins a program revision.
Each turn has its own execution identity; retrying the active turn identity does
not append the prompt twice. Concurrent turns return a conflict. Input bindings
project saved session state into public program inputs; output bindings project
public results back into domain state. Arbitrary application results remain in
`last_result` without being mistaken for graph state.

`BlueprintProgramImporter` converts an already resolved blueprint into a graph
program. Keep using `BlueprintResolver` and the existing resource services to apply
visibility, decryption, and caller overlays before conversion. Imported programs
use the complete domain GraphState as their public input/output contract; sessions
can bind all state channels explicitly. The importer preserves existing factories,
typed dependencies, conditions, and step metadata.

To import an existing stored blueprint, install the `blueprints` extra on the API
and set `UNIFAI_LIBRARY=true`. Configure `UNIFAI_MONGO_URI` and
`UNIFAI_MONGO_DATABASE` for the existing library. Collection names default to
`blueprints`, `resources`, `builtin_resource_descriptors`, and
`builtin_user_configs`; override them through `UNIFAI_BLUEPRINTS_COLLECTION`,
`UNIFAI_RESOURCES_COLLECTION`, `UNIFAI_BUILTIN_DESCRIPTORS_COLLECTION`, and
`UNIFAI_BUILTIN_USER_CONFIGS_COLLECTION` when the existing deployment uses
different names. The optional library module is isolated so the native execution
API can still run without loading concrete blueprint/provider schemas.

Send `PUT /api/programs/{program_id}/blueprint` with:

```json
{"blueprint_id": "existing-blueprint-id", "execution_profile": "trusted-worker"}
```

The profile is optional. The caller must own the blueprint; team callers use the
existing authenticated `teamId` query parameter. The service resolves the stored
draft, resource visibility, encrypted configuration, and caller overlays through
the existing BlueprintService, BlueprintResolver, and resource services. Legacy
retired draft fields are tolerated on reads. Normal program save then protects
the resolved configuration and returns the versioned draft envelope. Publish it
through `POST /api/programs/{program_id}/revisions` with that draft's
`expected_version`. This import endpoint creates a program draft; replacing an
existing draft uses the canonical version-fenced program save contract. Earlier
published revisions keep their original configuration.

Use the existing credential encryption key to read encrypted library values.
If resolution produces private inline credentials, also enable configuration
secret storage as described below. Typed SecretStr values are extracted for
protection before serialization can replace them with display masks. The API
owns a shared synchronous library client; legacy service calls and initialization
run off the event loop, and cancellation drains that work before releasing it.
Import itself reads the existing library without changing its source documents.

Native blueprint authoring uses async Mongo operations and Pydantic contracts
built once from the installed element registry during composition. Authoring,
inspection, and import share those same contracts. Register elements before
composition; adding a plugin does not require editing a central category union.
The resource's category and explicit outer `type` select its configuration schema,
even when that schema has no internal type discriminator. Inline entries require
a local `rid`, `name`, `type`, and configuration; external `$ref:` entries resolve
their configuration from the library and cannot also supply inline configuration.
The returned JSON schema includes the installed plugin configurations.

Portable document contracts and application services load without importing vendor
configuration lists. Blueprint import reuses the application authoring ownership
check and shared resolution path; its duplicate synchronous import adapter has
been removed. Existing synchronous resource reads and caller overlays remain
owned off-loop in the resolution adapter. The retained legacy execution/authoring
path keeps its older portable schemas for drain compatibility.

Resource deletion depends on a narrow blueprint-usage reader. Native library
composition borrows only that Mongo lookup rather than constructing the full
legacy blueprint repository. The async authoring repository initializes its own
usage and owner/listing indexes. A cold-process architecture check verifies that
native library composition does not import the fixed vendor configuration unions.

| Route | Behavior |
| --- | --- |
| `GET /api/blueprints/schema` | Installed authoring schema |
| `POST /api/blueprints` | Create from `{ "spec": {...}, "metadata": {...} }` |
| `GET /api/blueprints` | Owner-scoped page with `skip`, `limit`, and `sort_desc` |
| `GET /api/blueprints/{id}` | Read the owner's stored document and version |
| `PUT /api/blueprints/{id}` | Replace `spec`; preserve omitted prompt shortcuts |
| `PATCH /api/blueprints/{id}/metadata` | Merge validated metadata keys |
| `GET/PUT /api/blueprints/{id}/prompt-shortcuts` | Read or set the `prompts` list |
| `DELETE /api/blueprints/{id}` | Delete a source document; published revisions remain |

Updates accept an optional `expected_version`; deletion accepts it as a query
parameter. A mismatch or an intervening edit returns HTTP 409. Writes also compare
the prior specification and metadata, including versionless legacy documents.
Deploy the updated legacy authoring repository during mixed operation: its draft,
metadata, and shortcut writes increment the same version. Older writer binaries
cannot participate fully in client version checks. Duplicate names remain scoped
to the owning user/team and return HTTP 409.

New authoring saves protect declared inline credentials before storage. Existing
legacy drafts can retain their older inline values until saved through this path;
their owner can still read the stored authoring document. Native-authored secret
references require native execution and receiver resolution. Keep legacy drain
workers for their existing runs, and move new execution callers to the native
program/session path. The older authoring raw YAML/form and dotted-route HTTP contracts,
admin behavior, and affected UI migration remain
open. The CLI's `inbound.blueprints.files.BlueprintFileLoader` accepts YAML and
JSON objects. File access belongs to this inbound adapter; installed schema
validation belongs to the application service. The unused broken JSON-only loader,
single-implementation loader base, and old `mas.blueprints.loader` package have
been removed. Import concrete blueprint models from their defining modules;
the models package no longer eagerly re-exports provider-dependent schemas.

### Graph analysis

Graph analysis reuses the same authenticated blueprint resolution as inspection.
The application service owns planning, validation, and fix suggestions; the storage
adapter owns legacy library access and drains blocking work off-loop. Saved
ownership is checked before parsing. Draft references must be visible to the
caller. Analysis does not write authoring data or construct execution clients.

| Route | Behavior |
| --- | --- |
| `GET /api/graph/validation/names` | Installed validator names |
| `POST /api/blueprints/draft/graph-validation` | Analyze `{ "spec": {...}, "validator": optional_name }` |
| `POST /api/blueprints/{id}/graph-validation` | Analyze saved blueprint with `{ "validator": optional_name }` |
| `POST /api/graph/validation/{check}.validate` | Retained raw YAML/JSON request shape |

The native server also exposes the old `names.get` alias. Raw checks are `all`,
`channels`, `dependencies`, `cycles`, `orphans`, and `required_nodes`. All native
routes require authentication. Named analysis returns its report and fixes; full
analysis aggregates the installed checks. Unknown validators, invalid topology,
and analysis limits return 422; missing referenced resources return 404. Unexpected
provider/storage errors use safe application errors. The old Flask routes remain
part of the compatibility/authorization audit until their clients migrate.

Validator providers are explicit, scoped dependencies. Analysis is bounded to
256 steps, 256 path depth, and 1,024 enumerated paths to reject explosive graphs.
Tests apply cycle and required-node fixes to real plans and verify their meaning,
alongside ownership, stored/draft/raw transport parity, redaction, and cancellation.

### Native library resources

With `UNIFAI_LIBRARY=true`, native resource authoring uses asynchronous Mongo
repositories and the installed element registry. Requests contain `config`; responses
retain the existing resource document's `cfg_dict` shape.

| Route | Behavior |
| --- | --- |
| `GET /api/resources/schema/{category}/{type}` | Installed configuration schema |
| `POST /api/resources` | Create a custom resource from `category`, `type`, `name`, `config` |
| `GET /api/resources` | Own custom resources and public built-ins; category/type/ownership filters, offset/limit |
| `GET /api/resources/{rid}` | Read a visible resource |
| `PUT /api/resources/{rid}` | Replace custom configuration and optionally its name |
| `DELETE /api/resources/{rid}` | Delete an unreferenced custom resource |
| `GET /api/resources/{rid}/configuration` | Read the caller's encrypted built-in overlay and version, or null |
| `PATCH /api/resources/{rid}/configuration` | Merge caller-configurable fields from `config` |
| `DELETE /api/resources/{rid}/configuration` | Clear caller-specific fields, retaining the version fence |

Custom updates and overlay patches accept `expected_version`; deletion/reset
accept it as a query parameter. Native writes compare the previous stored values
as well as their versions, including versionless legacy records. Updated legacy
resource and overlay writers advance those same versions. Concurrent native edits
produce one winner and HTTP 409 for stale requests. A cleared overlay keeps an empty
record and increments its version, so an old editor cannot overwrite a newly
configured value after a reset. Built-in reads and overlays separate user and team
identities even when their textual IDs match. An identity named `admin` has no
special authority. Administrative lifecycle operations remain in [the active plan](plan.md#remaining-milestone-order).

Library resources and overlays retain the existing encrypted string format rather
than owner-scoped program secret references: a shared built-in must resolve under
library policy before publication protects the caller's execution snapshot.
Declared SecretStr, SecretHint, and ENCRYPTED_FIELDS values are extracted before
serialization can replace them with display masks. Typed nested models and field
aliases are supported. Native overlay writes reject non-configurable fields;
schema aliases normalize to canonical stored names. Real private values require
the existing encryption key; empty/public schema placeholders remain usable without
one. Reading an existing record does not retroactively migrate its stored values.

Custom responses retain encrypted credentials for editing. Public built-in
responses remove shared private values, including reusable ciphertext, and merge
only the requesting identity's allowed overlay fields. Caller-configurable secrets,
including nested typed credentials, never inherit a shared admin value during
resolution. Declared non-configurable shared credentials may still be used by the
authorized receiver; their values are removed from the public response.

Resource deletion checks current blueprint/resource references. These are authoring
safeguards rather than foreign-key transactions; publication validates the complete
dependency closure. Published revisions retain their resource/configuration snapshots
after deleting the source blueprint and resources. Native resource deletion also
does not remove server credentials merely because no live library resource uses
them: published revisions may still need those credentials. Credential retirement
needs its own reference/retention policy.

Native custom-resource writes and retained administrative descriptor changes are
not yet one atomic cross-collection operation. Administrative promotion, visibility
changes, dependency cascades, and edit locks still require a consistent native
mutation boundary before the legacy API can be retired.

### Resource execution preferences

Nodes and conditions can carry application execution metadata alongside their
element `config`. For example, an agent resource submitted to `POST /api/resources`
can include:

```json
{
  "category": "nodes",
  "type": "custom_agent_node",
  "name": "Researcher",
  "config": {"type": "custom_agent_node", "llm": "$ref:research-model"},
  "execution": {"profile": "isolated-agent"}
}
```

The profile is a deployment-approved identifier; configure its Kubernetes,
OpenShell, process, or thread runner in the platform composition. It does not
select an LLM provider or change the agent's behavior. Tools, LLMs, providers,
retrievers, and tool-level sandboxes are construction dependencies and cannot
select a separate invocation profile through this field.

Updating a resource preserves omitted/null `execution`. Send `"execution": {}`
or `"execution": {"profile": null}` to clear the preference, using the existing
`expected_version` fence. Metadata edits have the same ownership restrictions as
configuration edits. Reads of older resources without the field use no preference.

A blueprint reference inherits its saved resource's preference. An explicit
resource-level `execution` in the blueprint replaces it, including an empty object
to clear it. Inline resources can declare their own preference. Import materializes
the preference into the program's existing element-step or condition-route
`execution` selection. Publication pins that value; editing/deleting the library
resource does not change published revisions. Construction bundles contain only
element configuration and dependencies, without placement metadata.

The effective precedence is an explicit program-step edit, the imported resource
preference, the program default, then the platform default. A step can replace the
imported selection with a profile or an explicit named-environment binding. Named
environments belong to the calling program; resource defaults cannot refer to a
caller-specific environment instance. Existing explicit child imports control
borrowing. Profile approval and environment availability are checked when preparing
execution, before dispatch; saving/publishing a preference does not grant permission
to provision an environment. Matching names do not imply compute reuse across
session turns.

### Resource validation and cards

The native inspection adapter reuses `CoreResourceService`,
`BuiltinAwareResourceService`, `ElementValidationService`, and `ElementCardService`.
It implements an application-owned async port; FastAPI knows neither synchronous
Mongo repositories nor provider validators. Library composition owns the shared
stores and, when credentials are enabled, the existing AuthService. No graph or
engine run is needed for an authoring inspection.

| Route | Behavior |
| --- | --- |
| `POST /api/resources/{rid}/validation` | Validate one saved resource and its dependencies |
| `POST /api/resources/validation` | Validate `resource_ids`, preserving input order |
| `POST /api/resources/configuration/validation` | Validate inline `category`, `type`, `config`, optional `name` |
| `GET /api/resources/{rid}/card` | Build the requested resource card |
| `POST /api/resources/cards` | Build cards for `resource_ids` and their transitive dependencies |

All routes require authentication. Workspace ownership comes from the authenticated
user/team scope; credential lookup uses the logged-in human separately. Inline
validation now passes that scope through dependency resolution too. The retained
`config.validate` route now requires authentication and forwards the same scope.
Callers cannot override credential identity through a request body.

Validation bodies accept `timeout_seconds` (greater than zero and at most 60);
single-resource validation accepts `{}` for defaults. Batch selection is bounded
to 100 roots, with at most ten concurrent probes per request. MCP and A2A probes use
their native async validators and SDK clients directly. Each probe owns its deadline
and drains transport cleanup on timeout or cancellation. Synchronous validators and
legacy library reads run off-loop; cancellation drains them rather than forcibly
terminating Python threads. Batch cancellation reaches started async probes once,
and all started work finishes cleanup before library clients are released.
Empty batches return `[]` or `{}`.

Validation returns one result per root; missing or inaccessible roots/dependencies
produce an invalid result without exposing foreign configuration. Card and inline
configuration requests return HTTP 404 for missing/inaccessible dependencies.
Stored dependency cycles return HTTP 422. The shared library resolver now rejects
missing resources and cycles rather than silently accepting incomplete closure.
Schema errors omit private input, storage failures return HTTP 503, and unexpected
provider/plugin exceptions return a safe inspection failure without exporting SDK
exception details. Shared validation/card services redact declared private
configuration values from diagnostic messages and card content, including nested
models and extra card fields. They preserve resource identifiers, validation codes,
field paths, and model types. Installed plugins still own their public report/card
contracts; arbitrary unmarked provider data is not automatically classified.

Real Mongo tests exercise actual registered validators/card builders, caller
overlays, dependency report propagation, and encrypted human credential lookup
for a team-owned resource. Separate deployed HTTP tests exercise validation and
cards before program publication. Remaining legacy client contracts still require
migration.

### Blueprint validation and cards

The native blueprint inspection application service uses the same validators and
card builders. A narrow source adapter invokes the existing BlueprintResolver and
collector off-loop, preserving library visibility, caller overlays, and typed
configuration. The collector now depends on the resolved blueprint contract and
does not import concrete provider schemas. The inspection service authorizes saved
documents before parsing or resolving them.

| Route | Behavior |
| --- | --- |
| `POST /api/blueprints/{id}/validation` | Validate a saved blueprint's elements; body `{}` uses defaults |
| `POST /api/blueprints/draft/validation` | Validate an unsaved `{ "spec": {...} }` |
| `GET /api/blueprints/{id}/cards` | Build cards for an owned saved blueprint |
| `POST /api/blueprints/draft/cards` | Build cards for an unsaved `{ "spec": {...} }` |

Validation accepts the shared `timeout_seconds` setting. All routes require
authentication; saved reads require owner user/team identity. Credential lookup
retains the logged-in human separately. Configurations normalize through the
installed registry, and construction dependencies are ordered from typed references
before probing. Validation reports missing/inaccessible dependencies as invalid
results. Cards return HTTP 404 for missing dependencies; incompatible categories
produce invalid validation results and HTTP 422 for cards. Duplicate resource IDs
and construction cycles are rejected before provider calls.

Native-authored credentials are opaque owner-scoped references. Inspection resolves
them locally through ConfigurationSecrets and passes hydrated typed models to the
validator/card builder. `resolve_authored` also accepts unsaved literals without
writing secret snapshots; the execution-facing `resolve` contract still rejects
literal private credentials. Inspection does not change blueprint versions or
stored configurations. Tests verify unchanged Mongo documents and secret counts,
and reject a different owner's copied credential reference. Stored legacy fields
are tolerated on reads while new draft input remains strict.

These routes inspect element configuration and construction dependencies. Program
publication continues to validate graph execution contracts; the remaining graph
analysis HTTP endpoints still require migration. Native resource and blueprint
inspection share `ElementValidationService.validate_ordered_async`. MCP/A2A
validators await their SDK transports on the request loop; their synchronous entry
points retain a bridge only for legacy callers. `AuthService.bind_async` owns and
drains synchronous credential-store access off-loop. The logged-in human remains
the credential identity even when the resource belongs to a team.

MCP session/transport contexts unwind in reverse order in the task that entered
them, including failed initialization. A2A closes a partially entered HTTP client
when agent-card discovery fails or is cancelled. A missing, expired, or empty bound
MCP credential produces invalid credentials before opening a transport; it cannot
silently become an anonymous probe. Native reports omit SDK exception details.

The dev extra installs the MCP SDK and HTTP URL support. SDK protocol tests use
the actual MCP server/session and A2A card resolver over in-process HTTPX ASGI
transports. They cover authenticated success, HTTP 401, timeout, cancellation,
client closure, and absence of bridge calls. Separate real-Mongo API tests prove
saved-resource, inline, and saved/draft-blueprint paths with encrypted human
credentials; those tests substitute provider transports. These checks do not claim
live external-provider availability or replace the separate deployment E2E tests.

Native Redis clients use an owned adapter scope across the API, receivers, and
cancellation effects. Closing a Redis client disconnects its sockets; the adapter
also resets its owned, drained pool to release retained closed entries. This keeps
the SDK's metrics-importing pool finalizer out of unrelated Temporal workflow
garbage collection. Closure and pool reset finish together even if owner cleanup
is cancelled. Borrowed Redis clients remain the caller's responsibility.

Tests exercise publication, submission, results, cancellation, authorization, and
server-sent execution observations using the actual local runtime. The legacy
endpoint set and client interaction contracts, legacy schedule migration, durable
worker deployment, and the default container command remain migration work.

## Native program schedules

The Temporal + Mongo composition exposes `/api/program-schedules` through thin
authenticated routers. Local coordination returns 503 for these routes. UnifAI's
schedule service owns authorization, pinned programs, inputs, session bindings,
and finite-run policy; an outbound port uses Temporal's calendar API. Run Engine
owns the generic worker, delivery, traversal, children, cancellation, and environments.
There is no UnifAI polling scheduler.

Create a schedule for an already published revision:

```json
{
  "session": {
    "program": {"program_id": "report", "revision": 1},
    "output_bindings": {"output": {"kind": "path", "path": ["answer"]}}
  },
  "inputs": {"name": "daily report"},
  "schedule": {
    "interval": "P1D",
    "timezone": "UTC",
    "overlap_policy": "skip",
    "enabled": true,
    "remaining_actions": 10
  }
}
```

Use `cron_expression` instead of `interval` for a five-field cron expression.
Intervals must be at least one minute. Naive absolute boundaries mean UTC; aware
boundaries normalize to UTC. The calendar evaluates cron in the specified IANA
timezone and validates its actual calendar semantics. Unknown configuration
fields are rejected. Overlap choices are `skip`, `buffer_one`, and `cancel_other`.

| Route | Behavior |
| --- | --- |
| `POST /api/program-schedules` | Create from the body above; returns 201 |
| `GET /api/program-schedules?limit=100` | Owner-scoped, eventually consistent list |
| `GET /api/program-schedules/{id}` | Definition, version, live status, counters, and next times |
| `PUT /api/program-schedules/{id}` | Replace with `{ "request": {...}, "expected_version": 1 }` |
| `POST /api/program-schedules/{id}/pause` | Pause future automatic actions |
| `POST /api/program-schedules/{id}/resume` | Resume automatic actions with the current budget |
| `POST /api/program-schedules/{id}/trigger` | Queue one manual action; returns 202 |
| `GET /api/program-schedules/{id}/runs?limit=20` | Owner-scoped durable session history |
| `DELETE /api/program-schedules/{id}` | Remove the calendar; existing sessions/results remain |

An optional `Idempotency-Key` on creation identifies an owner-scoped request.
Retrying it recovers the original schedule and credential binding after a lost
reply; a different request with the same key returns 409. Omission creates a new
schedule. Updates use version checks and confirm the actual applied definition
and prepared snapshot. Temporal can acknowledge a queued update before its
scheduler rejects a conflicting token; an RPC acknowledgment alone is insufficient.
The adapter uses the public fenced update RPC and the installed SDK's serializer,
then reads back the result within a bounded deadline. The tested SDK is 1.35.0;
the Temporal extra requires at least 1.35. Re-run the native calendar contracts
when upgrading, including its isolated `_to_proto` serialization boundary.
See the [upstream scheduler implementation](https://github.com/temporalio/temporal/blob/main/service/worker/scheduler/workflow.go)
for queued-update and conflict-processing mechanisms.

Each tick invokes idempotent business admission on the trusted worker, then runs
the pinned graph or application in the same owning engine run. Admission records
the already accepted execution before creating its session, so retries cannot
submit a second root run. Existing staging, factories, bundles, secret references,
state bindings, and result reconciliation remain in use. Publishing a replacement
program revision does not rewrite the calendar snapshot. Explicit program calls
still create children; session/calendar bookkeeping creates no graph child.

### Recurring workflow access consent

An optional schedule `workflow_access` contains `requirements` (the same purpose/
scope/lease declarations as manual invocation) and an aware `expires_at` deadline.
Consent must expire within 30 days of human approval. Creating or replacing that
configuration requires a human principal; bearer-plus-cookie elevation is rejected.
The private Mongo record binds owner, original human/time, exact definition/version,
pinned prepared digest and scopes. Native registration carries an opaque
`authorization_id`. No workflow credential is issued while configuring a calendar.

At actual tick admission, the trusted worker reads the currently applied native
registration and resolves live private consent, including Mongo-clock expiry and
revocation. A mismatched definition/prepared digest/reference is refused before
credential creation. Unused consent metadata from a failed/superseded update cannot
authorize another registration. Original consent metadata survives uncertain
calendar responses and idempotent retries. Request identity distinguishes JSON
booleans, integers and floats; Python equality alone is insufficient.

The API and trusted admission worker share `WorkflowAccessSettings` and
`WorkflowAccessComponents`: matched purpose policies, recoverable issuance,
vault key and private binding. Ordinary element receivers require their source
binding, not the vault key. Operator configuration stays outside portable payloads.
Read-only native observation borrows the SDK RPC facade without owning executors,
workers or environments. The accepted root uses the common application provisioning
port; its `workflow_access_approval.consent_id` identifies the original approval.
Business/session admission remains idempotent and creates no extra graph child.

List/detail views expose matching consent metadata. Human
`DELETE /api/program-schedules/{id}/workflow-access` revokes future admission;
expired/revoked consent denies both application triggering and direct native ticks.
Already admitted roots retain their independent bounded grants; cancel those runs
explicitly when required. Calendar deletion remains owner-authorized even when
optional consent metadata is unavailable. Removing the calendar prevents later
admission without erasing consent audit or completed results.

Installed backend declarations are resolved synchronously after worker preload.
Temporal coordination cannot use `asyncio.to_thread`; operational I/O continues
through invocation ports. The native consent gate exposed and corrected that
unnecessary declaration-resolution bridge. Fresh scheduled entry/admission
contracts are `unifai-scheduled-program-v2` and `unifai-schedule-admission-v2`.
Current thread/process calendar cases cover worker restart during review, replay,
material retirement and refusal of revoked native ticks. Generic event-source
admission is described next. Broader recovery, isolated remote delivery and full
UI controls remain open.

Rapid calendar actions can reuse a Temporal workflow ID within one second. The
generic engine extension binds empty-ID native ingress to a versioned opaque
generation identity. Results, messages, cancellation, events, and replay resolve
that exact generation; child operation identities also include it. Ordinary
RunHost IDs retain their existing interpretation. The environment-owner locator
format remains compatible, and old histories without the patch marker replay
with their original identity behavior.

Manual actions are one-off runs and do not consume the automatic action budget,
including after that budget is exhausted. Editing inputs or metadata preserves
the remaining automatic budget. Changing timing on a completed schedule starts
a new counted series; durable history keeps earlier sessions. Pause/resume and
updates wait for confirmation; unavailable confirmation is a recoverable 503,
and callers should reload rather than assume the mutation was rejected.

Legacy `/schedule.*` routes, `workflow_schedules` documents, and their calendars
still use the retained workers. They are not silently rewritten. Migrating those
records/clients, retaining authoring definitions beyond calendar retention, legacy
quota policy, and deployment drain checks remain in [the active plan](plan.md#remaining-milestone-order).
Native run history lives in Mongo and survives deletion of its calendar.

## Authenticated event-driven Program starts

Enable `UNIFAI_EVENT_SOURCES_ENABLED=true` with Mongo storage to expose the generic
event-start adapter. `ProgramEventService` owns subscription approval and admission
through application-owned ports. `MongoEventSources` stores private registrations;
the HTTP adapter handles transport. `ExecutionService` still owns root submission,
provisioning, delivery claims, uncertain submission and recovery. Run Engine owns
execution and physical environment lifetimes. There is no second event scheduler.

A human registers an immutable source containing a pinned Program revision, event
type, optional additional input schema, requested workflow scopes and expiry of at
most 30 days. Creation prepares the Program without starting work or allocating its
environments. The complete prepared snapshot stays private; source metadata exposes
its digest. Draft/resource changes cannot retarget it. Binding an occurrence replaces
only root input/context/identity, preserving compiled calls, schemas, resources and
placement. Changed/withdrawn profile configuration or work-budget policy refuses new
binding instead of silently adopting new execution settings. Already admitted roots
retain their own frozen preparation and recovery behavior.

| Endpoint | Authority and result |
| --- | --- |
| `POST /api/program-events/sources` | Human owner; creates source and returns its delivery key once, with `Cache-Control: no-store` |
| `GET /api/program-events/sources?after=...&limit=100` | Human owner; bounded, identity-type-scoped metadata page |
| `GET /api/program-events/sources/{id}` | Human owner; metadata without delivery key, hash or raw prepared configuration |
| `GET /api/program-events/sources/{id}/settings` | Human owner; frozen admitted profile catalog and work limits |
| `DELETE /api/program-events/sources/{id}` | Human owner; idempotent, one-way revocation with audit retained |
| `POST /api/program-events/deliveries` | Source bearer; typed event and minimal admission receipt, HTTP 202 |

The source key is purpose-separated from workflow/reviewer/evidence credentials.
The settings response projects only the frozen public profile catalog and work
limits. It does not expose backend configuration or establish current availability;
the pinned Program describes its authored per-call/environment selections.
Only its hash is stored. Losing the creation response does not permit retrieving
that key: inspect owner metadata, revoke the unusable source and explicitly create
a replacement. Source-key rotation/renewal and keyed creation are not implemented.
Source management rejects any supplied bearer even with a valid human cookie.
Event delivery uses its bearer exclusively; a cookie cannot rescue an invalid key.
The receipt contains source/event/execution IDs and submission state, not inputs,
results, private placement or workflow credentials. The human opens that execution
through the existing workbench/API contracts.

Each delivery supplies `event_id`, `event_type` and portable JSON `inputs`. Both
the source's optional schema and the pinned Program's input contract must hold.
Schemas use existing bundled Draft 2020-12 interfaces, without network reference
resolution. Source/type/schema errors are private refusals. Source ID plus event ID
determines the public idempotency key; the normal submission service chooses the
separate private native identity. Concurrent/uncertain redelivery reuses the original
root. Changed input under the same event ID is HTTP 409; another source has its own
namespace. A 202 receipt is not operational completion or verified acceptance.

Workflow access reuses private `WorkflowConsents` and keyed purpose provisioning.
Consent binds the complete source definition and template digest; every occurrence
binds original human/time/scopes to its actual request. Variable event input is not
mistaken for the identical concrete request used by a calendar tick. Mongo's clock
also fences source expiry. Source revocation/expiry refuses later deliveries;
already admitted roots have separate bounded grants and cancellation. These checks
do not provide an atomic stale-attempt fence for external work already in flight.
The context's event provenance is observation metadata, never authorization.

Generic backend and graph Programs use this same path, including nested Programs,
typed operations and Human Review. The Local source remains bound to its owning
Local host; restarting that host cannot recover its environments or silently move
new occurrences elsewhere. Use durable Temporal coordination for the verified
API/worker-restart path. Current tests cover thread/process receivers, source
persistence, concurrent delivery, review, replay and independent material cleanup.
See [event admission evidence](evidence/2026-11-05-event-admission.md).

Owner-scoped source settings also expose a frozen safe placement tree: static graph
calls, declared child relationships, environment imports and Program defaults.
Imported child environment profiles may be unresolved and backend Program calls are
dynamic; this is admitted intent, not a live execution trace. Backend configuration,
resource payloads and credentials are excluded. See [placement evidence](evidence/2026-11-05-frozen-placement.md).

Owners can rotate source credentials with `POST /api/program-events/sources/{id}/credential`,
supplying the `expected_revision` from source settings. The response contains the
new credential once; stale revisions fail. An unconfirmed response requires inspecting
settings and rotating again. Rotation preserves source consent and deduplication but
does not fence a delivery already authenticated. See [rotation evidence](evidence/2026-11-05-event-rotation.md).

This adapter starts roots. Provider-specific signature verification/mapping, event
routing into existing waits, traffic/fairness controls,
remote private delivery and full trigger UI remain separate work. Do not call this
live Jira integration or massive-scale acceptance. Existing authorized review and
runtime-message contracts still own continuation of their particular waits.

The optional Engineering implementation is registered by installing the
`mas_plugins.engineering.program` application module in both API and worker
configuration. Its implementation and repair are declared child Programs;
verification and review use scoped service operation bundles. This is an initial
application slice. Local thread/process API tests exercise the same published
revision independently and within a deterministic delivery graph. The test now
verifies published fixture bytes with automatically provisioned `artifact@1`,
review and verification capabilities and terminal retirement. See
[managed artifact evidence](evidence/2026-11-05-managed-artifacts.md) for the scoped
proof and outstanding coding-agent, remote and recovery acceptance.

Install `mas_plugins.engineering.coding` alongside that module to register
`coding_file_candidate@1`. This backend Program consumes `EngineeringWork` whose
`task` follows `CodingInput` (`prompt`, optional `context` and immutable input files).
Configure coding, artifact-loader, workspace-reader and content-publication bundles,
a relative output `path`, coding `execution` and separate `artifact_execution`.
It loads input/report bytes on artifact placement, invokes coding with inline
files, reads the actual returned workspace on coding placement, and publishes the
bounded content on artifact placement. Loaded hashes/sizes, exported paths and the
published identity must match before it returns an `EngineeringCandidate`.
This is an optional single-file composition, not a new operation category or a
Git requirement. Other candidate Programs can return other verification subjects.

Coding and workspace reads must access the same physical workspace. On isolated
receivers use an approved named environment binding; repeating a profile alone
does not establish shared storage. Repairs attach the previous blob candidate at the
configured output path and check reports under `.unifai/reports/<artifact_id>`.
Original input files are preserved, except that the previous candidate replaces an
original input at the output path. Conflicting report paths and input limits fail
before coding; report lists are not silently truncated. Trusted checks and acceptance
still belong to Engineering and its authorized services.
The native [candidate handoff evidence](evidence/2026-11-05-coding-candidate.md)
uses the real CLI adapter with a protocol executable, operator-private credentials
and Local thread/process receivers. It is not paid-agent, automatic provisioning,
remote placement, or full feature-design/UI acceptance.

### Feature design and approval

Install `mas_plugins.engineering.design` in both API and worker application-module
configuration to register `feature_design@1`. It takes a task and nonempty acceptance
criteria. Its configured designer child takes `DesignWork` and returns a
`DesignProposal` (plan text and optional generic references). The child can be a
published Program or an owned body, through normal registration and contracts.

Each proposal becomes a numbered `DesignRevision` containing the exact request,
criteria and proposal. The normal scoped Human Review operations persist that full
revision as the subject. A rejected decision supplies the previous design and the
recorded reviewer response to the next bounded attempt. Approval returns `approved`;
exhaustion, pending observation and closed review remain explicit unsatisfied
outcomes. A design result cannot substitute a different subject or relabel rejection
as approval. Revision numbers are local to this execution, not Programs library
publication revisions. The durable review occurrence identifies the accepted version.

Install `mas_plugins.engineering.designer` to register `coding_designer@1`, a normal
designer child for coding tasks. Its concrete `CodingDesignWork` contract specializes
generic `DesignWork` / `FeatureRequest` with `CodingInput`, preserving generic task
contracts for other designers. Configure a captured coding-operation bundle, loader,
coding `execution` and separate `artifact_execution`. The shared application-owned
`ProgramFileInputs` loader supplies bounded verified inline files, also used by the
file candidate. Reviewer feedback includes the previous proposal and recorded response;
input bytes are staged rather than duplicated into the prompt's structured context.
The agent's JSON is validated as `DesignProposal`. Invalid proposals fail safely
before review; the designer neither approves work nor produces completion evidence.
Planning instructions do not enforce a read-only filesystem. The [designer checkpoint](evidence/2026-11-07-configurable-designer.md)
records native revision/repair and real OpenShell browser proof, including remaining
pre-approval evidence and authoring gaps.

Install `mas_plugins.engineering.feature` to register `coding_feature@1`. Its input
has a coding prompt, optional context and acceptance criteria. It composes declared
design and Engineering child Programs, checks that the reviewed request matches the
original input, and starts Engineering only after approval. Engineering receives the
approved proposal, revision, criteria and approval ID as structured context alongside
the original task. Oversized combined context fails its input contract; it is not
silently truncated. Unsatisfied design never invokes Engineering.

These are optional ADLC compositions, not new execution kinds or core scheduling
primitives. They use `ProgramRuntime` child calls, scoped effects and native waiting.
Existing publication, environment imports and placement still apply. Normal designer
and Engineering Programs remain independently reusable. No graph state is passed to
generic operations, and the generic platform remains useful outside coding.

Engineering repair feedback now carries check evidence/report references and the
recorded reviewer response, rather than only outcome labels. Its result enforces the
same candidate for verification/review; `verified` requires accepted checks and an
approving human response. Serialized consistency does not itself establish authority:
production execution still obtains decisions and checks through scoped services.

The [design/feature checkpoint](evidence/2026-11-05-feature-design.md) uses real native
HTTP, Mongo/Redis, thread/process review/check/artifact receivers and automatic root
credentials with seeded candidate fixtures. The newer [coding repair checkpoint](evidence/2026-11-05-coding-repair.md)
replaces candidate fixtures with the production CLI adapter and controlled protocol
code generation, independent executable checks and staged repair evidence. The
[production-checker checkpoint](evidence/2026-11-06-engineering-program-checks.md)
adds native and actual-App proof. Complete live acceptance, Temporal recovery and
the broader remote matrix remain on the active plan.

### Workspace input preparation and saved bundles

`CodingInput.files` accepts immutable `ArtifactFile` references or bounded
`InlineFile` content with contained relative paths. Aggregate inline content is
limited to 1 MiB. `CodingOperation` computes its normal isolated/shared
workspace, validates the final prompt, and calls its optional `WorkspacePreparation`
port before invoking the agent. Missing, failed or cancelled preparation cannot
silently proceed to coding. Input paths appear in the prompt without copying report
bytes into the model context. Canonical duplicate destination paths are rejected.

Configure a `providers/artifact_workspace` resource whose `store` references the
normal artifact-store provider, then set the coding resource's
`workspace_preparation` to that provider. Existing dependency discovery/factories
construct the closure. The application preparation service uses artifact-transfer
and workspace-file ports; HTTP/filesystem details stay in adapters. Preparation runs
inside the coding invocation's actual workspace and needs no separate environment
or fabricated graph state. Code/publisher placement and borrowed environment ownership
remain Run Engine responsibilities. This works with fresh isolated repair workspaces;
the file adapter still refuses to overwrite different existing content in shared ones.
Report reads require explicit `verification-reports` access in the root artifact scope.

For credential-free receiving workspaces, configure `providers/inline_workspace`.
It accepts only content values and refuses unresolved references before writing.
The normal `load_artifact_content`, `read_workspace_content` and
`publish_file_content` operations bridge trusted storage access and isolated
workspace work without delivering an artifact-store credential to the producer.
`InlineContent` describes unpublished bytes; it does not imply a storage record.
Its hash/size verification is shared with published inline artifacts. Registered
transfers default to 65,536 bytes and permit at most 1 MiB. Values may be retained
in coordination history; encoding is neither encryption nor secret redaction.
This optional path does not replace streaming artifacts or repository transport.

Human authoring can capture a saved resource for backend configuration with
`POST /api/resources/snapshot`, passing `{ "source": <ResourceSourceRef> }`.
The shared `SavedResourceResolver` checks the selected revision, authorizes and
captures transitive dependencies, rechecks the closure, protects credential fields,
and returns a digest-checked `ElementBundle`. Graph authoring and backend fields
reuse the same construction pipeline. Bearers cannot gain this human authority even
alongside a cookie; team selection uses the authenticated owner scope. This POST can
create private configuration-secret references; it is a selection action, not a
polling/read-preview endpoint. Captures freeze configuration rather than following
later library edits. The UI client is `captureResourceSnapshot`. Backend Program
configuration now uses shared `SchemaValue` fields and a saved-resource capture
adapter for `ElementBundle` fields. `SavedResourcePicker` handles scoped/paginated
catalog selection; graph adoption remains a separate wrapper. Configuration capture
never copies redacted catalog fields, and pending capture locks editing/publication
to avoid applying a response to newer edits. Unmount aborts the request and guards
its completion; this does not undo a server-side capture that already committed.
The existing placement controls render `ExecutionSelection` with approved profiles
and named environments. Local schema references, nested objects, arrays, scalar
fields and optional omission are supported; unresolved, recursive or complex schemas
retain JSON editing. This is presentation assistance, not a JSON Schema validator.
Pinned invocation, explicit capability consent and the shared execution/review route
are integrated. Shared artifact inspection recognizes generic blob references in
inputs, results and review subjects with bounded traversal. Inspection requires
normal owner authorization and exact reference matching; reviewer assignment alone
does not grant another owner's artifact content. Downloads remain attachments.
Explicit text preview is limited to 256 KiB, verifies byte count and SHA-256 before
strict UTF-8 decoding, and renders escaped text. Binary/invalid/oversized content
does not become executable markup. Closing inspection aborts pending preview work.
The [controlled App journey](evidence/2026-11-05-feature-ui.md) verifies design approval,
repair, final review and source/report retrieval after compute deletion. Live-agent,
production verification and complete Engineering authoring acceptance remain open.

Configured plugin modules export `ELEMENT_SPECIFICATIONS`; reflective built-in
discovery alone does not prove that explicit module installation works. Codex now
supports both paths through the normal registry, including identical registration.

## Durable worker and deployment

Run the API and a separate worker with the same `UNIFAI_HOST` endpoint, namespace,
and task queue. The default queue is `unifai-programs-v2`. Superseded worker
entrypoints and queues are not compatibility requirements.

For example, after starting Temporal and the application's storage services:

```sh
UNIFAI_HOST='{"runner_type":"temporal","endpoint":"127.0.0.1:7233","namespace":"default","task_queue":"unifai-programs-v2"}' \
UNIFAI_REDIS_URI=redis://127.0.0.1:6379/0 \
.venv/bin/mas-platform worker
```

Install `mas[api,temporal]` plus the element/provider extras used by published
programs on the API and workers. The development extra includes Temporal support.
Every invocation environment needs the same installed entrypoints, compatible
application modules, and required credentials/configuration. Set
`UNIFAI_APPLICATION_MODULES` to the same installed module list as the API; no extra
HTTP session secret is required merely to run the worker. Settings use JSON for
structured values. SIGTERM/SIGINT stop the worker through its owned SDK lifecycle.

Retained environments require Run Engine's durable ownership store. Choose
`UNIFAI_ENVIRONMENT_SQLITE=/durable/local/path/environments.sqlite` for cooperating
workers on one durable filesystem, or `UNIFAI_ENVIRONMENT_POSTGRES` for a shared
PostgreSQL DSN and install `runengine[postgres]`. These settings are mutually
exclusive. Do not share a SQLite file between hosts or put it on ephemeral storage
when recovery is required. Without a journal, retained environment operations are
unsupported; the worker does not substitute local execution. The generic engine
owns reconciliation and release. Remote borrowing has real Kubernetes/OpenShell
evidence under both hosts; remote worker-loss and journal recovery remain open.

### OpenShell policy configuration

Policies belong to approved execution profiles in deployment configuration. Programs
select a profile through their default, an element's imported preference, or a step
override. A program cannot supply inline OpenShell policy, SDK objects, or a policy
file path through that selection. `UNIFAI_PROFILE_ACCESS` can restrict discovery and
admission by owner; without that policy, all configured profiles are available to
authors. Expose only profiles appropriate for the deployment and owner grants.

For an inline policy, use the OpenShell profile's existing `policy` field in
`UNIFAI_EXECUTION_PROFILES`. For a separately maintained JSON policy, configure:

```sh
export UNIFAI_EXECUTION_PROFILES='{
  "isolated": {
    "runner_type": "openshell",
    "endpoint": "127.0.0.1:8090",
    "image": "unifai-sandbox:release",
    "tls": {
      "ca_path": "/etc/unifai/openshell/ca.crt",
      "cert_path": "/etc/unifai/openshell/client.crt",
      "key_path": "/etc/unifai/openshell/client.key"
    }
  }
}'
export UNIFAI_DEFAULT_EXECUTION_PROFILE=isolated
export UNIFAI_EXECUTION_POLICY_FILES='{"isolated":"/etc/unifai/policies/isolated.json"}'
```

The example paths refer to the dispatcher's gateway certificates; supply your
actual image, gateway address and certificate paths.
The file must be an absolute path on the API process, keyed by an existing OpenShell
profile. Inline and file policies cannot be combined. Startup reads and validates
files off the event loop before opening platform clients, then the compiler retains
an independent snapshot. Restart the API to load file changes for new submissions;
existing execution snapshots and named environments keep their original policy.
File paths do not enter compiled program requests. Workers receive validated portable
policy data, not a policy-file dependency.

[`multi-agent/config/policies/openshell-restricted.json`](../multi-agent/config/policies/openshell-restricted.json)
is an opt-in example for the test sandbox image. Its only network rule allows the
Gemini host on port 443 for the listed Python executables. Adjust the executable
paths and filesystem/process baseline for the selected image. The example explicitly
uses `best_effort` Landlock compatibility; deployments that require refusal when
Landlock cannot apply their policy can select `hard_requirement`, subject to their
gateway/kernel support. See [NVIDIA's policy reference](https://docs.nvidia.com/openshell/latest/reference/policy-schema).

The current Run Engine adapter supports destination **hosts and ports**, scoped by
executable paths. Use `host: "api.example.com"`, not `"https://api.example.com/path"`.
URL schemes, paths, credentials, embedded ports and unknown policy fields are rejected.
Individual URL paths, HTTP methods and richer OpenShell network rules need an engine
adapter extension; they are not enforced by this subset.

A supplied policy replaces the image policy; it does not merge with it. The portable
contract therefore also supports `filesystem_policy`, `landlock`, and `process`.
Retain the settings needed by the image when editing its network rules. Omitted
policy leaves the image policy in effect. A pre-existing `sandbox_id` cannot be paired
with a policy or a policy file: its external owner manages its existing policy.

UnifAI owns profile selection and snapshots; Run Engine translates policy data to
the SDK and OpenShell enforces it. Named environments are created with that snapshot.
Borrowing an environment does not reconfigure its policy. Environment cleanup follows
the existing engine lifetime rules, independent of policy-file ownership. OpenShell
is an execution backend; its retired tool element is not involved.

### Environment ownership and reuse

Environment lifetime is separate from element construction and session state.
Each invocation constructs its own element/dependency instances; a shared compute
environment can retain working files between those invocations.

| Selection | Owner | Release boundary |
| --- | --- | --- |
| Step profile without a named environment | Run Engine invocation | Invocation termination |
| Program-declared named environment | Declaring program execution | Owning execution termination |
| Explicit child environment import | Ancestor owns the environment; child holds a grant | Child releases its grant; owner retains physical cleanup |
| Pre-provisioned OpenShell `sandbox_id` | External deployment | External owner deletes after its work drains |

Declare shared environments in `GraphDefinition.environments` and bind selected
steps through `ExecutionSelection.environment`. Child calls declare imports using
child-alias-to-parent-name mappings. A child does not acquire ownership merely by
using a parent's environment. Run Engine handles declarations, grants, admission,
dispatch, draining, and release. UnifAI translates application selections into
those contracts and records execution state.

For a shorter reuse lifetime, group the relevant steps in a graph program that
owns the named environment and call it as a child. That scope ends before the
parent continues. Lifetime follows explicit program scope, including branches and
child calls. Equal names across separate session turns do not imply compute reuse;
durable artifacts require their own storage contract. Completion, failure, and
cancellation all require owned cleanup; remote worker-loss and active cancellation
validation remain separate gates in [the active plan](plan.md#verification-cadence).

The API persists immutable submission snapshots and application records. Run
Engine owns durable coordination, activity delivery, timers, messages, and native
child identity. Business effects still need application-owned idempotency keys:
delivery retry after worker loss does not imply permission to repeat a business
effect. Completed invocation history is replayed rather than executed again.

Prepared requests and execution records also pin the complete coordinator
configuration by digest, including endpoint, namespace, queue, and delivery
settings. Changing that configuration returns `execution_location_unavailable`
(HTTP 503) for active runs; restoring the original configuration reconnects to
them. This prevents recovery from submitting the same work to another coordinator.
Each Local host has a unique location because identical settings do not restore
its in-memory runs. Persisted terminal results remain readable independently of
the active coordinator. Accepted work whose native observation has disappeared
becomes `unknown` with `execution_observation_unavailable`; it is never submitted
again merely because observation is missing. A later successful observation or
result clears that transient failure.

Root submission also has an application-owned delivery claim. The repository
atomically assigns a private token and expiry when admitting an initial or recovery
attempt. Reconciliation observes an active `starting` attempt without redelivering
it. `UNIFAI_SUBMISSION_TIMEOUT_SECONDS` bounds the original I/O (default 30 seconds);
its claim expires five seconds later so a crashed owner can be recovered. Finishing
an attempt is fenced by its token: an expired owner's late reply/refusal cannot
overwrite the newer owner. Recovery always uses the identical stored request and
private native ID. A genuine first-start collision remains refused. This claim
protects application delivery, not worker scheduling or environment ownership.

Cancellation first records durable `cancel_requested` intent after validating
ownership/location. It does not claim native cancellation has finished. A request
arriving before native acceptance is applied once admission becomes observable,
and stale submission/projection updates cannot erase it. The original submission
path and background reconciliation both use the existing engine cancellation port.
Wrong-location requests fail before changing cancellation intent. This preserves
the original coordinator boundary rather than starting work on a replacement host.

Active records without a stored location are rejected. Prototype formats and old
workers are not compatibility requirements under the fresh-platform decision;
cleanup of currently owned resources remains required.

`GET /api/executions/{id}/children` returns application records for direct children.
Projection reads accepted native child requests and preserves bound inputs,
revision identity, ownership, root correlation, and session identity. Children do
not create new chat sessions. Terminal parent projection completes before its
record is finalized; terminal child results remain readable from Mongo after the
original Local host closes. Local requests still depend on bounded in-process
retention until projected; Local execution does not provide crash durability.

Child cancellation through HTTP or `ChildExecution.cancel()` notifies application
waits for that subtree and then requests native cancellation. Ancestor fences
release grandchild approvals without cancelling sibling work. Program-side
notification uses an ordinary invoked effect and therefore consumes an invocation
from the run's configured budget. Approval request IDs must be unique within the
root execution; distinct requests cannot reuse the same ID with different payloads.

## Human Review

Status: the `human_review@1` application program, registered review effects,
Mongo-backed decisions, scoped workflow access, native HTTP routes and actual
reviewer UI are implemented. Local graph/code/thread/process execution and
Temporal API/worker restart with native replay have focused evidence. The broader
milestone is recorded through [the evidence index](evidence/README.md). Visual program-block authoring,
parallel/repeated occurrence coverage and retained remote environments remain
acceptance work; this does not introduce an agent delegation framework.

Run Engine has two relevant capabilities:

- A graph node marked `interrupt=True` pauses **before** its invocation. The engine
  checkpoints traversal, publishes a suspended snapshot, receives the graph's
  resume message, applies its field updates, and then executes the node. This is a
  graph control mechanism; a resume payload is not a validated human decision.
- An application program can await a named message with a timeout through
  `ProgramRuntime.receive`. The existing adapter delegates this to engine
  coordination. Temporal supplies durable waiting/replay; Local waiting is
  in-memory. Neither requires keeping an invocation worker open for the wait.

References in the companion checkout:
`src/runengine/programs/graph/program.py` (`GraphProgram._interrupt`),
`src/runengine/programs/graph/handle.py` (`GraphHandle.resume`), and
`src/runengine/programs/graph/traversal/README.md` describe the pre-node boundary.
UnifAI's current compiler does not set interrupt flags. Existing receiver-side
tool approvals use a separate receiver-side gate and Redis tickets; those tests
do not prove durable Human Review.

**Application representation.** The feature is **Human Review**, implemented as one
registered, versioned application program. It uses the existing `ProgramCallStep` so
it appears as a reusable graph step and can also run independently or be called
by another application. This explicit program call creates a child execution;
reviewing an ordinary element does not otherwise require a child. A palette item
can present this as a review node without creating a second element registry,
step executor, or new step kind. Keep ordinary element factories and builders for
the invoked effects they construct; do not turn `BaseNode.run` into a durable
coordination API or let it reach into engine operations.

**Configuration and result.** Publish immutable review configuration: prompt,
allowed decisions, validated expected response fields, timeout, and permitted
timeout behavior. Begin with one reviewer response, explicit approve/reject
decisions, and optional structured feedback; do not add quorum/escalation systems
speculatively. JSON Schema describes configurable response data; Pydantic validates
the stable configuration and submission envelope. Reject invalid schemas at
publication and invalid responses before accepting a decision. Revalidate portable
data at the coordination boundary. Return a typed outcome and validated response;
existing output bindings and conditions route the graph to continue, revise, or
stop. Receiving a message alone must not mean approval. Existing tool auto-approval
rules must not silently approve graph reviews.

**Responsibilities and boundaries.** UnifAI owns request/response validation,
reviewer authorization, the pending request, atomic decision acceptance, responder
identity, and the audit result. Thin FastAPI routes call that application service.
Use a review-specific request model rather than filling the tool approval model's
required tool fields with fictitious values. Reuse execution authorization,
identity, interaction observation, and persistence conventions where their
semantics fit. Add only the narrow review persistence/effect port required by
this use case. The coordinator opens and inspects requests through invoked effects
at the existing runtime boundary. The API and owned reconciler persist lifecycle
changes and deliver notifications through application-owned ports. The application
coordinator itself performs no direct database, Redis, HTTP, or wall-clock I/O.
It uses engine messages/timers for waiting and expiry. Engine SDK objects remain
in adapters; no second scheduler or custom durability layer belongs in UnifAI.

**Reliable submission.** Correlate each request with its actual execution, step,
and review occurrence; retries reuse that identity, later loop visits do not.
Persist decisions durably and accept them atomically. An identical retry returns
the original acceptance; conflicting, expired, cancelled, or superseded responses
cannot change it. Delivery to the exact waiting review execution is a wake-up,
not the source of truth: reconcile the persisted accepted response through invoked
effects after an ambiguous send or worker/API restart. Engine-controlled bounded
waits can trigger reconciliation; invalid or stale wake-ups must not reset the
overall deadline. Protect internal review messages from the general public message
route, and verify the request/response correlation in the coordinator. Do not claim
the existing Redis ticket retention is a durable review audit.

**Lifetime.** Waiting does not occupy an element worker, Kubernetes pod, or
OpenShell invocation merely to receive a decision. Intentionally retained parent
environments still follow their declared engine ownership; a review does not
silently destroy them. Scope cancellation and expiry close pending reviews and
prevent late submissions from resuming the flow. An ordinary pause of an arbitrary
node can later expose the engine's pre-node interrupt separately; do not conflate
that low-level control with this business review program.

**Acceptance cases.** Reuse shared program/session fixtures and saved-resource
authoring helpers. Verify saved, published review definitions and node/program
references, source edits after publication, nested graph calls, correct outcome
bindings, custom response validation, rejection, timeout, unauthorized reviewers,
parallel/repeated review occurrences, identical/conflicting submissions, stale
messages, parent/child cancellation, API restart, worker restart during the wait,
and replay. Prove no element invocation stays occupied during the wait. Test
application policy with port doubles, adapters against real persistence, and the
complete HTTP/Temporal path with the independent Docker infrastructure. Existing
tool HITL behavior remains covered separately. Record remote-agent placement and
environment-retention results only after running those cases.

### Current contracts and setup

Enable `UNIFAI_REVIEWS_ENABLED=true` with Mongo storage. Configure
`UNIFAI_REVIEW_POLICIES` as a mapping of policy IDs to admitted owners, assigned
human user IDs in `reviewers`, and `max_timeout_seconds`. Include
`mas.application.reviews.program` in `UNIFAI_APPLICATION_MODULES` and
`mas_plugins.reviews.specification` in `UNIFAI_ELEMENT_MODULES`. Registration uses
the existing application registry and element discovery; no dedicated review
worker or compiler branch exists.

The ordinary `review_service` provider supports `open_human_review`,
`inspect_human_review` and `close_human_review` operations. Factories and transitive
dependency bundles construct them. `HumanReviewConfig` freezes a policy, prompt,
allowed decisions, response schema/deadline, opener/inspection bundles, execution
selection and bounded reconciliation cadence. Its subject is the exact portable
JSON input passed to that program. Graph bindings choose its input shape; there
is no automatic artifact or Git interpretation.

Response schemas use the bounded, self-contained JSON Schema draft 2020-12
subset enforced by `ReviewSchema`. Local references are validated, including their
targets. External references, resource `$id` scopes and regular-expression
validation are rejected. The stable submission envelope is Pydantic-owned. The UI
renders simple string/number/boolean/enum fields and uses JSON input for complex
schemas; server validation remains authoritative.

| Route | Authority and behavior |
| --- | --- |
| `POST /api/review-access` | Authenticated human issues scoped access; optional configured Idempotency-Key recovers the same issuance |
| `GET /api/review-access/self` | Workflow credential metadata, without secret material |
| `DELETE /api/review-access/{id}` | Authenticated owner revokes workflow access |
| `POST /api/reviews` | Scoped workflow capability opens an occurrence bound to its actual active execution/root |
| `GET /api/reviews/inbox` | Assigned human's cursor-paginated inbox across owners; selected workspace does not grant reviewer authority |
| `GET /api/executions/{root}/reviews` | Human owner's paginated root review inspection; bearer credentials cannot use it and ownership never grants decision authority |
| `GET /api/reviews/{id}` | Authorized owner/workflow read or assigned reviewer read |
| `POST /api/reviews/{id}/responses` | Assigned human session only; stable key, expected revision, decision and schema-validated data |
| `POST /api/reviews/{id}/close` | Authorized owner/workflow cancels or supersedes the occurrence |

Workflow bearer credentials cannot submit decisions, including alongside a human
cookie. Assignment is frozen when the occurrence opens; ownership alone does not
permit a human response. Access is purpose-separated from artifact/verification
credentials. Operator-only `UNIFAI_REVIEW_ENDPOINT` and
`UNIFAI_REVIEW_ACCESS_DIRECTORY` bind workers to private mode-0600 capability files
named by `review_credential_key(owner, root)`. HTTPS is required unless the operator
explicitly enables insecure transport; the test harness uses loopback only.
Endpoint and private directory settings are not authored program data. Effective
workflow authority follows actual root liveness. Opt-in bounded same-token renewal
uses the existing reconciler, as described above. Automatic provisioning, rotation
and managed-secret retirement remain part of the credential-lifecycle milestone;
operator-owned private credential files are not deleted by authentication.

Decision acceptance and notification intent commit together through Mongo CAS.
The reconciler sends only an occurrence wakeup to the exact review execution;
the coordinator ignores message data and invokes inspection for its authoritative
result. Its finite runtime receive timeout also recovers lost notifications.
Pending records expire or cancel when their execution/root becomes inactive.
Decided records retain their original human response. A bounded check limit returns
`check_limit` with a pending review; it never invents an approval.

Temporal message admission requires a live workflow worker to acknowledge an
Update. The API-owned reconciler is cancelled and drained during shutdown rather
than waiting for that acknowledgement; its persisted delivery intent survives.
This is application task ownership, not a replacement scheduler. Local-host waits
remain in-memory and do not promise restart durability.

The actual App exposes `/reviews` and `/reviews/{id}` through its sidebar. It
refreshes authoritative snapshots, preserves response identity after uncertain
submission, prevents older revisions replacing a newer accepted decision, and
aborts old requests on selection/workspace changes. Approval is distinct from
notification delivery; the screen can show a saved decision whose workflow
notification is still pending. The current screen does not grant artifact access
to reviewers or implement visual review-block authoring.

## Receiver services and interactions

The default interaction backend is Redis. Set `UNIFAI_REDIS_URI` on the API and
every invocation worker to the same service. Set `UNIFAI_INTERACTIONS=disabled`
for development that does not require streaming or human approval. A node configured
to require approval fails if no gate/policy is available. Native approval requests
await the shared async gate. Legacy channel/store adapters isolate unavoidable
blocking calls inside their adapter and drain them before releasing resources.

Execution interaction routes are:

- `GET /api/executions/{id}/approvals` lists pending requests.
- `POST /api/executions/{id}/approvals/{request_id}` submits a decision.
- `GET` / `PUT /api/executions/{id}/approval-rules` reads or replaces execution rules.
- `GET /api/executions/{id}/stream?after=0-0` replays application events over SSE.

The SSE `id` is the resume cursor. A cursor outside retained history receives a
conflict before streaming, or an explicit error event if retention advances after
headers have been sent. Root streams aggregate child events while retaining each
actual child execution identity. `UNIFAI_INTERACTION_TTL` controls retention and
must exceed `UNIFAI_APPROVAL_TIMEOUT`. `UNIFAI_MAX_STREAM_EVENTS` and
`UNIFAI_STREAM_BUFFER_CAPACITY` bound retained history and receiver buffering.
Transport failure and overflow are explicit failures. Approval submissions are
atomic and replayable; conflicting decisions and late responses are rejected.

The UI session routes add persistent defaults:

- `GET /api/sessions/session.approval.rules?sessionId=...` reads session rules.
- `POST /api/sessions/session.approval.rule` applies a scoped command with
  `sessionId`, `executionId`, `action`, and optional `nodeUid`/`toolName`.
- `POST /api/sessions/session.approval` requires both the originating root
  `executionId` and `requestId`; an old turn cannot resolve a new turn's ticket.

Rule commands use session optimistic concurrency and update defaults used by later
turns. After saving, the service publishes the rules to the current root's Redis
copy. A monotonically increasing session-policy revision prevents delayed older
publications from replacing newer rules. The existing session reconciler retries
missed publication; a retryable `approval_rules_sync_pending` error means persistence
succeeded but live synchronization was not confirmed. This is an explicit
two-store boundary, not a cross-store transaction. Reconciliation can restore a
lost cache from the durable session default. Cached execution-only overrides have
the interaction retention lifetime; they are not independently durable.

The canonical execution `PUT` remains a full execution-only replacement. It
preserves the session revision fence, so repeated publication of that same session
revision leaves it intact; a newer session policy command replaces it. A saved
rule governs later requests and does not resolve an already pending ticket. The
UI saves the rule and separately submits the captured current decision. It reports
those operations independently and keeps entered feedback after a failed decision.

Enable existing stored credentials with `UNIFAI_CREDENTIALS=mongo` on the API and
invocation workers. Configure `UNIFAI_MONGO_URI`, `UNIFAI_MONGO_DATABASE`, and
`UNIFAI_CREDENTIAL_ENCRYPTION_KEY` consistently with the existing credential store.
The optional `credentials` package extra supplies the runtime dependencies and is
included in `dev` and `all`. Credentials default to disabled for deterministic
local development. This wires runtime lookup and refresh; native credential
onboarding/callback HTTP routes are still part of the remaining API migration.

The receiver owns a scoped Mongo client shared by the existing credential and
server-config adapters. The application service depends on their ports; storage
calls remain off the event loop. Team ownership does not select team credentials:
the execution context supplies the initiating human's credential identity.
Registered AuthService credentials and live clients stay outside bundles and
prepared requests.

For existing inline configuration credentials, enable
`UNIFAI_CONFIGURATION_SECRETS=true` and configure the Mongo connection and
`UNIFAI_CREDENTIAL_ENCRYPTION_KEY` on the API and invocation workers. This is
independent of `UNIFAI_CREDENTIALS=mongo`: one handles authored configuration
values, while the other provides runtime AuthService credential lookup.
Fields declared with `SecretHint`, `ENCRYPTED_FIELDS`, or `SecretStr` are replaced
at save time with owner-scoped `unifai-secret:v1:<id>` references. Their immutable
values are encrypted in `program_configuration_secrets`; published revisions,
element bundles, prepared requests, and Temporal histories carry references.
Construction resolves those references inside the receiving environment before
calling the existing factories. Application-program configurations can contain
element bundles using the same protection path. Aliased schema fields and nested
models in enum-keyed mappings retain their canonical configuration shape.

The reference prefix is reserved. A different owner cannot reuse a reference.
Secret storage must be enabled for nonempty private values; empty fields and
public schema defaults such as a mock's `EMPTY` key remain usable without it.
Schemas must identify credentials explicitly; arbitrary provider dictionaries
do not infer sensitivity from their keys. Marked string fields must accept the
opaque reference format in their portable configuration. Receiver-side validation
also checks the resolved value before construction.

Keep the encryption key and immutable values available for the lifetime of their
revisions, snapshots, and durable histories. Automatic deletion and key rotation
are not implemented. A failed or uncertain save can leave an unreferenced secret
snapshot; deleting it automatically could break a save that actually committed.
Any operational cleanup must first establish that no retained revision or run
uses the reference. Existing native-preview drafts with literal private values
must be saved again through the protected path before publication or execution.

Failures from a protected element and its dependents publish a generic message
and preserve their failure category rather than returning provider exception
details containing credentials. This protects declared configuration fields; it
does not redact arbitrary values intentionally emitted as application outputs.

An installed custom module may supply
`element_runtime(holder) -> AsyncContextManager[ElementRuntime]` through
`UNIFAI_RECEIVER_MODULE`. Its build context must use that same execution holder.
The receiver closes after elements and their dependencies, runtime unbinding,
stream draining, and tracing flush.

### Native tracing

Install `mas[telemetry]` in every receiving environment and configure its local
deployment secrets:

```sh
export UNIFAI_TRACING=langfuse
export UNIFAI_LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
export UNIFAI_LANGFUSE_PUBLIC_KEY=your-public-key
export UNIFAI_LANGFUSE_SECRET_KEY=your-secret-key
export UNIFAI_TRACING_TIMEOUT=5
```

Tracing defaults to `disabled`. Selecting it also selects the built-in receiver,
even when credentials and interactions are disabled. Configuration stays in the
receiving process; keys are absent from bundles, revisions, execution snapshots,
and workflow histories. Configure process/container workers independently with
the same deployment secrets. The test receiver image includes the optional extra.

The existing application-owned `TracingService` remains the instrumentation port.
The native adapter exports its observations through Langfuse's documented
[OTLP HTTP endpoint and attribute mapping](https://langfuse.com/integrations/native/opentelemetry).
It owns a private OpenTelemetry provider, batch processor, and exporter for each
invocation. This differs from the retained Langfuse SDK adapter, whose resources
are shared by public key within a process. Independent ownership allows one
receiver to close without disabling concurrent receivers or later invocations.
The adapter installs no global provider and creates no client in workflow code.

Session trace IDs preserve the existing SHA-256 session correlation. Each receiver
opens its own root observation; nested node, LLM, tool, and iteration observations
inherit session/user metadata and actual execution, root, and parent identities.
Closing an invocation flushes and shuts down its exporter off the receiver loop,
including cancellation during acquisition or export. The export deadline bounds
collector retries. An unavailable collector is an observability failure and does
not turn a completed application effect into a retryable execution failure.
Exception classification is exported without raw exception messages or stack events;
Pydantic private values remain masked. Explicit application inputs/outputs sent to
the tracing port remain trace content.

Real API/worker deployment tests exercise concurrent composition in thread and
process receivers under Local and Temporal coordination, including replay. They
decode actual authenticated OTLP protobuf HTTP requests at an owned local endpoint.
That endpoint verifies transport and mapped fields; it does not verify a live
Langfuse deployment's persistence, aggregation, or UI. Legacy session-cost HTTP
compatibility remains part of the remaining API migration.
### Receiver-local deployment settings

Set `UNIFAI_SECRETS_DIR` to an existing absolute directory in the receiving
environment. The shared settings source uses Pydantic's file-secret loader;
files use their environment-variable names, such as `UNIFAI_LANGFUSE_PUBLIC_KEY`,
`UNIFAI_LANGFUSE_SECRET_KEY`, `UNIFAI_MONGO_URI`, or
`UNIFAI_CREDENTIAL_ENCRYPTION_KEY`. Nonsecret settings such as `UNIFAI_TRACING`
and the collector URL may be provided there too. Keep deployment files private.
Selecting an unavailable directory fails explicitly. Each invocation reads current
files; live clients retain their configuration for their owned lifetime.

Explicit constructor values, environment, and dotenv values retain their normal
precedence over file secrets. An explicit Pydantic `_secrets_dir` argument selects
that source instead of the environment selector. Empty environment placeholders
still override files. Receiver, worker, API, scheduled admission, and cancellation
effects share this source. Invocation-side reads run off-loop; configuration
failures are classified as private, nonretryable infrastructure failures.

Native platform validation rejects declared private settings and their aliases in
profile `env` maps, which are serialized execution configuration. The file directory,
secret object name, and existing sandbox identity are portable references; key
contents stay in the deployed environment. This check covers declared private
platform/receiver fields, rather than inferring sensitivity from arbitrary names.

Kubernetes can use Run Engine's existing `secret_mounts`, for example:

```json
{
  "runner_type": "k8s",
  "image": "registry.example.com/unifai/receiver:version",
  "namespace": "unifai",
  "env": {"UNIFAI_SECRETS_DIR": "/var/run/unifai-settings"},
  "secret_mounts": [{"secret_name": "receiver-settings", "mount_path": "/var/run/unifai-settings"}]
}
```

The deployment owns that Secret. When only remote receivers need these services,
select `UNIFAI_RECEIVER_MODULE=bootstrap.receiver` on the API so compilation emits
the installed receiver entrypoint; local API settings need not contain remote keys.
Configure API-side services separately when they are needed.

For the pinned OpenShell integration, a deployment can provision private files
outside execution and select the existing `sandbox_id` mode, with
`UNIFAI_SECRETS_DIR` pointing to those files. The external owner keeps that sandbox
alive and deletes it after its work has drained. UnifAI adds no sandbox or secret
manager. Automatic file provisioning for managed OpenShell environments remains a
deployment capability gap; do not replace it with plaintext keys in profiles or
images. The deployment tests provision their own sandbox through the authenticated
SDK and send synthetic settings over stdin before any program starts.

## Verification limits

The [test layout](../multi-agent/tests/README.md) follows the same boundaries as the
application. Application tests run without an engine, HTTP server, or database.
Integration tests extend that composition with actual adapters. Reusable fixtures
live in support modules and avoid process-global resource tracking.

The default tests require no real LLM, MongoDB, Temporal service, Kubernetes cluster,
or OpenShell gateway. Enable the real Mongo contracts with
`UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27017`; the fixture creates and removes a
uniquely named test database. Those tests verify persistence and application restart
with completed results, plus encrypted credentials in actual thread/process receivers.
Stored blueprint contracts also resolve transitive catalog dependencies and user
or team overlays before native thread/process session execution. They reject
foreign resources, unowned blueprints, missing dependencies, and draft built-ins.
Set `UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6379/0` for real interaction tests;
they remove their unique execution keys afterward. Set
`UNIFAI_TEST_TEMPORAL_ENDPOINT=127.0.0.1:7233` for real composition, replay, native
worker crash/replacement, and message recovery. The API-restart contract also
requires Mongo. Queues and execution identities are unique to each test. These
checks also verify encrypted configuration snapshots and failure records and
assert that Temporal histories contain no tested plaintext credential on success
or failure, followed by replay of those histories. The API restart test rejects
coordinator drift before reconnecting through the original settings. These
checks do not establish remote backend cleanup, environment borrowing, scheduling,
or complete legacy HTTP compatibility. The separately selected remote deployment
suite verifies the backend cleanup/lifetime cases described below; remaining
contracts stay in [the active plan](plan.md#remaining-milestone-order).

With all three test services configured, `integration/deployment` starts a real
loopback HTTP process using the production ASGI factory and a separate native
worker. It uses a signed cookie backed by actual Redis identity data, creates an
encrypted LLM resource and a dependent node through the native API, validates
the node and builds its card, authors and inspects a
referenced blueprint, imports/publishes a program, executes a session,
reads events, restarts the API, resumes durable work through messages, and cancels
another run. It verifies thread/process targets, history replay, retained results,
credential absence in tested storage/logs, and graceful process shutdown. The
listening socket is inherited to avoid a port-allocation race; these process tests
use POSIX descriptor passing. Shared process support signals and reaps only the
processes it created.

The [independent infrastructure guide](../multi-agent/tests/infra/README.md) creates
UnifAI's own Mongo/Redis/Temporal services, kind cluster, receiver images, and mTLS
OpenShell gateway. Remote deployment scenarios run the same public API with Local
or Temporal coordination and Kubernetes or OpenShell invocations. They verify
transitive factory construction, three distinct invocation environments versus one
retained environment, graph/application/graph ancestry, failure cleanup, and
Temporal replay. Explicit graph children also borrow a parent's named environment
while the parent continues using the same physical receiver; owner completion
releases it. Shared files prove workspace continuity. A child-owned scope releases
its physical environment before a waiting parent continues. Receiver-local settings
cases use actual authenticated OTLP traffic while checking key absence from records
and history. The full matrix passed 28 cases across both backends/hosts. Replay
uses the actual namespace and installed module preload.
These cases do not yet establish remote approval transport, network-policy
enforcement, or worker-loss recovery.

### Coding agents and Codex CLI

`operations/codex_coding` is the production typed coding operation. Its outer
plugin lives at `multi-agent/plugins/mas_plugins/coding/codex`: configuration,
identifier, specification/factory, and CLI adapter. `bootstrap.elements` installs
`CodexSpec` into the existing element registry. Bundles, resource secrets,
construction factories, category builders, and receiver ownership are shared
with other registered operations. The former Codex node implementation is deleted.

The application owns `CodingAgent`, `CodingInput`, `CodingOutcome` and
`CodingOperation`. The operation translates explicit work into a coding request;
the provider adapter owns the subprocess protocol. No application coding module
imports graph state, provider SDKs, transport adapters or Run Engine. Graphs
project inputs/results through `OperationStep` bindings. Custom programs invoke
the identical operation through `ProgramRuntime`.

The element configuration requires an explicit `model`; an optional protected `api_key`
selects resource-owned credentials.
`instructions`, `workspace`, reasoning effort, timeout, command count and output
byte limits are configurable. Credentials use the same resource encryption and
opaque published configuration references as other elements. The receiver resolves
them locally through its configured secret store. Alternatively, an operator can
provision a private file and set the receiver-only `UNIFAI_CODEX_API_KEY_FILE`
path. The adapter reads that file when the resource has no `api_key`; authors
cannot select its path through resource configuration. Missing credentials fail
before the CLI starts. Live Kubernetes tests use a private Secret mount; live
OpenShell tests provision this operator file through the authenticated fixture.
Native Mongo egress was unreachable on the pinned 0.0.103 OpenShell runtime, and a policy
allow-list alone did not establish database transport. Never put API keys in image
layers, execution profiles, program inputs or ordinary workflow state.

Placement is selected by the containing program step. Select an approved profile
for one invocation, or use `execution.environment = "coding"` and
`graph.environments = {"coding": "approved-codex-profile"}` to share an environment
between sequential coding steps. Program children use the existing explicit
environment imports. The element creates no sandbox, worker, child engine or child
program. The environment owner controls retention and deletion.

The receiver-local `UNIFAI_WORKSPACE_ROOT` defaults to `/tmp/unifai-workspaces`.
Within it, the root execution identity selects a hashed namespace.
`workspace_mode=isolated` (default) additionally scopes the directory by execution
identity and stable invocation key: concurrent calls and child executions use
separate directories while retries of the same logical call find the same one.
`workspace_mode=shared` explicitly selects the root namespace plus configured
workspace name, allowing sequential steps/children to share files in one retained
or imported environment. Sharing files does not coordinate simultaneous edits;
parallel independent work should use the default isolation. The typed outcome
includes the receiver-relative workspace binding, not a durable artifact reference.
These files belong to the execution environment, not durable artifact storage.
Local thread placement leaves files on the operator's worker; choose a disposable
remote environment when its destruction should remove the workspace.

Each invocation starts a fresh noninteractive `codex exec --json --ephemeral` turn.
Explicit input bindings carry the previous answer; files carry repository changes.
CLI chat-thread resumption is not implemented. The CLI defaults to workspace-write permissions and noninteractive approval
handling; it does not wait on a terminal. An operator may set receiver-only
`UNIFAI_CODEX_SANDBOX_MODE=danger-full-access` for a profile whose external
isolation already provides the required boundary. This is not an element
configuration field, and there is no automatic fallback. The tested OpenShell
host disallows nested unprivileged user namespaces, so its live fixture explicitly
uses that operator setting while retaining the OpenShell filesystem and egress
policy. The Kubernetes live fixture also explicitly selects container isolation;
it does not certify the nested CLI sandbox or enforce an egress-denying policy.
Ordinary profiles keep the CLI workspace sandbox by default.
A private, temporary `CODEX_HOME` is removed after success, failure or cancellation.
Only the Codex process receives its API key. Its generated shell commands use an
empty inherited environment, and raw events/diagnostics are not persisted. The
adapter strips the exact configured credential from returned answer text. This
is a credential-handling boundary, not isolation from arbitrary hostile code
running as the same OS user; use trusted workspaces and appropriate external
execution policy.

The asynchronous POSIX process adapter terminates its owned process group and
reaps the CLI on cancellation, timeout and protocol failure. It bounds elapsed
time, reported command starts and stdout bytes. A command-count limit is observed
after the CLI emits the start event; it cannot undo an already-started operation.
These are execution limits, not a strict dollar or API token budget. CLI usage is
returned as typed token counts. Ordinary unsuccessful commands can be repaired by
the coding agent; only a failed CLI/turn or contract violation fails the element.
No automatic business retry is added for potentially mutating coding work.

The optional [Codex image](../multi-agent/tests/infra/Dockerfile.codex) derives from
the UnifAI OpenShell receiver. It pins CLI 0.166.0 and installs the native binary at
`/usr/local/bin/codex`, with the package's Bubblewrap and ripgrep helpers also on
PATH. A version check alone cannot prove command execution: nested namespace
support must be tested inside the actual target environment. The opt-in
[Codex policy](../multi-agent/config/policies/openshell-codex.json) allows only that
binary to contact `api.openai.com:443`. A receiver using Mongo secret storage additionally needs working native database
transport and an operator-approved endpoint for its Python interpreter. The
private-file binding needs no database access from the sandbox. Preserve the
receiver's HTTPS proxy and certificate environment for the CLI; do not strip it
when creating the limited child environment. Add required endpoints to the
complete operator policy rather than allowing authored agents to widen it.
A supplied policy replaces image defaults; pre-existing sandboxes retain their
external owner's policy.

Codex supports API-key noninteractive execution and JSONL events in the
[official automation documentation](https://learn.chatgpt.com/docs/non-interactive-mode).
The initial small live scenario selects `gpt-5.4-nano`, verified with an actual CLI
coding task. The model is marked deprecated, so keep its API availability under
review rather than silently substituting an expensive model. Published standard prices are $0.20 per million input tokens and
$1.25 per million output tokens; recheck the
[model page](https://developers.openai.com/api/docs/models/gpt-5.4-nano) before
changing paid tests. It remains an explicit test choice, not a production default.

### Existing UI transport contracts

The native FastAPI application now composes `CatalogService` from the installed
registry. It provides `/api/catalog/categories`, `/api/catalog/elements` and
`/api/catalog/elements/{category}/{type_key}`, plus the existing UI's
`categories.list.get`, `elements.list.get` and `element.spec.get` forms. These
metadata routes use the same authentication boundary as the native API. Custom
resource editing also accepts the existing editor's `resource.schema`,
`resources.list`, `resource.get`, `resource.save`, `resource.update` and
`resource.delete` paths. Their camel-case request aliases and pagination envelope
are HTTP adapter concerns; persistence, credential protection, visibility,
optimistic version checks and dependency rules stay in `ResourceAuthoringService`.
The static editor paths are registered before native `/{rid}` routes.

The existing UI API clients can therefore use these flows without replacing their
components. The shared Axios boundary maps native `detail` errors to the UI's
existing `error` presentation, including validation messages, while retaining
HTTP status codes and the original failure. Category fallback no longer offers
retired sandbox elements. Other UI contracts remain under migration: this does
not make login, built-in administration,
chat/streams/approvals, collaboration, analytics or schedules complete on FastAPI.
Default backend startup remains unchanged until that cutover is verified.

Run actual TypeScript clients against a separately started native API and isolated
Mongo with `--ui-clients`; see the [test guide](../multi-agent/tests/README.md#actual-ui-api-clients).
That runner compiles the production client modules with the UI's locked Vite
version, exercises HTTP responses without mocks, and cleans its temporary bundle.
It is distinct from a browser test of the whole logged-in application. The UI's
production build and actual login-screen rendering were checked, but the identity
service was not running during that rendering check, so it is not login proof.

The full UI type audit now passes with `pnpm run typecheck`, including the
TypeScript contract suites. `pnpm run test:contracts` checks saved-reference graph
display and validates the chat-output boundary without external services. The
production build also passes with existing vendor chunk/size warnings. These are
separate checks from native HTTP integration and authenticated browser workflows.

Blueprint editor paths also use native application services. The inbound
`ui_blueprints` adapter parses the current editor's YAML/JSON strings with the
shared source parser off the event loop, and translates existing request fields
and response envelopes. It delegates writes to `BlueprintAuthoringService`,
validation to `BlueprintInspectionService` and display queries to
`BlueprintQueryService`. It is registered before dynamic blueprint-ID routes.
There is no call through Flask and no second blueprint writer.

Resolved snapshots retain transitive resources, missing-resource reports and
prompt shortcuts while masking registered credential fields. Reads do not create
new secret records or alter stored drafts. These snapshots are for display;
editing continues to read the protected draft, preserving opaque credential
references. Summary responses omit configuration, although the query service
currently retrieves full authoring documents before projecting them.

The editor carries the loaded version in update requests and remembers each
successful save's new version. A stale update returns 409. Team scope is explicit
in load, edit, deletion and sharing-metadata requests; authentication resolves
membership and retains the acting human for credential lookup. Request-body
`userId` is no longer sent to the metadata endpoint.

The real TypeScript blueprint-client case covers these transports and follows
the saved graph into native import, publication and session execution. Its
session calls use canonical APIs directly. Shared-chat authorization, raw multipart
uploads and complete authenticated browser workflows remain
required. Existing deployment startup is
retained until those contracts are finished and verified.

### Existing UI session and stream transport

The current UI's creation/submission, state/chat/status, list, metadata and
deletion paths now delegate to native application services. `BlueprintSessionService`
resolves and protects a blueprint, publishes an immutable revision under a unique
draft identity and creates a `ProgramSessionService` record pinned to it. Separate
session creations cannot race by publishing over one shared mutable draft.
Creation starts no engine run. Each submitted turn starts its own root execution;
the session does not add a wrapper child graph. Published program revisions have
independent retention from chat records, including when a chat is removed.

`SessionQueryService` projects chat/list data, checks blueprint availability and
retrieves metadata once per distinct blueprint in each page. Session-store queries
filter by the authenticated owner, paginate in stable creation-time/ID order and
accept the existing typed blueprint filter. Mongo indexes cover these owner and
owner/blueprint orderings. Memory and Mongo implement the same query/deletion
contract. Deleting a busy session is refused, and deleting an observed idle record
uses its version so a concurrent new turn cannot be orphaned.

The native execution stream remains SSE. The UI adapter translates the same
application events into NDJSON and binds the subscription to one execution.
An explicit stale execution selection returns 409; an open reader finishes using
its pinned execution even after another turn starts. Resume cursors use retained
interaction history. Missing count/timing monitoring stays null. Submitting a
human decision uses the native interaction service. Cancellation is accepted
asynchronously and returns the observed session status, rather than claiming it
has already stopped.

The shared UI API client generates a turn identity when one is not supplied;
callers can retain `executionId` when explicitly retrying an ambiguous submission.
Team scope is passed through session reads, submission, streams, cancellation and
approval calls, while identity and credential-user selection remain server-owned.
The NDJSON reader owns UTF-8 framing and reader cleanup. The subscription hook
passes a real abort signal, isolates replacement subscriptions and surfaces HTTP
failures. Disconnecting the client reader does not cancel backend work. Cancellation
keeps observing the server until its terminal result arrives.

The TypeScript sessions contract uses real HTTP/Mongo/Redis, including reader
abort, approval, replay, stale subscription rejection and a second cancelled turn.
The shared two-agent scenario also runs through UI session routes with real tools,
transitive resources and multiple turns on thread/process workers. Pure framing
tests cover split UTF-8, an unterminated final line and reader cleanup. These checks
do not prove full React callback/state ownership, authenticated browser navigation,
or shared-chat permissions. Approval cards retain their originating root execution
ID, and resolved-event handling matches both execution and request IDs, including
node-less child resolutions. Actual client tests also exercise rule save/read/clear
and stale actions; application/Redis cases cover persistence, recovery and revision
ordering. Turn admission refreshes an apparently busy session before rejection,
allowing a new turn immediately after its predecessor's result is available.
Use [session diagnostics](../.cursor/skills/debug-session-ui/SKILL.md) and the
[test guide](../multi-agent/tests/README.md#actual-ui-api-clients) for verification.

## Team editing during native API migration

Enable native resource/blueprint editing leases with `UNIFAI_EDIT_LOCKS=true`
and `UNIFAI_LIBRARY=true`. The composition root owns an asynchronous Redis client;
`UNIFAI_EDIT_LOCK_TTL` defaults to 180 seconds (accepted range 1–3600). Disabled
coordination returns 501, preserving the existing optional UI behavior. An enabled
Redis failure returns 503; clients must not interpret it as an unlocked entity.

`TeamEditService` owns authorization through the resource/blueprint application
services. The Redis adapter owns atomic acquire/renew/release, expiry and actor/
occurrence comparison. Thin FastAPI routes retain the collaboration endpoint
shapes. Membership and actor identity come from authentication; request-body
user/display fields do not grant authority. Status replies omit editor nonces.

Each native editor sends a unique `leaseId`. A late heartbeat/release from an old
editor cannot refresh or clear a newer occurrence's lease. Heartbeats never
reacquire expired leases. The UI disables saving while acquisition is pending
and closes an editor when renewal fails. Workspace changes remount its provider
and editors. Targeted full-App personal/team profile save/reload, delayed type
selection and team-switch checks pass in the owned browser fixture. Full workflow
authoring, account/session callback lifetimes and successful notification/share
flows remain outstanding; see [the active plan](plan.md#remaining-milestone-order).

These leases coordinate cooperative editors; resource/blueprint version checks
remain the persistence conflict boundary. They do not make writes transactional
with Redis. Older Flask clients use user-only leases, so a mixed deployment does
not provide complete occurrence fencing. Cut over matched clients/routes and
verify legacy-editor drain before claiming that guarantee.
