# UnifAI program platform: target architecture

Status: agreed architectural target, recorded 2026-11-01. This document defines
what we want to achieve and the criteria against which implementation should be
reviewed. It is not a claim that all capabilities below already exist.

UI direction clarified 2026-11-03: evolve the existing builder, resource library
and session experience into one coherent design and execution environment.
Preserve valuable capabilities, including live execution visualization, while
allowing substantial improvements to layout, navigation and interaction.

Implementation priority updated 2026-11-05: deliver one complete feature journey
with design approval, real coding, trusted checks, bounded repair, final review
and durable evidence through the existing UI. Work backend-led and connect the
thin UI journey as contracts stabilize; unrelated administration and broad hardening
must not delay it. Architectural correctness and necessary safeguards apply during
every milestone. The full scope remains required; see the
[active plan](../plan.md#remaining-milestone-order).

Use this README for architectural direction and the
[development guide](../program-platform-development.md) for implemented behavior.
Start routine work with [current status](../status.md) and [the active plan](../plan.md),
then consult relevant reference sections and selected [evidence](../evidence/README.md).
The frozen historical record is opt-in, not startup reading. Update direction when
an accepted design decision changes; historical evidence does not override it.

Fresh-platform decision (2026-11-01): old code, stored formats, workers, import
aliases, and dual APIs are not compatibility requirements. Convert useful behavior
to the target and remove superseded implementations, tests, dependencies, and
misleading guidance. Earlier old-worker retention and migration/drain requirements
are superseded. Safe cancellation and cleanup of current owned work still apply.

## Diagram navigation

All diagrams below describe the target; implementation status is called out
separately. The full diagrams from the design discussion are retained here.

- [Overall architecture and ownership](#architecture-and-ownership)
- [Definitions, configuration, and runtime hierarchy](#definitions-configuration-and-runtime-hierarchy)
- [Program model and callable components](#programs-and-composition)
- [Plugin files and registration flow](#adding-a-plugin-operation)
- [Runtime hierarchy shown in the UI](#runtime-hierarchy-in-the-execution-explorer)
- [Unified UI and live execution experience](#unified-ui-and-live-execution-experience)
- [UI-to-publication sequence](#ui-to-publication-sequence)
- [End-to-end execution sequence](#execution-sequence-and-ownership)
- [Invocation scope and ownership](#invocation-scope-and-ownership)
- [Execution profiles, environment reuse, and cleanup](#execution-profiles-and-environments)
- [Human Review pause and continuation](#human-in-the-loop-engine-pause-and-continuation-are-explicit)
- [Jira-to-CI/CD workflow](#adlc-example-and-verified-completion)
- [Detailed repository structure](#repository-organization)
- [Hexagonal dependency directions](#hexagonal-dependency-directions)

## Objective

Make reusable units of work composable into programs, and make programs composable
into larger workflows. Graph programs and registered application programs must
interoperate through the same public program contracts. Users must be able to
author, validate, publish, run, inspect, and interact with workflows through the UI,
API, or CLI without different execution semantics.

A representative workflow is Jira -> feature design -> human design approval ->
implementation/testing/review loop -> final approval -> CI/CD -> confirmed outcome. The implementation loop and
CI/CD can each be independently versioned programs, implemented as graphs or code.
The platform provides composition; integrations supply the particular operations.

Preserve the current services, specifications, factories, category builders,
dependency references, element bundles, immutable program revisions, execution
profiles, and Run Engine integration. Refine their responsibilities rather than
introducing parallel construction or execution frameworks.

## Architecture and ownership

These are logical boundaries, not a requirement for one microservice per box.

```text
+----------------------------------------------------------------------------+
| UI                                                                         |
|                                                                            |
| Component library | Workflow builder | Execution explorer | Review inbox   |
| Resource editor | Templates | Artifacts and results | Run history          |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| INBOUND ADAPTERS                                                           |
| FastAPI | CLI | Authenticated webhooks                                     |
| Translate requests, authenticate callers, return application responses     |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| UNIFAI APPLICATION                                                         |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | AUTHORING                                                            |  |
|  | Catalog and saved resources | Drafts and validation                  |  |
|  | Publication and immutable revisions                                  |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | EXECUTION SERVICES                                                   |  |
|  | Admission and placement | Start, inspect and cancel                  |  |
|  | Decisions and authoritative execution views                          |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | DOMAIN CONTRACTS                                                     |  |
|  | Operations | Programs | Bindings | Outcomes | Artifacts | Policies   |  |
|  | Definitions, identities and valid state transitions                  |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | CONSTRUCTION AND INVOCATION                                          |  |
|  | Specifications | Factories | Dependency bundles | Category builders  |  |
|  | Validate input -> construct scope -> invoke -> validate output       |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | APPLICATION-OWNED PORTS                                              |  |
|  | Runtime | Execution gateway | Storage | External capabilities        |  |
|  +----------------------------------------------------------------------+  |
+----------------------------------------------------------------------------+
                                      ^
                                      | implemented by
+----------------------------------------------------------------------------+
| OUTER IMPLEMENTATIONS                                                      |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | INFRASTRUCTURE ADAPTERS                                              |  |
|  | Run Engine | Mongo | Redis | Artifact storage | Telemetry            |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | CAPABILITY PLUGINS                                                   |  |
|  | Coding agents | Jira | Git | CI | Models | Retrieval                 |  |
|  +----------------------------------------------------------------------+  |
+----------------------------------------------------------------------------+

+----------------------------------------------------------------------------+
| RUN ENGINE                                                                 |
| Graph traversal | Durable coordination | Child runs | Dispatch             |
| Timers and waits | Recovery | Cancellation | Environment ownership         |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| EXECUTION INFRASTRUCTURE                                                   |
| Temporal | Worker pools | Processes | Kubernetes | OpenShell               |
+----------------------------------------------------------------------------+
```

The upward arrow is dependency direction: adapters implement ports owned by the
application. Runtime calls go from application services through those ports.
The composition root alone selects and wires concrete implementations.

UnifAI owns application semantics, permissions, contracts, decisions, and business
outcomes. Run Engine owns execution mechanics. ADLC-specific work management and
acceptance sit above generic program composition. Other kinds of programs must
not be forced to adopt software-engineering concepts.

## Fundamental components

| Component | Responsibility | Examples |
| --- | --- | --- |
| Component specification | Versioned configuration and capability metadata | Schemas, factory, requirements |
| Configured resource | Saved configuration and dependency references | Coding-agent configuration, model, tool provider |
| Dependency capability | Supplies behavior inside a constructed scope | LLM client, retriever, provider |
| Operation | Bounded work with typed input and output | Fetch ticket, coding attempt, execute tests |
| Program | Coordinates operations and other programs | Repair loop, review, CI/CD, delivery |
| Workflow/blueprint | User-facing authoring/template representation of a program | Visual workflow or declarative document |
| Execution | One running instance of a program revision | Root or child execution |
| Occurrence and attempt | A particular call/iteration/item and an execution attempt | Map item 7, iteration 2, retry 3 |
| Artifact | Durable output with identity, authorization, integrity and provenance | Change set, test report, build |
| Interaction | Authorized command or decision for a particular occurrence | Review response, intervention |
| ADLC work item | Expected business outcome and acceptance criteria | Implement an approved change request |

An operation can perform substantial work. Its distinction from a program is its
invocation/lifecycle contract, not its size. An ordinary operation need not create
a child program. Calling a reusable program creates a child execution.

Keep definitions, configuration, live objects, execution state, artifacts, and
infrastructure separate. A bundle packages construction configuration, not live
clients, conversation history, mutable work state, or plaintext credentials.

### Definitions, configuration, and runtime hierarchy

```text
+----------------------------------------------------------------------------+
| DEFINITION AND CONFIGURATION                                               |
| Component specification + implementation version                           |
|              |                                                             |
|              v                                                             |
| Configured resource ------> Dependency resources                           |
|              |                                                             |
|              v                                                             |
| Program draft ------> Published program revision                           |
+----------------------------------------------------------------------------+
                                      |
                                  start run
                                      |
                                      v
+----------------------------------------------------------------------------+
| RUNTIME                                                                    |
| Program execution                                                          |
|      |                                                                     |
|      +--> Step occurrence                                                  |
|      |       +--> Attempt 1                                                |
|      |       +--> Attempt 2                                                |
|      |                                                                     |
|      +--> Child program execution                                          |
|      |       +--> Its own occurrences and attempts                         |
|      |                                                                     |
|      +--> Artifact references, decisions and accepted outcomes             |
+----------------------------------------------------------------------------+
```

## Programs and composition

There is one public Program concept and lifecycle. Graph composition and registered
Python coordination are implementation choices, not separate resource libraries,
execution APIs, or mandatory user-facing program categories. Retain the internal
distinction where validation, editing, compilation, or inspection requires it; do
not reorganize the platform into parallel graph/code product stacks.

```text
+----------------------------------------------------------------------------+
| PROGRAM                                                                    |
| Versioned inputs, outputs, configuration and execution policies            |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | GRAPH IMPLEMENTATION                                                 |  |
|  | Calls, branches, loops, parallel work and waits                      |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | APPLICATION IMPLEMENTATION                                           |  |
|  | Registered async Python program                                      |  |
|  | Coordinates through application runtime ports                        |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
| Either implementation can invoke:                                          |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | OPERATIONS                                                           |  |
|  | Typed request -> bounded operation -> typed result                   |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | OTHER PROGRAMS                                                       |  |
|  | Typed inputs -> child graph or code program -> typed outputs         |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | DEPENDENCY CONSTRUCTION                                              |  |
|  | Saved resources -> references -> bundle -> factories -> owned scope  |  |
|  +----------------------------------------------------------------------+  |
+----------------------------------------------------------------------------+
```

### Installed implementations and configured programs

A developer can implement a program in the backend, declare its configuration and
input/output schemas, and register its versioned implementation. The catalog makes
that capability discoverable. Users select it in the UI, fill its configuration,
bind declared dependencies, save a named program draft, and publish a reusable
revision. The saved definition references the installed implementation/version;
it does not store a live Python object or duplicate the implementation source.

```text
+--------------------------------------------------------------------+
| BACKEND EXTENSION                                                  |
| Implementation + configuration/input/output schemas + registration |
+---------------------------------+----------------------------------+
                                  |
                                  v
+--------------------------------------------------------------------+
| UI: PROGRAMS LIBRARY AND AUTHORING WORKSPACE                       |
| Select implementation -> configure -> bind dependencies            |
| Save draft -> validate -> publish immutable revision               |
+---------------------------------+----------------------------------+
                                  |
                                  v
+--------------------------------------------------------------------+
| REUSABLE PROGRAM REVISION                                          |
| Run directly | Call from a larger program | Inspect execution      |
|                                                                    |
| Jira -> Engineering -> Human Review -> CI/CD -> Validation         |
+--------------------------------------------------------------------+
```

Keep stable program configuration, per-execution input, and placement/environment
policy separate. Dependency binding uses declared contracts and authorized pinned
references, not arbitrary repository access from coordination code. Credentials
use protected references and scoped capabilities, not ordinary portable values.

Schema-based forms are the default configuration experience; specialized editors
may improve complex configurations while using the same application contracts.
Backend validation remains authoritative. Visual composition edits a program's
graph when available; a registered implementation exposes its configuration,
interfaces and declared dependencies without requiring an editable internal graph.
Both support observed execution drill-down through the same runtime contracts.

Calling these saved definitions "program resources" in the product is acceptable,
but element resources and program definitions retain distinct typed contracts and
construction/publication responsibilities. Neither a graph wrapper nor conversion
to an element is required merely to reuse a registered program.

Saved element selection resolves on the server through the library's authorized
configuration and dependency contracts. Authoring commands carry source revisions;
published programs carry protected, frozen construction snapshots. Reuse existing
specifications, bundles, factories and builders. Preserve snapshots during ordinary
edits, and require explicit adoption when a selection changes configuration shared
by existing blocks. Keep saved-resource defaults and per-call placement separate.
Display/redacted configuration is not an execution snapshot.

The proposed minimal composition vocabulary is:

| Form | Meaning |
| --- | --- |
| Call | Invoke an operation or pinned program |
| Flow | Region with explicit ordering/dependencies and data bindings; supports sequential and parallel work |
| Choose | Select a declared branch from a validated predicate or recorded decision |
| Repeat | Execute a body until an outcome or explicit bound |
| Map | Execute a body for runtime items with bounded concurrency |
| Wait | Await a correlated event/decision or deadline through engine coordination |

Owned inline bodies and published calls share these composition contracts. An
inline body belongs to its enclosing draft/revision; it has no independent library
identity, owner or publication lifecycle. It can contain operation calls, declared
controls and further bodies. Publishing the enclosing Program freezes the complete
owned structure and its referenced published revisions. Extracting a body for
independent reuse is an explicit authoring action, not an automatic helper
publication required for every branch or loop.

Definition identity and execution identity stay separate. Identify an owned body
by the enclosing published revision plus a stable path of authored block/child
identities. An actual invocation additionally has its own native execution,
occurrence, item/iteration and attempt identities. Do not invent unrelated global
Program IDs for inline bodies or use mutable canvas indices as durable addresses.
Inspection resolves the body from the immutable revision that ran. Calls to a
separately published Program retain that Program's own revision identity.

Protection, dependency validation and contract checks traverse the owned structure.
Nested scope does not implicitly grant environments or credentials: imports,
placement, authority and lifetimes retain the same explicit rules as reusable
Program calls. Lower bodies and controls through the existing compiler/runtime
ports and native children; do not create a second orchestration mechanism.
Backend owned-body definitions, recursive protection/publication and lowering to
native children are implemented and proven on Local thread/process paths. The
production client can round-trip, publish, execute and inspect their source
addresses. Visual inline authoring, full occurrence inspection and current-source
remote/recovery verification remain open; see the implementation ledger.

Timeout, retry, failure handling, and environment ownership are explicit scope/call
policies. Join semantics must be declared, including treatment of failed or losing
branches. Program implementations and composition semantics are versioned.

This is an application composition model, not another scheduler or durability
system. Static regions lower to engine graphs; other forms can lower to versioned
application programs using existing child, invocation, message, and timer ports.
Retain registered application code as an escape hatch. Arbitrary Python does not
need to round-trip into an editable graph.

Distinguish four relationships: construction dependencies, execution ordering,
data bindings, and placement. An ordering edge does not establish a data contract
or credential permission. Sharing compute does not imply shared agent state.

Agent decisions are invoked effects producing validated, recorded data. Durable
control flow branches on that recorded result. Replaying coordination must not
silently ask the model to produce a new plan.

Initially reuse declared, pinned child programs. Future runtime program selection
or recursive delegation requires authorization, compatible contracts, recorded
references, depth/fan-out limits, and a shared budget. Dynamic plan changes are
validated proposals accepted at defined boundaries; they cannot rewrite history.
Define whether already-running work finishes, is cancelled, or is superseded.

## Operation contracts and extension convention

An executable specification describes configuration, input/output schemas,
implementation version, dependencies, required capabilities, and relevant effect,
retry, cancellation, and resumption characteristics. Calls carry a narrow context:
occurrence/attempt identity, deadline, progress capability, and granted resources.
Do not inject an unrestricted service container or engine SDK object.

Keep existing specification/factory/builder conventions. Construction resolves and
validates the dependency closure, freezes the bundle, builds dependencies in order,
prepares the owned scope, invokes, validates the result, and releases resources even
after partial construction, failure, or cancellation. Pure construction can be
synchronous; preparation, I/O, invocation, and release are async.

A new Jira operation should register a specification and factory, implement the
operation contract, and supply schemas. It should require no Jira-specific compiler
branch, execution endpoint, workflow runner, or hardcoded canvas behavior.

The shared catalog feeds generic forms and typed ports. Optional presentation
extensions can improve a specialized editor without changing semantic contracts.
Trusted plugin registration is explicit at composition time; catalog discovery
must not construct live provider clients. External plugin distributions may use
an allowlisted registration mechanism without a second registry.

Plugin is a packaging/catalog concept, not a reason to move application policy
outside the library. Provider integration belongs in the outer ring; reusable
vendor-neutral coding or acceptance behavior belongs in application modules.

### Adding a plugin operation

A small plugin follows the existing specification/factory convention:

```text
plugins/mas_plugins/tickets/jira/
|
+-- contracts.py      # Configuration and invocation models
+-- specification.py  # Identity, schemas, capabilities, factory registration
+-- factory.py        # Construct the configured implementation
+-- operation.py      # Jira integration and result translation
```

Registration makes it usable by the same catalog, editor, and invocation path:

```text
+----------------------------------------------------------------------------+
| ADD PLUGIN                                                                 |
| Configuration/input/output schemas | Operation | Spec and factory          |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| COMPOSITION ROOT                                                           |
| Explicitly enable plugin and register its specification                    |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| EXISTING CATALOG                                                           |
| Expose public metadata and schemas without constructing live clients       |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| UI COMPONENT LIBRARY                                                       |
| Generate configuration form and typed connection ports                     |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| SHARED INVOCATION PATH                                                     |
| Construct -> prepare -> execute -> validate -> release                     |
+----------------------------------------------------------------------------+
```

## UI and public contracts

The UI has three linked views: authored intent, admitted execution, and observed
execution. Canvas positions and visual styling are separate from executable
semantics. The backend owns validation and execution policy for every client.

### Unified program builder and reusable libraries

Evolve the existing blueprint builder into one program-authoring workspace. A
blueprint is the user-facing authoring/view representation of a program draft;
publication produces the canonical program revision. Preserve separate presentation
metadata without maintaining independent executable blueprint and program models.
The initial standalone **Compose a Program** screen is an interim implementation
view whose useful behavior should be folded into this workspace.

Keep these reusable definitions distinct, while making both discoverable from the
builder's libraries:

- An element resource is a saved configuration of an installed element, including
  its construction dependency references. Specifications/factories/builders own
  its construction and lifecycle. Executable resources are used in operation calls.
- A program definition coordinates operations and/or other programs, with public
  input/output contracts, configuration, bindings and execution/environment policies.
  Publish immutable revisions for reuse. A program becomes a child through a runtime
  call relationship; it is not permanently a separate "child program" type.

The Programs library contains all saved programs. Do not require users to choose
separate graph/code libraries or expose implementation terminology before their
task requires it. Creating a program can start from visual composition or an
installed implementation's configuration form, within the same workspace and
draft/publication/run lifecycle. Element resources remain a complementary library.

Expose operation calls, program calls, Flow, Map, Repeat, Choose and Wait as clear
authoring blocks. Users configure work and control flow in the same builder.
Lowering some controls to installed versioned application programs is an execution
mechanism; it must not require a separate user-facing workflow language or manual
helper-program creation for every loop/branch. Registered custom Python programs
remain supported through the same program contracts/runtime ports.

Provide two explicitly different forms of expansion:

- **Definition expansion:** inspect a called program's public contract and pinned
  revision; expand its internal graph when available. Editing the reusable program
  opens its own draft and publishes a new revision. Callers explicitly adopt that
  revision; expanding or editing a view never silently changes a pin. Code programs
  expose configuration/interfaces and declared calls without promising arbitrary
  Python-to-graph round-tripping.
- **Execution drill-down:** open the actual child execution for a call, then its
  operation invocations, nested calls, map items, iterations and attempts. Distinguish
  one authored block from its many runtime occurrences. Code-program execution
  inspection uses observed calls/events even when no editable internal graph exists.

The same workspace must preserve element configuration, program configuration and
execution inputs as distinct lifecycles. Keep construction references, runtime data
bindings, control ordering and placement distinct. Include approved profiles,
named environments and explicit child imports in authoring/inspection through safe
application contracts. The UI presents and edits definitions; application services
own validation/publication/authorization, and Run Engine owns native execution and
physical environment lifecycle. This clarification adds no scheduler or program kind.

### Unified UI and live execution experience

The existing UI is a source of useful behavior and interaction patterns, not a
fixed layout to reproduce. Build a cohesive ADLC experience with clear hierarchy,
readable cards, contextual inspectors, progressive disclosure, purposeful motion
and responsive layouts. Status must be accessible through text/icons as well as
color; provide keyboard alternatives to canvas gestures and respect reduced-motion
preferences. Visual polish must make actual work easier to understand and control.

The product has connected library, design and execution areas:

```text
+-----------------------------------------------------------------------+
| LIBRARY                                                               |
| Programs | Configured element resources | Templates                   |
| Discover -> Inspect -> Configure -> Reuse                             |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
| PROGRAM WORKSPACE                                                     |
| Overview | Design / Configuration | Interface | Published revisions   |
| Resource calls | Pinned Program calls | Inline controls | Placement   |
| Save unfinished draft -> Validate -> Publish                          |
+-----------------------------------+-----------------------------------+
                                    |
                    Manual form / Session / Trigger
                                    |
                                    v
+-----------------------------------------------------------------------+
| SHARED EXECUTION WORKBENCH                                            |
| Overview | Live flow | Timeline | Inputs / Outputs | Artifacts        |
| Nested occurrences | Environments | Authorized interactions           |
| Conversation when supported; review inbox links to the same execution |
+-----------------------------------------------------------------------+
```

Programs are first-class reusable entries in the library and canvas. Keep one
public Program lifecycle for graph composition and configured backend
implementations. An installed implementation supplies configuration/input/output
schemas; it can be configured, saved, published and called without a separate
product experience. Resources retain their own configuration/dependency semantics.
Using a published Program pins a revision; creating from a template makes an
independent draft. Repeated calls can reuse one resource while retaining distinct
block and execution identities.

Converge the existing blueprint builder and interim Programs screen into one
authoring workspace. Reuse useful canvas, form, dependency-selection, validation,
placement, theme and personal/team patterns. Keep one canonical draft document;
derive canvas/YAML views and store presentation separately. The renderer is a
replaceable presentation adapter. Reusing the existing graph surface is preferred
where suitable, but preserving a particular rendering library or page layout is
not an architectural requirement. Do not maintain competing permanent builders.

Evolve the existing session execution layout into a shared execution workbench.
All entry points open the same execution detail experience. Invocation uses the
published Program's structured input contract, with schema-driven forms and an
advanced JSON option. Conversation is an explicit supported interaction mode,
not a requirement imposed on every Program. Manual, scheduled and event-driven
invocations use the same admission and observation contracts. Sessions optionally
group related invocations and retained interaction context; they are distinct
from root executions and child calls. Keep saved configuration, invocation input,
session context, credentials and placement separate. Session continuity does not
implicitly grant shared compute, workspace files or agent memory.

Preserve and improve the ability to see what is running now. The live flow and
execution tree must identify active work and parallel branches, nested Program
calls, map items, loop iterations, retries and observed waits. Show why work is
waiting when authoritative information is available: dependency, human review,
external event or resource admission. Selecting an occurrence reveals its actual
inputs/results, attempts, logs, artifacts, safe placement and authorized actions.
For example, an Engineering block can summarize repair iteration 2 of 5 with
coding completed, tests running and review pending, then open those occurrences.

Drive indicators and animations from authoritative snapshots/updates. Node UID
alone cannot identify an occurrence. Preserve exact revision/source mapping for
historical execution, even after the editable definition changes. Distinguish
unknown/disconnected observation from waiting, failure and completion; do not
invent progress percentages, timing or inferred success. Load aggregate summaries
and paginate deeper detail rather than rendering an entire execution tree at once.

Design and execution inspection share a consistent visual language with explicit
editing/inspection modes. Definition expansion follows pinned reusable structure;
execution drill-down follows observed children and occurrences. Registered Python
implementations expose public contracts and observed work without promising an
editable graph for arbitrary code. Reviews target exact authorized occurrences
and evidence. Business review, tool approval and operational pause/resume remain
distinct. Show execution completion separately from verified/accepted outcomes.

Maintain SOLID/hexagonal boundaries throughout: renderers own presentation,
authoring controllers own draft edits/conflicts, observation controllers own
snapshot/event lifetimes, and API clients translate application contracts.
Application services own authorization, publication, admission and business
outcomes. Run Engine owns scheduling, durable waits and physical environments.
Do not put provider/engine SDKs, credential resolution, scheduling or execution
policy inside canvas components. These UI requirements refine the target; they
are not claims that the current screens already satisfy it.

| Contract | Required information |
| --- | --- |
| Catalog | Identity/version, configuration/input/output schemas, requirements, documentation and form hints |
| Draft | Composition, bindings, references and expected revision |
| Validation | Stable codes, severity, source paths, affected blocks/ports and explanations |
| Preview | Resolved dependencies/placement, compatibility and policy warnings; no execution side effects |
| Publication | Immutable revision and resolved dependency identities |
| Execution view | Hierarchy, occurrences, attempts, outcomes, waits, artifacts and source mapping |
| Observation | Authoritative snapshot plus resumable updates; explicit reset if history expired |
| Interaction | Response schema, authorized actions, expiry and exact reviewed occurrence/artifact |
| Control | Target, expected revision, idempotency identity and recorded outcome |

Validation results are revision-scoped and advisory; admission rechecks current
authority and compatibility. Schema checking catches obvious binding errors before
execution and validates concrete values at runtime. Schemas alone do not prove
semantic correctness.

Map authored blocks to published identities and actual runtime occurrences. Node
UID alone cannot identify repeated loop visits, concurrent items, child runs, and
attempts. Provide aggregate status and paginated drill-down rather than rendering
every occurrence at once. Stream disconnection must not imply run completion.

### Runtime hierarchy in the execution explorer

The authored definition and actual occurrences remain separate. A UI block can
expand into the following execution tree:

```text
Delivery execution
|
+-- Fetch ticket
|
+-- Implementation program
|   +-- Iteration 1
|   |   +-- Coding attempt
|   |   +-- Verification: rejected
|   +-- Iteration 2
|       +-- Coding attempt
|       +-- Verification: accepted
|
+-- Human review: approved
|
+-- CI/CD program
    +-- Build
    +-- Deploy
    +-- Deployment validation
```

## UI-to-publication sequence

```text
+------------+ +-------------+ +-----------------+ +------------------+
| UI         | | FASTAPI     | | AUTHORING       | | CATALOG / STORE  |
+-----+------+ +------+------+ +--------+--------+ +---------+--------+
      |               |                |                    |
      |-- catalog --->|--------------->|-- read metadata -->|
      |<-- schemas ---|<---------------|<-- specifications -|
      |               |                |                    |
      | build blocks, bindings, nested calls and policies  |
      |               |                |                    |
      |-- validate -->|--------------->|                    |
      |               |                | check contracts    |
      |               |                | dependencies       |
      |               |                | topology and limits|
      |<-- diagnostics linked to blocks and ports ---------|
      |               |                |                    |
      |-- save draft->|--------------->|-- compare version->|
      |<-- new draft revision ---------|<-- saved -----------|
      |               |                |                    |
      |-- publish --->|--------------->|                    |
      |               |                | resolve and pin    |
      |               |                | dependency versions|
      |               |                |-- save revision -->|
      |<-- published program reference-|<-- immutable ------|
```

Publishing part of a workflow requires declared public inputs, outputs, and
outcomes. Its parent uses a pinned program reference. Publishing a newer version
does not silently change existing references or executions.

## Execution sequence and ownership

```text
+----------+ +-------------+ +-------------+ +-------------+ +-------------+
| UI       | | APPLICATION | | ENGINE      | | RUN ENGINE  | | WORKER      |
|          | | SERVICES    | | ADAPTER     | |             | | RECEIVER    |
+----+-----+ +------+------+ +------+------+ +------+------+ +------+------+
     |              |              |              |               |
     |-- start ---->|              |              |               |
     |              | authorize    |              |               |
     |              | admit budget |              |               |
     |              |-- prepare -->|              |               |
     |              |              | compile, bind and map sources|
     |              |<-- snapshot -|              |               |
     |              | persist intent              |               |
     |              |-- submit --->|-- start ----->|               |
     |<-- run ID ---|              |              |               |
     |              |              |              |-- invoke ---->|
     |              |              |              |               | build
     |              |              |              |               | plugin
     |              |              |              |               | execute
     |              |              |              |<-- result ----|
     |              |              |              |               |
     |              |              |              | start child:  |
     |              |              |              | implementation|
     |              |              |              | program       |
     |              |              |              |               |
     |              |              |              | code/test/    |
     |              |              |              | review loop   |
     |              |              |              |               |
     |              |              |<-- lifecycle / results ------|
     |              |<-- normalized execution facts               |
     |              | update application view     |               |
     |-- inspect -->|              |              |               |
     |<-- snapshot and occurrence updates --------|               |
```

### Invocation scope and ownership

```text
+----------------------------------------------------------------------------+
| UNIFAI WORKER RECEIVER                                                     |
|                                                                            |
| Validate envelope and authority                                            |
|              |                                                             |
|              v                                                             |
| Resolve bundle -> build dependencies -> prepare owned invocation scope     |
|              |                                                             |
|              v                                                             |
| Invoke operation through its typed contract                                |
|              |                                                             |
|              v                                                             |
| Validate result -> publish artifact references -> release resources        |
+----------------------------------------------------------------------------+
```

| Owner | Responsibility |
| --- | --- |
| Run Engine | Physical environment, dispatch, grants and cleanup |
| Receiver | Constructed clients and invocation-scoped resources |
| Plugin | Integration behavior and owned subprocess/protocol |
| Application | Artifact access, review authority and business acceptance |

UnifAI owns behavior and constructed invocation resources. Plugins own their
integration protocols and subprocesses. Run Engine owns physical environments,
grants, borrowing, dispatch, and cleanup. Publish durable outputs before relying
on them surviving environment destruction.

Placement stays outside behavioral configuration: operation requirements plus
author preference plus tenant policy resolve to a compatible profile. Persist the
resolved execution choice. Public UI contracts expose approved names and safe
metadata, not raw infrastructure credentials or SDK configuration.

Named environments can be reused under explicit run ownership and child imports.
Borrowers do not own deletion. Intentionally shared writable workspaces need an
explicit concurrency policy; independent coding branches default to isolated
workspaces based on a known revision. Compute reuse, artifacts, and chat history
have different lifetimes.

## Execution profiles and environments

Execution profiles and environments are first-class placement concepts in this
design. They are required for composable operations, graph programs, custom
programs, isolated coding, controlled reuse, and predictable cleanup.

| Concept | Meaning | Owner |
| --- | --- | --- |
| Execution profile | Approved configuration describing how invocations execute: backend, installed implementation/image, resource/isolation/network policy, and supported capabilities | Deployment configuration and UnifAI admission policy |
| Named environment binding | Program-local name selecting a reusable environment backed by a compatible profile | Declaring program revision and its owning execution |
| Live environment | Actual process/container/pod/sandbox instance and its engine-managed binding/grants | Run Engine and its backend adapter |
| Workspace | Mutable files used by a task; can be inside an environment but has separate concurrency and handoff semantics | Application work policy and operation configuration |
| Artifact | Published durable output that remains usable after compute is destroyed | UnifAI artifact services and storage adapters |

A profile selects execution characteristics; selecting the same profile twice
does not by itself select the same live environment. Explicit named bindings
express reuse. A physical environment can contain several sequential invocations
with separately constructed clients and agent configurations.

### Placement resolution and persistence

```text
+----------------------------------------------------------------------------+
| UI AND AUTHORING                                                           |
| Resource preference | Program default | Per-call selection                 |
| Named environment declarations | Placement preview                         |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| UNIFAI APPLICATION                                                         |
| Operation requirements + saved preferences + tenant policy                 |
| Resolve compatible placement; reject unavailable or forbidden choices      |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| UNIFAI ENGINE ADAPTER                                                      |
| Translate public selections into engine targets and bindings               |
| Persist concrete execution settings before submission                      |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| RUN ENGINE                                                                 |
| Create or borrow the selected environment | Dispatch invocation            |
| Enforce ownership and child grants | Release owned environment             |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| EXECUTION BACKENDS                                                         |
| Local/process workers | Kubernetes | OpenShell | Other supported backends  |
+----------------------------------------------------------------------------+
```

Placement remains beside behavioral configuration. Do not put raw engine targets,
Kubernetes configuration, OpenShell policies, or credential values into an agent's
ordinary configuration schema. The UI discovers approved profile names, shows
capability/availability diagnostics, and previews effective placement before a run.

- A reusable resource can save a profile preference.
- A program/workflow can save a default and declare named environments.
- A particular call can select a profile or a declared environment, exclusively.
- A published revision retains those authored selections and references.
- Admission resolves concrete deployment settings and persists the prepared
  execution. Recovery reuses that snapshot; later runs may resolve newer settings.
- Concrete production images and implementations require immutable version/digest
  pinning; freezing a mutable tag string does not freeze its contents.

Preserve current graph authoring semantics during evolution: omitted/null call
placement inherits the resolved resource preference, then workflow/program and
platform defaults. An explicit empty selection bypasses the resource preference.
An explicit profile or named environment overrides inheritance. Reject an invalid,
unsupported, or unauthorized selection instead of silently weakening isolation.

A program's default governs invocation placement; it does not automatically move
its durable coordinator into a coding sandbox. Conditions can have independent
placement. Dependency clients such as an LLM or tool provider are built inside
the invoking operation's scope; independently placing them requires an explicit
operation/service boundary.

### Reuse, child programs, and cleanup

```text
+----------------------------------------------------------------------------+
| ROOT EXECUTION: DELIVERY                                                   |
|                                                                            |
| Named environment: coding -> approved coding profile                       |
| Owner: this root execution                                                 |
|      |                                                                     |
|      +--> Implement operation uses coding                                  |
|      +--> Test operation reuses coding after implementation                |
|      |                                                                     |
|      +--> Child program: repair                                            |
|      |       Import: child-local workspace -> parent coding                |
|      |       Child borrows; parent retains ownership                       |
|      |                                                                     |
|      +--> Parent can continue using coding after child completes           |
|                                                                            |
| At owner close: drain owned work -> release through Run Engine             |
| Publish durable artifacts before environment destruction                   |
+----------------------------------------------------------------------------+
```

Run Engine owns provisioning, binding, grants/borrowing, dispatch, release, and
cleanup reconciliation. UnifAI decides which bindings are permitted to be shared.
Children receive only explicitly imported environment bindings with local aliases;
access to one environment does not grant every parent environment or credential.

An invocation-scoped target and a run-owned named environment have different
lifetimes. Child-owned environments close with that child's scope. Borrowed
environments remain owned by their declarer. Externally managed environments
retain their external owner's deletion responsibility.

On completion, failure, timeout, or cancellation, follow engine ownership and
drain/release semantics. Cleanup uncertainty is observable and reconciled through
engine/backend mechanisms; do not invent another environment manager in UnifAI.
A human-review wait does not silently destroy an intentionally retained parent
environment. Idle release/recreation requires an explicit supported lifetime
policy and durable workspace handoff.

Sharing an environment does not merge agents, CLI histories, model state, or
credentials. Concurrent coding defaults to isolated workspaces; shared writable
files require explicit coordination. Environment reuse is bounded by declared
ownership, rather than implicitly extending across unrelated runs or chat turns.

### Existing foundation and target extension

The current platform already persists graph-node/condition profile preferences,
workflow defaults, named environments, prepared settings, placement previews, and
child environment imports. Resource preference validation currently applies to
nodes and conditions. The target carries these semantics into typed operation
calls and custom program invocation contracts. Per-tenant profile authorization,
richer capability policy, and complete production recovery/isolation evidence
remain implementation work.

See [implemented profile persistence and authoring](../program-platform-development.md#profile-persistence-and-authoring)
for current APIs, UI behavior, precedence, and limitations.

## Human-in-the-loop: engine pause and continuation are explicit

Yes: human review and custom HITL behavior must use Run Engine coordination
through UnifAI runtime ports. Do not implement a second pause/resume scheduler.
There are two distinct mechanisms:

| Mechanism | Intended use | Ownership |
| --- | --- | --- |
| Graph pre-node interrupt/resume | Operational pause before a selected graph node | Engine checkpoints and suspends traversal; UnifAI controls access and maps public commands |
| Durable program wait | Human Review, structured input, external decisions and custom program interactions | UnifAI validates/persists the interaction; engine messages/timers suspend and continue coordination |

A graph resume payload alone is not an authorized business approval. Human Review
is a registered, versioned application program, exposed as a reusable UI block.
Graphs and custom programs can call it through the same program contract.

For an operation requiring human input, compose the review before the operation,
or split its work at a meaningful boundary: propose -> review -> apply. A wrapper
program coordinates those operations and the durable wait. Keep long-lived
coordination out of an ordinary operation's graph-state method. An existing
agent's in-flight tool approval may use a bounded invocation-local gate; it must
not be presented as restart-durable review without evidence for that guarantee.

Custom installed programs can define their own authorized interaction protocols
and await them through the application runtime. Invoked effects open/reconcile/
finalize application records; the durable coordinator itself performs no direct
database, network, or wall-clock I/O. SDK types remain in adapters.

```text
+-------------+ +----------------+ +-------------+ +------------------+
| PROGRAM     | | REVIEW SERVICE | | UI / HUMAN  | | RUN ENGINE       |
+------+------+ +-------+--------+ +------+------+ +---------+--------+
       |                |                |                  |
       |-- open review->| persist artifact, criteria, occurrence
       |                |-- pending ---->|                  |
       |-- durable wait ----------------------------------->|
       |                |                |                  |
       |                |<-- decision ---|                  |
       |                | authorize reviewer                |
       |                | validate response and revision    |
       |                | persist decision + delivery intent|
       |                |-- wake exact waiting run -------->|
       |<-- wake and reconcile recorded decision -----------|
       | continue, request changes, or reject               |
       |                |-- updated ---->|                  |
```

The persisted accepted decision is authoritative; a message is a wake-up.
Accept identical retries idempotently and reject conflicting, stale, expired,
cancelled, or superseded decisions. Use atomic pending delivery/outbox semantics
and reconciliation for the database-to-engine boundary. Bind approval to the exact
artifact and review occurrence; later loop visits have different identities.
Cancellation and expiry prevent late responses from reviving closed work.

Waiting should occupy coordination state rather than hold an invocation worker
solely to await a human. Intentionally retained environments still follow their
declared lifetime. Temporal supplies restart-durable coordination; Local waiting
is in-memory. Pausing stops progress at a defined boundary; it cannot undo an
external action already sent.

Current-state distinction: UnifAI has runtime message waiting and existing tool
approval behavior. The dedicated Human Review program is planned. The compiler
does not currently enable graph pre-node interrupts. See the development guide's
[Human Review design](../program-platform-development.md#human-review)
for the investigated engine mapping and detailed acceptance cases.

## ADLC example and verified completion

```text
+--------------------------------------------------------------------------+
| PROGRAM: DELIVER A JIRA CHANGE (TARGET)                                  |
|                                                                          |
| Fetch Jira ticket -> analyze requirements                                |
|                          |                                               |
|                          v                                               |
| +----------------------------------------------------------------------+ |
| | PROGRAM: DESIGN AND DELIVER A FEATURE                                | |
| |                                                                      | |
| | Propose versioned design -> Human review                             | |
| |           ^                      |                                   | |
| |           +--- reject + feedback -+                                  | |
| |                                  | approved exact revision           | |
| |                                  v                                   | |
| | +------------------------------------------------------------------+ | |
| | | PROGRAM: ENGINEERING                                             | | |
| | |                                                                  | | |
| | | Code -> trusted checks -> human review -> evaluate acceptance    | | |
| | |   ^                                           |                  | | |
| | |   +--------- evidence and repair feedback -----+                 | | |
| | |                                                                  | | |
| | | Bounded repair; exact candidate, evidence and final decision     | | |
| | +------------------------------------------------------------------+ | |
| |                                                                      | |
| | Unsatisfied design stops before Engineering; bounds are explicit     | |
| +----------------------------------------------------------------------+ |
|                          | verified work                                 |
|                          v                                               |
| +----------------------------------------------------------------------+ |
| | PROGRAM: CI/CD                                                       | |
| |                                                                      | |
| | Build -> checks -> deploy -> validate actual deployment              | |
| +----------------------------------------------------------------------+ |
|                          |                                               |
|                          v                                               |
| Update Jira with the observed delivery outcome                           |
+--------------------------------------------------------------------------+
```

Every program can be graph- or code-implemented. Reuse the implementation program
unchanged in other workflows. Parallel tasks use Map plus isolated workspaces;
integration produces a new candidate that is verified again. Dynamic delegation
uses admitted program references, not hardcoded workflow-engine branches.

Operation success means an attempt returned successfully. ADLC acceptance means
trusted evidence satisfies the agreed criteria for the exact candidate. Use typed
outcomes such as accepted, needs_clarification, budget_exhausted, and
verification_failed instead of parsing an agent's final paragraph.

### Configurable deliverables and completion

The core Program platform remains independent of Git and any particular definition
of "work done." The ADLC layer distinguishes the expected deliverable contract,
the completion policy governing required checks and approvals, and the delivery
outcome when publication, integration or deployment is required.

Reusable Engineering Programs configure compatible candidate-producing,
verification and delivery capabilities through declared input/output schemas and
normal registered extensions. A deliverable may be a Git revision, patch, file,
document or another typed result. The same Program can select among declared
compatible alternatives without changing the generic runtime. Validate compatibility
before dispatch where possible and validate concrete results at runtime. Do not
introduce a mandatory universal result wrapper or speculative reference registry.

Coding agents may manage branches, worktrees, edits, commands and commits internally
through their available tools. Separate repository operations are appropriate when
independent inspection, controlled preparation, publication authority or reuse
justifies the boundary; not every Git command needs a platform operation. Agent
integrations own execution details, adapters own external protocols, ADLC
coordination owns acceptance policy, and Run Engine owns scheduling and environments.

Treat worker output as a candidate. Schema validity and self-reported success alone
do not establish completion. Independently inspect references where required and
bind verification and review to the exact candidate. Changed candidates require
appropriate new evidence. Retain the deliverable before deleting temporary compute.

Freeze configured contracts and completion policy in the published definition,
with any permitted invocation selections validated and recorded in admitted
execution settings. Runtime selection remains within declared alternatives. Any
supported amendment to acceptance requirements must be explicitly recorded,
validated and appropriately authorized; it cannot mutate the published revision,
erase prior decisions or silently reuse evidence for different requirements.

Use a small concrete deliverable to prove the first useful journey. A complete Git
subsystem is not a prerequisite for that milestone, and a bounded file-transfer
example must not become the only supported definition of completed work.

### Typed outputs and immutable references

Artifact publication is optional. Each operation declares its own validated input
and result model; the execution kernel passes portable values without interpreting
Git, blob storage, Jira, or CI/CD semantics. Simple results can remain ordinary
typed data. Do not force every output into an artifact envelope or add a universal
reference registry just to anticipate hypothetical backends.

Committed source can be handed off as a repository identity plus a full immutable
Git commit ID. A moving branch name must be resolved to a recorded immutable
revision before it becomes a candidate for testing, review, or deployment. Git
checkout/materialization belongs in an integration adapter, and source-candidate
semantics belong in the ADLC layer. Commit availability and authorization must be
established; knowing an ID does not grant access to its repository.

Managed files, uncommitted patches/snapshots, reports and other byte outputs may
use `BlobArtifactRef`, with a verified content hash and bounded size. A commit ID
is not a managed blob ID. Build-image digests and deployment references can have
their own typed contracts too. A verified change can reference a Git revision and
separate report/build artifacts, with evidence bound to that exact candidate.
Git is an optional capability plugin, not a platform-wide source protocol. Its
resolve/checkout operations use the same specifications, factories, construction
dependencies and typed invocation contracts as other integrations. No Git-specific
branches belong in the compiler, runtime, program definitions or execution engine.
Elements with other semantics remain free to return their own validated data.

The current implementation has managed-blob transfer, optional Git resolve/checkout
with local graph/code integration, and verification-plan/evidence-admission APIs.
Verification is an opt-in application capability: freeze an exact subject and
required checks, admit authenticated verifier receipts, and derive acceptance.
Workflow-scoped plan capabilities and registered request/inspect/cancel operations
compose with a reusable bounded wait program using the existing runtime timer port.
Candidate kinds remain extensible; other operation outputs use their own contracts.
An accepted receipt set is distinct from invocation completion. The first trusted
CI adapter now supports GitHub Actions dispatch, durable intent reservation,
reconciliation and exact-candidate evidence through ordinary operations and a
reusable waiting program. Its deterministic native tests do not establish live
GitHub execution. Optional required reports now carry a frozen provider manifest,
verified durable blob references and configuration provenance in immutable evidence.
Native audited intervention can attach a provider-confirmed run to an uncertain
intent without resubmitting work or supplying a verdict. Provider cancellation,
permanent absence/compensation, report/review UI, automatic run authority/lifecycle
binding, commit
publication/retention and remote source handoff remain implementation work.

Durable artifacts carry ownership, content identity, producing implementation and
input provenance, schema/type, retention, and authorized access. Repository change
sets identify the base revision. Tests/reviews attach to exact candidate content;
affected evidence is invalidated when the candidate changes.

Retry, replay, repair, resume, reconciliation, and compensation are distinct.
Consequential external effects use stable intent identities, input digests,
provider receipts/idempotency where supported, and provider-specific reconciliation.
When an outcome cannot be determined, preserve uncertainty instead of blindly
repeating a merge, release, or deployment. An outbox does not make an external
provider transaction atomic.

A bounded coding CLI invocation and a platform-coordinated durable agent loop have
different recovery granularity. Wrapping a CLI does not checkpoint every internal
tool call. Preserve that distinction in contracts and UI.

## Repository organization

Target layout; create/move modules when an implemented responsibility warrants it.
Preserve the current lib/adapters/bootstrap separation. Ports live near their
owning use cases. Avoid a global core or ports module containing unrelated code.

```text
UnifAI-ADLC/
|
+-- multi-agent/
|   |
|   +-- lib/
|   |   +-- mas/
|   |       +-- domain/
|   |       |   +-- elements/       # Definitions, references, bundles
|   |       |   +-- programs/       # Composition, bindings, revisions
|   |       |   +-- execution/      # Identities, outcomes, policies
|   |       |   +-- artifacts/      # Durable output contracts
|   |       |   +-- interactions/   # Decisions and review contracts
|   |       |   +-- adlc/           # Work items, evidence, acceptance
|   |       |
|   |       +-- application/
|   |           +-- elements/
|   |           |   +-- catalog/
|   |           |   +-- construction/
|   |           |   +-- invocation/
|   |           +-- resources/     # Saved-resource use cases
|   |           +-- programs/      # Authoring, validation, publication
|   |           +-- execution/     # Admission, submission, control
|   |           +-- interactions/  # Review and decision use cases
|   |           +-- artifacts/     # Publication and access
|   |           +-- sessions/      # Chat/session application behavior
|   |           +-- adlc/          # Reusable engineering policies
|   |           +-- capabilities/  # Shared provider-neutral behavior
|   |
|   +-- adapters/
|   |   +-- inbound/
|   |   |   +-- http_api/
|   |   |   +-- cli/
|   |   |   +-- webhooks/
|   |   |   +-- run_engine/         # Installed worker entrypoints
|   |   +-- outbound/
|   |       +-- run_engine/         # Compiler, runtime, gateway
|   |       +-- mongo/
|   |       +-- redis/
|   |       +-- artifact_storage/
|   |       +-- telemetry/
|   |
|   +-- plugins/
|   |   +-- mas_plugins/
|   |       +-- coding/
|   |       |   +-- codex/
|   |       +-- tickets/
|   |       |   +-- jira/
|   |       +-- source_control/
|   |       +-- ci/
|   |       +-- llms/
|   |       +-- retrieval/
|   |
|   +-- programs/                  # Installed reusable code programs
|   |   +-- mas_programs/
|   |       +-- review/
|   |       +-- delivery/
|   +-- templates/                 # Declarative reusable workflows
|   |
|   +-- bootstrap/                 # Composition root
|   |   +-- platform.py
|   |   +-- plugins.py
|   |   +-- programs.py
|   |   +-- receiver.py
|   |   +-- worker.py
|   |   +-- settings.py
|   |
|   +-- tests/
|       +-- domain/
|       +-- application/
|       +-- contracts/
|       +-- adapters/
|       +-- plugins/
|       +-- integration/
|       +-- e2e/
|       +-- architecture/
|       +-- support/
|
+-- ui/
|   +-- client/src/
|       +-- api/                   # Typed transport clients
|       +-- features/
|       |   +-- catalog/
|       |   +-- resource-editor/
|       |   +-- workflow-builder/
|       |   +-- execution-explorer/
|       |   +-- reviews/
|       |   +-- artifacts/
|       +-- shared/                # UI primitives, not workflow semantics
|
+-- docs/
    +-- architecture/
    +-- extensions/
    +-- operations/
```

Plugins are outer adapters; installed code programs are application compositions
using public contracts. Package discovery must be updated when new source roots
are introduced. Do not duplicate a provider implementation in plugins and adapters.

A small plugin may need only contracts.py, specification.py, factory.py, and
operation.py. Combine related code when clearer; extra client/mapper/validator
files are optional. Shared provider-neutral behavior stays in the library.

## Hexagonal dependency directions

This diagram describes source dependencies and interface ownership. Runtime
calls from use cases go through the outbound ports implemented by adapters.

```text
+----------------------------------------------------------------------------+
| INBOUND ADAPTERS                                                           |
| FastAPI | CLI | Webhook receivers | UI compatibility transport             |
+----------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------+
| APPLICATION USE CASES                                                      |
| Save draft | Publish | Start | Review | Replan | Accept work | Inspect     |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | DOMAIN                                                               |  |
|  | Program contracts | Bindings | Policy | Work outcomes | Decisions    |  |
|  +----------------------------------------------------------------------+  |
|                                                                            |
|  +----------------------------------------------------------------------+  |
|  | OWNED OUTBOUND PORTS                                                 |  |
|  | Execution | Artifacts | Repositories | Credentials | Integrations    |  |
|  +----------------------------------------------------------------------+  |
+----------------------------------------------------------------------------+
                                      ^
                                      | implemented by
+----------------------------------------------------------------------------+
| OUTBOUND ADAPTERS AND PLUGINS                                              |
| Run Engine | Mongo | Redis | Object storage | Git | Jira | Model SDKs      |
+----------------------------------------------------------------------------+
```

## Clean code, reliability, and scale constraints

- Enforce inward dependencies with import and cold-import architecture tests.
- Use cohesive classes for owned state, lifecycle, services, and strategies; keep
  pure mappings, predicates, and validation functions as functions.
- Use Pydantic for validated portable/configuration/API boundaries and enums for
  closed statuses/policies. Plugin identities remain extensible versioned keys.
- Use top-level imports, explicit injection, native async I/O, and scoped cleanup.
  Do not add request event-loop bridges or hidden service lookups.
- Keep explicit outputs/state writes and deterministic merge/conflict rules.
  Graph state is not a universal shared mutable blackboard or artifact store.
- Scope authority and credentials to required resources. Identity fields alone
  are not cryptographic capabilities. Enforce untrusted-plugin isolation outside
  cooperative Python state views.
- Enforce root-work budgets, tenant admission/fairness, provider limits, bounded
  concurrency/inboxes/payloads/history, and cleanup reconciliation. Per-run limits
  do not automatically establish tree-wide or physical concurrency bounds.
- Preserve distinct execution history, business audit, and operational telemetry;
  correlate them without claiming a cross-system transaction.
- Keep Run Engine's documented limits visible, including history continuation and
  adverse remote-failure coverage. Add engine features only for demonstrated gaps.

## Evolution and removal of replaced paths

| Phase | Deliverable | Completion evidence |
| --- | --- | --- |
| 1 | Shared program/operation contracts, source identities and UI mapping | API and UI express the same program semantics |
| 2 | Typed operation invocation, reusing construction | Deterministic and coding operations run from graphs and application programs |
| 3 | Durable artifacts and verification | Environment destruction does not lose required outputs or recovery state |
| 4 | Complete ADLC slice with durable review and external-effect reconciliation | Request -> implementation -> checks -> bounded repair -> review -> verified change proposal |
| 5 | Nested visual calls, Map, Repeat, Wait and occurrence inspection | Parallelism and iterations remain inspectable after restart |
| 6 | Controlled dynamic work | Authorized plan changes, fenced stale attempts and aggregate budgets |
| 7 | Production validation | Measured load/isolation, failure recovery, bounded history, compatible upgrades and cleanup |

Required product behavior remains in scope; old transports, formats, execution
paths, and import aliases are not preservation requirements.

The clean end state has one authoritative program model, one construction path,
one operation invocation path, one execution integration, and shared validation
semantics. Implement the canonical new contracts directly. Do not preserve a
second workflow language, old-format reader, forwarding module, dual API, or old
worker for backward compatibility.

For each replaced path: update current callers and tests, verify target behavior,
and remove superseded code, entrypoints, tests, documentation, recipes, and
dependencies. Old stored executions and prototype histories do not delay removal.
Release active test processes and owned resources safely; resource cleanup does
not require retaining legacy deployments.

Defer separate actor runtimes, unrestricted uploaded Python, a broker for every
call, a new scheduler, and speculative microservices until concrete requirements
justify them. These are not prerequisites for the agreed composition model.

## Architecture acceptance checklist

- [ ] A graph calls a code program, and a code program calls a graph.
- [ ] A reusable implementation/test/review program runs independently and inside
      a larger Jira-to-CI/CD workflow without modification.
- [ ] The first useful UI journey includes versioned feature design, authorized
      design approval/revision, actual coding, trusted checks, bounded repair and
      final review. Decisions and evidence identify the exact reviewed candidate.
- [ ] A new operation uses registration, schemas, factory, and the shared runner;
      it adds no integration-specific compiler branch or execution endpoint.
- [ ] Existing dependency references/builders construct transitive resources and
      clean up partially built scopes on failure/cancellation.
- [ ] UI and API share semantics; published revisions remain stable after edits.
- [ ] One evolved blueprint/program builder composes saved element resources and
      pinned graph/code programs, with inline control blocks and one executable model.
- [ ] The library discovers/configures reusable Programs and resources through
      coherent, semantically distinct flows; unfinished drafts can be saved.
- [ ] Structured manual, Session and trigger-based invocations open the same
      execution workbench; conversation is available when supported.
- [ ] Live visualization shows observed active/parallel work, nested occurrences,
      retries and waits; historical views use the executed revision, and connection
      loss cannot appear as completion. Deeper execution detail is paginated.
- [ ] Editing and inspection modes share clear visual structure, accessible status
      indicators and responsive interactions, verified in actual browser journeys.
- [ ] Definition expansion preserves pinned revisions and explicit caller upgrades;
      execution drill-down targets actual children/items/iterations/attempts, including
      observed calls from code programs without inventing an editable source graph.
- [ ] Conditions, loop bounds, parallel joins, and result bindings are validated.
- [ ] Runtime occurrences distinguish iterations, map items, children, and retries.
- [ ] Human Review works from graph and code programs; typed/authorized decisions
      survive API/worker restart and duplicates, expiry, cancellation, and replay.
- [ ] Operation HITL uses an explicit durable composition boundary when needed;
      no expensive invocation is retained solely for a workflow review wait.
- [ ] Paused/awaiting behavior and Local versus Temporal guarantees are explicit.
- [ ] Durable artifacts survive environment destruction and evidence identifies
      the exact candidate; agent self-reports cannot satisfy trusted checks alone.
- [ ] Reusable Engineering Programs accept compatible configurable deliverable and
      completion contracts; Git-specific behavior stays in integrations/ADLC policy.
- [ ] Invocation choices stay within declared contracts; supported requirement
      amendments are recorded and authorized without reinterpreting old evidence.
- [ ] Lost external acknowledgements reconcile without uncontrolled duplicate effects.
- [ ] Isolation, budgets, stale-attempt fencing, cleanup, and upgrade behavior have
      evidence from real adapters and required load/failure scenarios.
- [ ] Domain/application tests use owned ports; shared contracts exercise adapters;
      E2E covers the real UI/API/worker path and infrastructure boundaries.
- [ ] Profile preferences, overrides, named bindings, and effective placement survive
      UI save/reload, publication, nested calls, and execution recovery.
- [ ] Explicit child imports preserve environment ownership; borrowed environments
      survive child completion and owned environments release on all terminal paths.
- [ ] Unsupported or unauthorized placement fails before dispatch, with no silent
      fallback or leakage of backend settings/credentials into public contracts.
- [ ] Superseded paths, compatibility scaffolding, misleading skills, and obsolete
      dependencies are removed; only the canonical new platform remains.

The first proving scenario is an independently reusable Implement Verified Change
program, embedded unchanged in a larger workflow, combining typed operations,
bounded repair, durable review, verified artifacts, and observable nested execution.
