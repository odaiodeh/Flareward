# Unified coordinators and composable Programs

Accepted milestone design: 2026-11-11. Implementation is in progress.

**A Program selects and configures a coordinator implementation.** Graph coordination
comes from Run Engine; other coordination behavior comes from plugins. All Programs
share contracts, publication, composition, placement and execution inspection.

This README is the detailed specification for this milestone. The
[parent architecture](../README.md) defines the whole platform and its remaining
obligations. [Status](../../status.md) records current facts; [the plan](../../plan.md)
records the active implementation step. [Checkpoint evidence](../../evidence/2026-11-11-coordinator-foundation.md)
is scoped to the source tested, not acceptance of this complete design.

For routine work, read status/plan and the sections relevant to the active step;
review the full acceptance criteria at milestone boundaries.

The diagrams below describe the target. The baseline table at the end identifies
what is implemented. Named contracts describe responsibilities; introduce a class
only when its ownership and behavior justify it.

## 1. Public mental model and construction

| Concept | Responsibility | Example |
| --- | --- | --- |
| Element | Installed specification, configuration schema, factory, dependency requirements and capability contracts | Coding agent, provider, test runner |
| Resource | Saved Element configuration with construction dependency references | A configured Codex agent |
| Operation | Executable Element with typed input/output and one invocation scope | Produce a candidate, fetch a ticket, run a check |
| Coordinator specification | Installed coordination identity/version, configuration, interfaces and declared Program dependencies | Graph, Repeat, Engineering |
| Program | Configured reusable coordination with a public interface, dependencies and execution settings | An engineering workflow |
| Published revision | Immutable Program definition, interface and dependency closure | Engineering revision 3 |
| Execution | Invocation of a published revision or an owned body addressed within that revision | Root delivery run or a nested attempt |

An owned body has no separate library identity. Its source is the enclosing
revision plus body path. A Session optionally retains interaction around executions.
Blueprints/templates are imported authoring data using the same Program lifecycle.

```text
+--------------------------------------------------------------------+
| INSTALLED CAPABILITIES                                             |
|                                                                    |
| Element specification              Coordinator specification       |
| Schema, factory, dependencies      Config, IO, dependencies        |
+---------------+------------------------------------+---------------+
                |                                    |
                | configure                          | configure
                v                                    v
+------------------------------+    +--------------------------------+
| RESOURCE                     |    | PROGRAM                        |
| Saved capability settings    | -> | Frozen capability dependencies |
| Construction references      |    | Coordinator configuration      |
+------------------------------+    | Public IO and Program bindings |
                                    +--------------------------------+
                                                     | publish + run
                                                     v
                                    +--------------------------------+
                                    | EXECUTION                      |
                                    | Inputs, results and reviews    |
                                    | Children and evidence          |
                                    +--------------------------------+
```

The horizontal arrow means use of a captured configuration, not a live Resource
lookup during execution. Factories/builders construct dependencies in an invocation
scope and release owned clients/resources. Programs coordinate that work. An
Operation can contain sophisticated agent logic; lifecycle, not implementation
size, distinguishes it from a Program.

## 2. Coordinator specifications and extensibility

Evolve the existing registry and plugin manifest convention. One specification
convention describes identity/version, typed configuration, public interfaces,
expected Program dependencies and safe authoring capabilities. Graph is the native
coordinator implementation supplied through the Run Engine adapter.

```text
+--------------------------------------------------------------------------+
| COORDINATOR IMPLEMENTATIONS                                              |
|                                                                          |
| Graph              Repeat             Map             Human Review       |
| Steps and edges    Bounded iteration  Parallel calls  Durable wait       |
| Routes and joins   over a body        over items      and decision       |
|                                                                          |
| Engineering                           Other plugin coordinators          |
| Domain-specific acceptance logic      Reusable coordination              |
+--------------------------------------------------------------------------+
```

- Graph configuration remains typed: topology, routes, joins, data bindings and
  graph-specific invariants. Configuration is interpreted by native graph behavior.
- Custom coordinators have typed configuration and cohesive Python behavior. They
  invoke effects, children, timers and messages through Lumora-owned runtime ports.
- Common specification metadata does not require identical Python entrypoints.
  Native graph integration and plugin invocation remain different adapter concerns.
- A typed discriminator inside implementation handling is legitimate. Shared
  callers must obtain contracts/dependencies without inspecting that discriminator.
- A developer adding a coordinator using existing runtime capabilities registers
  its specification and implementation. Unrelated publication, composition and
  execution services should not require edits.
- A genuinely new execution mechanism may require an explicit adapter capability.
  Do not build a universal interpreter or handler framework for speculative needs.
- Configuration selects installed behavior. YAML/JSON can serialize the canonical
  definition; it does not deploy arbitrary Python or establish another runtime.

Use the existing enabled plugin manifests. Preserve Element discovery, factories,
category builders and transitive bundle validation. Do not introduce a parallel
registry, uncontrolled filesystem execution or a shared superclass that forces
Element construction and Program coordination into the same lifecycle.

### Explicit execution strategies

Implemented refinement: [verification](../../evidence/2026-11-12-coordinator-strategies.md).

`CoordinatorRegistration` owns common identity, configuration and invocation-model
metadata. Its required `strategy` is `NativeGraphStrategy()` or
`CustomCoordinatorStrategy(entrypoint)`. The native variant has no Python
entrypoint; the custom variant validates its async entrypoint at registration.
The catalog kind is derived from the strategy, so it cannot disagree with it.
Native graph identity/schema and custom registrations cannot be interchanged.

Plugins export `COORDINATORS`; custom Program configuration uses
`CustomCoordinatorDefinition`, and the async behavior contract is
`CoordinatorEntrypoint`. The existing serialized `kind: application` discriminator
identifies custom configuration; it does not define a separate Program lifecycle.
`CoordinatorCall` is the adapter-owned portable custom call. Both strategies still
compile into the same `execute_program` boundary. No engine types enter these
application-owned strategy declarations.

## 3. Program dependencies, bindings and composition

Use **Program dependency** in the UI. The internal concepts are:

| Concept | Meaning |
| --- | --- |
| Declared dependency | Caller-owned name and expected input/output contract, possibly resolved from configuration |
| Configured binding | Selected pinned Program revision or owned inline body, with explicit environment imports |
| Invocation | Concrete input plus a stable occurrence identity for one call |

```text
+--------------------------------------------------------------------------+
| ENGINEERING PROGRAM                                                      |
| Logic: produce candidate -> call "reviewer" -> inspect outcome           |
| Dependency: reviewer expects candidate input and review output           |
| Binding: reviewer -> security-review, revision 3                         |
+----------------------------------+---------------------------------------+
                                   | invoke
                                   v
+--------------------------------------------------------------------------+
| SECURITY REVIEW PROGRAM                                                  |
| Graph or custom coordinator behind the same published interface          |
+--------------------------------------------------------------------------+
```

Changing the configured reviewer to a compatible Human Review Program must not
require changing Engineering's coordination code. Compatibility is based on actual
contracts, including required result fields and intended decision semantics.

Support graph -> graph, graph -> custom, custom -> graph and custom -> custom.
A reusable Program can run independently or nested without modifying its revision.
A child is an execution relationship, not a separate category of Program.

Keep these relationships separate:

- Construction dependencies: capabilities to build from frozen resource bundles.
- Program dependencies: admitted Program targets the coordinator may call.
- Ordering: graph topology or custom coordination logic.
- Data bindings: graph projections or typed requests built by coordinator code.
- Placement: approved profiles and explicit environment bindings.

Consolidate target/import metadata and source diagnostics without forcing graph
state projections onto Python coordinators. Avoid two independent editable copies
of the same dependency. Preserve aliases/body paths when updating targets.

Published references are pinned; owned bodies freeze with the parent. Publication
checks ownership, completeness and reference cycles. Admission prepares the pinned
closure. This milestone does not authorize selecting arbitrary undeclared Programs
at runtime or adding recursion. Choose selects declared targets; Map/Repeat invoke
declared bodies with bounded dynamic cardinality.

## 4. Publication and authoritative invocation interfaces

```text
+--------------------------------------------------------------------------+
| AUTHORING AND PUBLICATION                                                |
|                                                                          |
| Select coordinator -> configure behavior -> select Resources             |
|   -> bind Program dependencies -> resolve input/output interface         |
|   -> configure placement/imports -> validate -> publish revision         |
+--------------------------------------------------------------------------+
```

Allow safe incomplete drafts. Required shape, identity, ownership, credential
protection and supplied-value checks still apply. Publishing requires complete
configuration, valid topology where relevant and compatible dependencies.

Saved-resource selection must work consistently for graph and custom coordinator
configuration through the existing authorized snapshot/protection services. Capture
transitive dependencies; never turn redacted browser configuration into executable
credentials. Resource edits do not silently change published Program behavior.

Resolve and freeze a public invocation interface for each revision. Describe:

1. The raw input JSON shape accepted at the Program boundary.
2. Deterministic normalization/default/alias behavior and its implementation identity.
3. The normalized request contract when it differs from raw intent.
4. The serialized result shape callers can consume.

The UI, composition checks and runtime must use that revision's resolved interface.
Custom validators and serializers remain implementation behavior and require
runtime enforcement; do not claim full static proof of arbitrary Python semantics.
Preserve input normalization deliberately, and version any intentional change in
accepted behavior. Keep code/models installed; portable definitions carry data and
approved identities, not live objects.

Do not blindly combine schemas with `allOf`: raw input validation followed by
Pydantic normalization differs from intersecting two raw-input schemas, and nested
local references need preserved resolution scope. Validate configured refinements,
reject proven contradictions before dispatch, and enforce concrete values at
runtime. Schema uncertainty must not be reported as proven compatibility.

Business outcomes such as approved, changes_required or iteration_limit_reached
are typed results. A successful execution returning an unsatisfied outcome does
not establish accepted work. Contract failures and infrastructure failures retain
explicit failure semantics.

## 5. Ownership and hexagonal boundaries

```text
+--------------------------------------------------------------------------+
| UI / API                                                                 |
| Programs library | Resources | Workspace | Executions | Reviews          |
+----------------------------------+---------------------------------------+
                                   | application use cases
                                   v
+--------------------------------------------------------------------------+
| LUMORA                                                                   |
|                                                                          |
| Domain: definitions, identities, interfaces and invariants               |
| Application: authoring, publication, authorization and admission         |
| Services: resource capture, review, verification, artifacts              |
| Execution views: authorized snapshots, events and controls               |
|                                                                          |
| Owned ports: runtime, execution gateway, repositories, capabilities      |
+----------------------------------+---------------------------------------+
                                   | calls through ports
                                   v
+--------------------------------------------------------------------------+
| ADAPTERS                                                                 |
| Run Engine: graph lowering and custom coordinator preparation            |
| Persistence | External protocols | Observation translation               |
| Composition root selects and wires implementations                       |
+----------------------------------+---------------------------------------+
                                   v
+--------------------------------------------------------------------------+
| RUN ENGINE                                                               |
| Graph traversal | Invocations | Children | Messages and timers           |
| Recovery | Cancellation | Environment lifecycle | Execution journal      |
+----------------------------------+---------------------------------------+
                                   v
+--------------------------------------------------------------------------+
| INFRASTRUCTURE                                                           |
| Temporal | Workers | Threads/processes | Kubernetes | OpenShell          |
+--------------------------------------------------------------------------+
```

These arrows show runtime calls. Source dependencies point toward application-owned
ports: adapters implement them. Domain/application contracts exclude engine SDK,
HTTP, database and Kubernetes/OpenShell types. Feature-local domain directories and
ports/services retain the existing repository organization.

Coordinator plugins depend on Lumora runtime contracts. Operation implementations
own their work and depend on narrow capability ports where a replaceable external
integration warrants one. Core application code does not import concrete plugins.
Only the composition root chooses implementations. Run Engine owns physical
execution and durability; Lumora owns authority, business policy and acceptance.

Use minimal idiomatic Python, cohesive classes where justified, explicit injection,
Pydantic at meaningful boundaries and enums for closed policies/statuses. Keep
imports at module scope. Use async I/O and owned cancellation/cleanup; keep pure
computation and constructors synchronous. Apply the same rules to tests. Remove
superseded implementations and misleading guidance after migrating useful behavior.

## 6. Runtime lifecycle and placement

The current integration submits `RunRequest(execute_program, payload)` for both
mechanisms. PreparedGraph and PreparedCoordinator are adapter-owned payload types.

```text
UI             Lumora application       Run Engine          Operation
 |                     |                     |                  |
 | Run revision        |                     |                  |
 |-------------------->|                     |                  |
 |                     | Validate authority  |                  |
 |                     | Freeze placement    |                  |
 |                     |                     |                  |
 |                     | Submit RunRequest   |                  |
 |                     |-------------------->|                  |
 |                     |                     | execute_program  |
 |                     |                     | delegate to graph|
 |                     |                     | or custom logic  |
 |                     |                     |                  |
 |                     |                     | Invoke capability|
 |                     |                     |----------------->|
 |                     |                     | Construct -> run |
 |                     |                     | -> release scope |
 |                     |                     |<-----------------|
 |                     |                     | Typed result     |
 |                     |                     |                  |
 |                     |                     | Start child when |
 |                     |                     | a Program calls  |
 |                     |                     | another Program  |
 |                     |                     |                  |
 | Inspect execution   | Observe through port|                  |
 |-------------------->|-------------------->|                  |
 |                     |<--------------------|                  |
 |<--------------------| Authorized view     |                  |
 |                     |                     |                  |
 |                     |                     | Validate result  |
 |                     |                     | Close owned scope|
 | Result and evidence |<--------------------|                  |
 |<--------------------|                     |                  |
```

Calling native `run_graph` delegates within the current execution; it does not
create an extra child merely because the implementation is a graph. Calling another
Program creates a child scope with its own identity and cancellation lifecycle.
Coordinator effects and decisions requiring external I/O run through recorded
invocations. Replay must not silently rerun an LLM decision outside those effects.

Placement is independent of coordinator behavior:

- Distinguish coordination host (for example Local/Temporal) from Operation runner.
- Program defaults choose approved placement; calls can select other approved
  profiles or named environments. Thread/process runners need not be sandboxes.
- Selecting the same profile does not imply sharing a physical environment.
- Named environments express reuse; child imports explicitly grant borrowed access.
- Owned, borrowed and external environments have different deletion authority.
  A borrower cannot acquire ownership implicitly or delete the parent's environment.
- Run Engine controls allocation and release. Lumora checks policy and freezes
  admitted settings. Test terminal and relevant adverse cleanup and cancellation.
- Credentials use scoped capability bindings; do not place raw secrets in definitions,
  results, observation events or browser data. Preserve existing credential controls.

## 7. Nested workflow and Human Review

```text
+--------------------------------------------------------------------------+
| DELIVERY PROGRAM                                                         |
| Fetch task -> Design -> Improve -> Human approval -> Release             |
|                           |                                              |
|                           v                                              |
|             +----------------------------------------+                   |
|             | REPEAT PROGRAM                         |                   |
|             | Bounded iterations until accepted      |                   |
|             |                                        |                   |
|             | +------------------------------------+ |                   |
|             | | ATTEMPT PROGRAM                    | |                   |
|             | | Code -> Test -> Review -> Outcome  | |                   |
|             | +------------------------------------+ |                   |
|             +----------------------------------------+                   |
+--------------------------------------------------------------------------+
```

This illustrates composition; it does not claim current live Jira/CI/CD acceptance.
Delivery may be a graph, Repeat a plugin coordinator, Attempt either implementation,
and Release another reusable Program. Graph cycles revisit work within one graph
execution. Repeat starts a child execution for each iteration. Map bounds outstanding
child calls; its concurrency setting does not replace root work/resource budgets.

Generic result-based graph routing must work without mandatory MAS state. Preserve
useful MAS nodes/conditions behind explicit state adapters. Define small typed
routing predicates or conditions with clear unknown-label behavior rather than
introducing an unrestricted expression language. The implemented `ResultRoute`
selects labels from typed Operation/Program results using normal bindings;
`ConditionalRoute` retains saved condition Elements and their explicit state adapter.
Both lower to native conditional edges. See [local/API/client verification](../../evidence/2026-11-11-result-routing.md).

Human Review is a reusable Program where independent configuration, publication,
replacement and inspection are needed. ADLC binds it as a dependency instead of
importing the concrete review coordinator. Ordinary helper calls do not all need
child scopes. Keep generic review contracts independent of ADLC-specific subjects.
A returned approval-shaped value is a claim, not authoritative review evidence.
Callers confirm the returned review ID through the scoped review service against
an expected policy, exact subject and the invoked reviewer's execution subtree.
This permits graph/custom reviewers to delegate internally while rejecting an
unrelated occurrence or substituted work. Confirmation uses an ordinary Operation,
not a compiler special case. The [confirmation capability](../../evidence/2026-11-11-review-confirmation.md)
and the ADLC migration are implemented: Design 2 and Engineering 4 declare reviewer
dependencies and confirm persisted results. Local replacement and migrated Temporal restart/continuation/cancellation now have
[C6 acceptance](../../evidence/2026-11-12-adlc-review-recovery.md); broader remote
lifecycle and credential recovery remain separate obligations.

```text
ADLC Program       Review Program      Review service       Human / UI
     |                   |                  |                   |
     | Call reviewer     |                  |                   |
     |------------------>|                  |                   |
     |                   | Invoke request   |                   |
     |                   |----------------->|                   |
     |                   | Review identity  |                   |
     |                   |<-----------------|                   |
     |                   | Native wait      | Pending review    |
     |                   |                  |------------------>|
     |                   |                  | Submit decision   |
     |                   |                  |<------------------|
     |                   | Wake/reconcile   | Persist decision  |
     |                   |<-----------------|                   |
     |                   | Invoke inspection|                   |
     |                   |----------------->|                   |
     |                   |<-----------------|                   |
     | Typed decision    |                  |                   |
     |<------------------|                  |                   |
```

Service interactions in this diagram occur through invoked Operations. Run Engine
owns waits and continuation. Lumora owns reviewer authority, response schemas,
exact subject identity, decisions, expiry and supersession. Wakeups are hints;
reconcile the authoritative review record. Handle duplicates, stale responses,
restart and cancellation. Approval of one candidate must not approve a replacement.

Coding agents can manage Git internally. Commits, immutable files, patches and
reports can identify produced work. Branch names must resolve to the exact revision
being checked where required. Verification and acceptance are configured ADLC policy;
Git is optional. Retain required deliverables before temporary compute is deleted.

## 8. Unified authoring and execution UI

Use the existing React Flow canvas, schema editors, resource pickers, Program
library and shared execution routes. Preserve valuable session/review/streaming
components and evolve their layout; do not restore a competing authoring runtime.

```text
+--------------------------------------------------------------------------+
| PROGRAMS LIBRARY                                                         |
| Discover -> create/configure -> save draft -> validate -> publish        |
+----------------------------------+---------------------------------------+
                                   v
+--------------------------------------------------------------------------+
| PROGRAM WORKSPACE                                                        |
| Interface | Design | Dependencies | Placement | Revisions                |
|                                                                          |
| Graph: canvas and bindings       Repeat/Map: bounds and body             |
| Custom: configuration and declared Program dependencies                  |
| Any compatible Program can be a graph block                              |
+----------------------------------+---------------------------------------+
                                   | invoke selected revision
                                   v
+--------------------------------------------------------------------------+
| EXECUTION WORKBENCH                                                      |
| Hierarchy | Graph overlay or call timeline | Reviews | Results           |
| Exact source revision | Placement | Evidence | Authorized controls       |
| Delivery > Improve > Iteration 2 > Attempt > Review                      |
+--------------------------------------------------------------------------+
```

Inline Map/Repeat/Choose/Wait controls create ordinary owned Program bodies. Users
should not have to publish a helper Program for each control block. Open a nested
graph on its canvas; open a custom coordinator's configuration/dependencies without
fabricating an editable graph for its Python internals. An optional visual summary
is presentation metadata and must not define execution semantics.

Initial [child call-site correlation](../../evidence/2026-11-12-call-sites.md)
is implemented: authored dependency names and actual child IDs are recorded.
[Operation/Program occurrences](../../evidence/2026-11-12-occurrences.md), graph attempts
and child links now appear in the shared workbench. Retention is bounded and explicit;
waits, resumable updates, graph overlays and full nested editing remain open.

Definition expansion follows owned bodies and pinned references. Execution drill-down
follows actual occurrences and child IDs. Editing reusable work creates a draft/new
revision; adoption by callers is explicit. Historical views show what actually ran.
Schema-driven input forms use the selected published revision. Conversation is an
explicit projection; it is not mandatory for every Program.

The observation contract distinguishes authored call site, logical occurrence,
attempt, child execution, wait and result. Reusing a node UID or hashing a key is
insufficient to identify all these relationships. Use structured metadata correlated
with authoritative opaque engine IDs. Do not change idempotency keys solely to
make them readable. Lifecycle observation must survive replay, cancellation and
children whose results are not immediately awaited.

Lumora translates engine observations into authorized, paginated snapshots and
resumable updates. Handle gaps, unknown state and disconnection explicitly. Avoid
duplicate lifecycle truth derived only from best-effort wrapper events. Inspect
public engine contracts first; document any generic missing capability and its
acceptance criteria before changing the companion project.

Show active branches, loop iterations, attempts, pending reviews and actual outcomes.
Separate engine completion from verified acceptance. Preserve an elegant coherent
workspace with accessible status labels, keyboard alternatives, readable contrast
and progressive disclosure. Canvas gestures do not implement scheduling or policy.

## 9. Source ownership and baseline checkpoint

Paths below identify existing code, not a requirement to preserve every current
class name. Keep the feature-owned repository organization.

| Responsibility | Starting point |
| --- | --- |
| Definitions, body paths and dependency values | [programs/domain/models.py](../../../platform/src/lumora/programs/domain/models.py) |
| Coordinator registration/catalog | [programs/registry.py](../../../platform/src/lumora/programs/registry.py), [bootstrap/programs.py](../../../platform/src/lumora/bootstrap/programs.py) |
| Draft/publication and contract admission | [programs/service.py](../../../platform/src/lumora/programs/service.py), [contracts.py](../../../platform/src/lumora/programs/contracts.py) |
| Caller interface resolution | [programs/signatures.py](../../../platform/src/lumora/programs/signatures.py) |
| Runtime port and custom invocation | [programs/ports.py](../../../platform/src/lumora/programs/ports.py), [invocation.py](../../../platform/src/lumora/programs/invocation.py) |
| Native preparation/delegation | [outbound/compiler.py](../../../platform/src/lumora/executions/adapters/run_engine/outbound/compiler.py), [inbound/programs.py](../../../platform/src/lumora/executions/adapters/run_engine/inbound/programs.py) |
| Portable prepared variants | [shared/models.py](../../../platform/src/lumora/executions/adapters/run_engine/shared/models.py) |
| Reusable composition | [programs/composition](../../../platform/src/lumora/programs/composition) |
| Capability construction and snapshots | [elements/construction](../../../platform/src/lumora/elements/construction) |
| Concrete review and ADLC behavior | [plugins/human_review](../../../platform/src/plugins/human_review), [plugins/adlc](../../../platform/src/plugins/adlc) |
| Authoring and execution UI | [features/programs](../../../ui/client/src/features/programs), [components/executions](../../../ui/client/src/components/executions) |

Baseline as of the 2026-11-11 foundation checkpoint:

| Outcome | State at checkpoint |
| --- | --- |
| Shared Program lifecycle and graph/custom runtime composition | Implemented, with scoped native evidence |
| One coordinator catalog including graph@1 and UI selection | Implemented |
| Shared dependency projection and child preparation | Implemented; authored storage still has different representations |
| Central caller interface resolution | Implemented; complete published-interface resolution remains |
| Typed prepared graph/coordinator payloads | Implemented, Program entrypoint v7 |
| Human Review result model | Declared; ADLC still calls concrete review behavior in process |
| Resource-selection parity and generic routing independent of MAS | Incomplete |
| Full dependency authoring, inline controls and nested canvas | Incomplete |
| Structured occurrence history and full workbench | Incomplete |
| Current-source full browser and rebuilt remote acceptance | Pending for this complete milestone |

Update current state in status/plan and evidence; keep this table identified as the
baseline. Neither renaming classes nor passing existing tests completes the target.

Current implementation update: [published-interface evidence](../../evidence/2026-11-11-published-interfaces.md)
records immutable raw/model/canonical schema snapshots, caller checks, admission,
Program v8 worker enforcement and production client verification. This advances C2;
the remaining authoring and full milestone gates remain open. The baseline table above describes the earlier foundation snapshot.

[Resource-capture evidence](../../evidence/2026-11-11-configuration-resources.md) records
save/adoption parity for typed nested coordinator bundle fields and owned bodies,
existing-picker integration, and real graph/custom thread/process execution. This
advances C3; it does not certify the later full nested-canvas or remote gates.

[Configured-contract evidence](../../evidence/2026-11-11-configured-contracts.md)
adds frozen configuration refinements, portable custom dependency expectations,
Program v9 pre-effect drift enforcement and real API/client verification. This
advances C2/C4. [Step A acceptance](../../evidence/2026-11-11-coordinator-step-a.md)
adds unsaved interface/dependency discovery, the integrated editor and a contract audit.
Step B review composition/routing is active; full browser/remote gates remain in C/D.
The earlier v7/v8 records retain their historical source scope.

## 10. Delivery order and verification gates

Work backend-led with thin UI integration as contracts stabilize. Architectural
quality and required safeguards apply continuously. Keep one active implementation
step in the plan; queue unrelated improvements while preserving the overall goal.

| Step | Deliverable | Verification boundary |
| --- | --- | --- |
| A | Resolve published interfaces, specification/dependency semantics and resource selection | Focused domain/application tests, actual API/client publication and rejection cases |
| B | Complete review-as-child adoption and generic routing; mixed reusable workflow | Local thread/process composition and a coherent Temporal replay/restart gate |
| C | Occurrence correlation, nested/control authoring and shared execution inspection | Observation contracts, production client checks and actual browser journey |
| D | Current-source milestone acceptance and cleanup | Rebuilt Kubernetes/OpenShell receivers, relevant host/backend lifecycle tests, end-to-end evidence and documentation |

Run focused tests while changing each capability. Do not defer contract, authority
or cancellation checks until the end. Batch expensive Docker builds, Temporal
recovery, remote matrices and full browser suites at coherent boundaries; rerun
when changed installed code or failures invalidate evidence. Freeze tested source
while a gate runs. Historical image/test results do not certify new payloads.

Use Lumora's dedicated infrastructure and shared scenario/adapter fixtures. Normal
OpenShell sandbox configuration is sufficient for ordinary acceptance; optional
kernel-specific isolation tests remain separate. Keep paid model scenarios explicitly
opt-in, use private credential bindings, and record deterministic versus live scope.
An engineering workflow made only of fixtures does not certify real agent behavior.
Reuse recorded real-agent evidence only when its implementation scope still applies.

Checkpoint reports are progress updates. Continue through the remaining accepted
work without treating each checkpoint as a new permission boundary. When this
milestone passes, continue the larger goal's delivery and operational milestones.

## 11. Milestone completion criteria

Each criterion requires current implementation and appropriately scoped evidence.
Keep the compact mapping in the existing plan/evidence system, not another ledger.
C1-C4 have [Step A local/API/client acceptance](../../evidence/2026-11-11-coordinator-step-a.md),
and C7 has [result-routing acceptance](../../evidence/2026-11-11-result-routing.md);
this does not certify the later full browser, remote, recovery or capacity gates.

- [x] C1: Graph and plugin coordinators use one catalog and Program lifecycle;
  adding a compatible custom coordinator does not edit unrelated core services.
- [x] C2: Published interfaces and normalization semantics drive caller checks,
  UI invocation and runtime validation, including aliases, nested references,
  non-object values, invalid output and incompatible dependency cases.
- [x] C3: Saved resources and transitive dependencies can be selected for both
  implementations; published snapshots, ownership and secret protection hold.
- [x] C4: Declared Program bindings consistently handle pinned/owned targets,
  source diagnostics, explicit imports, unchanged reuse and all four compositions.
- [x] C5: A delivery graph calls a bounded Repeat whose body performs coding,
  testing and review; [controlled Local/thread/process evidence](../../evidence/2026-11-12-mixed-delivery.md)
  covers success, repair and bounded unsatisfied outcomes.
- [x] C6: ADLC Human Review is replaceable through a compatible dependency;
  exact-subject decisions, cancellation, restart and continuation have
  [Local/Temporal evidence](../../evidence/2026-11-12-adlc-review-recovery.md).
- [x] C7: Generic graph routes operate on typed results without requiring MAS
  channels; existing specialized MAS behavior remains explicitly supported.
- [ ] C8: The UI authors inline controls/nested bodies, publishes and runs them,
  and drills into actual iterations/attempts/children with authoritative statuses.
- [ ] C9: Profiles, environment reuse/imports, borrower ownership and relevant
  terminal/adverse cleanup are proven with matched current remote images.
- [ ] C10: Replaced paths and misleading guidance are removed; source, packages,
  startup/worker instructions, READMEs and focused evidence agree.

Full root-scale fairness, remaining credential/private-delivery work, external
Jira/CI/CD deployment acceptance and the larger operational matrix remain obligations
of the parent architecture/goal. This milestone preserves them and does not claim
that its passing subset completes the platform.

## Goal reference

The goal should reference this file rather than duplicate the full design:

> Finish the unified coordinator and Program milestone specified in
> docs/architecture/coordinator-programs/README.md. Treat its contracts, ownership
> boundaries and C1-C10 criteria as required acceptance. Reconcile current source
> and scoped evidence; continue beyond intermediate checkpoints. Work backend-led
> with focused verification during implementation and batched heavy gates at the
> defined boundaries. Preserve all existing SOLID, hexagonal architecture, code
> quality, security, testing and cleanup requirements. After this milestone is
> accepted, continue the remaining overall goal and plan obligations.
