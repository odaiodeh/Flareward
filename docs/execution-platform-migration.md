# Execution platform migration

Implementation follows the program-platform objective supplied in this chat.
Completion requires the full migration, not only the first passing vertical slice.

## Current implementation queue (2026-10-30)

This section is the current work order; dated sections below retain historical
evidence. The full goal is active. Do not infer repository-wide architectural
perfection or absence of dead code from passing tests in the migrated core.

Latest combined gate: **627 passed**, zero failures/errors/skips or reported
warnings, in 249.38 seconds. It includes SDK `6039344`, strict label routing,
native async actions and invitation notifications, real Mongo/Redis/Temporal,
separate API/worker processes and production TypeScript API clients. Remote
programs, OpenShell policy and paid Codex modules were excluded; remote-image
evidence is recorded separately below.
JUnit: `/tmp/unifai-native-notifications-platform-20261030.xml`.
This supersedes the 611-case action gate and its subsequent focused fix for the
current nonremote source. It does not establish completion of the migration.

### Mandatory migration work, in order

| Order | Work | Acceptance evidence |
| --- | --- | --- |
| 1 | Completed: condition contracts and routing SDK adoption | Threshold input paths/read declarations/configuration and application result validation are corrected. Built-in branch/rejoin contracts pass locally and selected separate-worker Temporal histories replay. Committed SDK ACTIVE joins adopted at `da10d1ac`; 45 UnifAI condition/blueprint/Temporal replay cases pass. Owner reports broader checkpoint/upgrade/regression gates. Strict-label commit `6039344` is adopted explicitly; 232 SDK routing/join cases pass with native Temporal. The current UnifAI gate passes 589 cases and matched strict-label receivers pass 28 remote cases across both hosts/backends. The prior join commit also passed 8 OpenShell policy cases. Exact evidence and upgrade limits are below. Worker-loss/concurrent-coding/Celery gaps remain separate. |
| 2 | Finish placement browser coverage in full workspace flows | Resource preferences, workflow defaults, independent node/condition overrides and named run environments survive authoring/publication/sessions. Production dialog and full App checks cover profile save/reload, delayed type changes, editor leases, native model/reasoning discovery and personal/team invitation decline/reload using signed cookies and a synthetic upstream membership service. Next finish share creation/acceptance/copy (row 3), full workflow authoring/navigation and account/session callback lifetimes; no OAuth claim. Keep placement outside element config and raw SDK settings outside public UI contracts. |
| 3 | Complete remaining required FastAPI/client parity | Native async action discovery/execution and notification list/details/decline/cancel are implemented; full App notification reads/declines are verified. Next migrate share creation/acceptance/team copy with typed owner checks, validated dependency closure, secret treatment and recoverable partial failures; review arbitrary Unicode legacy user-alias discovery before cutover. Also finish shared-chat authorization, collaboration/presence, administrative transitions/cascades, credential onboarding/callbacks, schedule clients/migration and required reporting/cost endpoints. Resource/blueprint edit leases and dotted validation compatibility are implemented. Native services own policy and thin routers translate transport. Browser session/workspace changes must not let old callbacks mutate a new view. |
| 4 | Deliver the requested Human Review element | A normal registered schema/spec/factory element with validated expected response, authorized reviewer, stable occurrence identity and typed outcomes. Test wait/restart, rejection, expiry, cancellation, duplicates and routing using engine primitives. Keep tool auto-approval rules separate from workflow review. Do not add an agent orchestration framework. |
| 5 | Finish package ownership and plugin cleanup | Consolidate remaining program/session/resource contracts and services into their proper domain/application boundaries; keep concrete integrations as adapters. Preserve factories, category builders and useful existing behavior. Remove unused facades, redundant abstractions and replaced code only with reference/reachability and compatibility evidence. Preserve installed portable references and old histories during moves. |
| 6 | Close deployment, security and recovery validation gaps | Remote worker loss/replacement, cancellation and uncertain cleanup on Kubernetes/OpenShell; remote approval transport; concurrent Codex isolation; optional SDK-agent and bounded live Gemini cases; verify supported Celery deployment. Complete encryption/old-credential retirement, profile policy, deployment transport/access controls and secret provisioning. Pin production worker/image implementations and verify upgrade/replay compatibility. |
| 7 | Cut over defaults and drain legacy infrastructure | Switch startup/container commands and all required clients after parity. Migrate or drain legacy executions/schedules before removing their workers, Flask execution endpoints, old bridge/runner paths and related dependencies. Verify actual drain state; file age or apparent lack of imports is insufficient. |
| 8 | Final requirement-by-requirement audit | Current-source tests, complete required E2E/browser matrix, import/cold-import checks, meaningful typing/lint/dead-code audit, deployment instructions, extension guides and tested skills agree. Mark the goal complete only when all original and accepted additional requirements have evidence. |

Quality review applies within every row, not only row 8. Existing passing slices
include program composition, bundles, session/identity handling, native async
execution, tool approvals, scoped persistent rule updates, replay and basic remote
environment ownership. They do not close the unfinished product/API or drain work.

### Classes, functions and minimal code

Use cohesive classes for services with injected dependencies, resource ownership,
domain entities, interchangeable strategies and plugin contracts. Keep useful
specifications, factories, category builders and small application-owned ports.
Keep pure bindings, reducers, validation and normalization as module functions
when they have no instance state or lifecycle. A static-method-only wrapper does
not improve SOLID; class relationships must express a real responsibility.

Use enums for closed policies/statuses/outcomes, not extensible program IDs or
plugin keys. Use Pydantic at validated configuration, HTTP and portable-data
boundaries; use dataclasses or ordinary objects for internal values/behavior where
runtime validation adds nothing. Avoid inheritance merely to reuse utilities,
parallel abstraction hierarchies, singleton lookup and class-per-helper expansion.
Tests follow the same ownership rules and reuse actual ports/scenario helpers.

### ADLC extensions after the migration: proposals, not implemented scope

The first useful product sequence is requirements -> design -> coding -> executable
checks -> review -> change proposal. Prefer capabilities that enable this sequence
over accumulating unrelated node types. Future team/delegation behavior remains
outside the current implementation.

| Priority | Capability | Ownership and current limit |
| --- | --- | --- |
| A | Typed structured node results and provider-neutral structured generation | UnifAI owns result schemas, validation and failure policy; LLM adapters translate supported provider formats. Programs already validate JSON input/output schemas, but `BaseLLM` has no typed structured-generation operation and ordinary node outputs are strings. A JSON parser alone is not the complete contract. Do not make application code depend on an engine-only state extension. |
| A | Durable code/test artifacts and workspace handoff | UnifAI already has artifact-reference values, but Codex files are environment-local. Add a concrete storage port/adapter, authorization, integrity and retention when implementing durable handoff. Keep large repositories/reports outside checkpoint payloads; graph state carries references. Compute reuse, durable storage and chat continuity remain distinct. |
| B | Reliable quality-gate conditions | Build typed-path comparison, schema-validation result, executable test result, change scope, reviewer outcome and bounded repair-attempt conditions. Specify missing/invalid-data behavior and use trusted evidence; an LLM's self-reported confidence is not a substitute for test evidence. Use registration/config/factory conventions and no arbitrary expression evaluation. |
| B | Bounded repair and parallel work | UnifAI application programs own attempt budgets, join/failure policy and external-effect idempotency. The runtime can already start declared/pinned children repeatedly; do not claim dynamic task counts necessarily require a new engine. Graph authoring lacks a map/join experience, and arbitrary runtime-selected program references are not currently exposed. |
| B | Replay-safe time and upgrade policy | Run Engine exposes a replay-aware clock; the present UnifAI runtime port exposes sleep/waits but not that clock. Add only the narrow clock operation when a concrete budget/deadline program needs it. Execution snapshots freeze configuration data, not the contents of mutable image tags; production digest/version pins and old-worker replay/drain policies are required. |
| C | CI/webhook and external review integrations | External adapters authenticate/correlate callbacks and application services validate transitions before delivering engine input. Engine messages are transport, not business authorization. Reuse existing waits/child/cancellation primitives rather than another scheduler. |
| C | Controlled multi-user operation | Define application admission budgets, allowed profiles, credential access/revocation and audit/retention against actual product requirements. Configured profiles are currently deployment-approved, not a per-user profile ACL system. Receiver identities are trusted control-plane metadata, not per-invocation signed secret capabilities. |

Engine infrastructure gaps must be demonstrated before adding engine abstractions.
Known current limitations include automatic private-secret provisioning into managed
OpenShell environments and the supported host/port/binary policy subset (not URL
path/method filtering). Other items above mostly require UnifAI contracts, adapters,
UI or validation; they are not reasons to build a second graph runtime.

## Architecture decisions

- Additional user scope: an installed Codex CLI coding-agent element follows the
  existing node config/identity/factory/spec/base-class convention. Its reusable
  workflow behavior belongs to the application; execution placement remains in
  Run Engine. Live paid tests require an explicit flag and private credentials.

- Prior user scope change: retire the OpenShell **element/tool integration**,
  including agent sandbox references and tool-routing wrappers. Keep OpenShell
  as a Run Engine execution backend selected through profiles/environments. This
  supersedes the original objective's request to preserve the tool-level integration.

- UnifAI owns application services, program contracts, policies, and element construction.
- Run Engine owns traversal, invocation dispatch, child runs, recovery, and environments.
- Programs support graph and registered application implementations. Advanced agent
  orchestration and delegation remain future additions.
- Element bundles retain the useful dependency-packaging purpose of mini-blueprints,
  without synthetic workflow reconstruction.
- Preserve existing factories, typed references, builders, domain reducers, and services.
- Preserve dependency direction with automated import checks, including cold imports
  that catch dependencies hidden in package initializers. Catalog discovery is
  scoped to installed specification modules rather than all loaded subclasses.
- Session bookkeeping does not introduce a separate graph child. Calls to reusable
  programs do create child runs.

### Async execution (user clarification)

The new FastAPI request path, application I/O services, execution gateway, runtime
operations, and resource lifecycle APIs should be asynchronous end to end. Await
Run Engine directly. Do not retain the legacy async bridge, per-request event-loop
creation, or `asyncio.run()` inside the new server path.

FastAPI does not turn blocking dependencies into asynchronous ones. Use native
async APIs where available. Isolate unavoidable synchronous SDK calls and existing
synchronous element execution in explicit adapter/execution boundaries that run
off the event loop. Such offloading is distinct from the legacy async bridge.
Own and drain in-flight work before releasing its resources on cancellation.

FastAPI provides the async entry point; removing the bridge also requires the
application and infrastructure call chain to support awaiting directly. Keep pure
validation, bindings, and other in-memory transformations synchronous. Use async
for I/O and coordination rather than making every function async.

The user's latest clarification makes async-first node, agent, LLM, tool, and
provider execution the next implementation priority. Establish one native async
execution contract, with synchronous compatibility limited to retained legacy
inbound boundaries when drain obligations require it. Pure transformations and
ordinary construction remain synchronous; resource acquisition that performs I/O
must be awaited. Use native async SDKs when available and own unavoidable blocking
SDK calls within adapters.

Native node invocation, packet handling, agent iteration, strategy thinking, and
LLM calls now await directly. `AgentActionExecutor` no longer uses an async bridge.
The iterator uses an async execution-handler contract, counts reasoning iterations
rather than queued output steps, and owns its trace context through cancellation.
Tool tracing now belongs to the executor's scoped execution instead of paired
pre/post hooks. Agent completion deadlines interrupt awaited work and drain cleanup.
Hook registration, construction, and pure state helpers remain synchronous.

Custom agents depend on `ToolProvider`, not the MCP adapter. MCP discovery is
asynchronous and lazy; its factories retain pure construction. Native OpenAI
Responses, OpenAI-compatible completions, and Google GenAI adapters use async SDK
calls and owned stream/client lifetimes. Bound model copies borrow their original
owner's client. Provider errors are sanitized during requests and stream iteration.
The GenAI 2.34 nested generator chain does not promptly close HTTP responses on
early consumer exit; the provider's public HTTPX response observer and owned scope
close them explicitly, including errors and cancellation. No engine change or SDK
private-method patch is involved.

Twenty-two focused agent/real-SDK-transport cases and seven architecture cases pass
without live model calls (JUnit: `/tmp/unifai-async-agent-provider-boundaries-20261029.xml`).
The saved-resource session and Redis approval matrix passed 18 cases after the
initial call-chain migration; the full regression run covers the later trace and
stream ownership changes. Native A2A, Claude, and Deep Agent call sites have been
adapted, but their optional SDK-specific execution still needs verification.

Tools now expose one `async run` contract. Execution, retry policies, MCP, web,
SDK converters, and built-ins use that contract; the duplicate `arun` APIs and
unused tool-capability mixin are removed. Retrieval is async too: Slack uses an
owned/borrowed HTTPX client, while document retrieval isolates its blocking RAG
SDK inside its adapter. Prompt augmentation awaits retrieval and preserves message
metadata. SSH connects lazily, serializes connection use, drains blocking SDK
work, and does not repeat uncertain commands. Generic retries apply to reads;
effectful tools require an explicit application retry policy. Mutating built-ins
declare their write semantics.

Approval gates and gatekeepers now await directly. The receiver reuses its async
Redis client, without an additional synchronous connection or a polling thread.
Cancellation drains ticket registration and closes only the matching pending
ticket; a conflicting request cannot close another ticket, and late submissions
do not rewrite cancellation as expiration. Legacy channel/store adapters isolate
their blocking transport at their own boundary.

Configured dependencies belong to their builder/caller. SDK agent nodes no longer
close borrowed tools prematurely. Following the user's subsequent scope change,
the OpenShell element package, sandbox builder, tool-routing proxy and SDK-agent
sandbox wrappers are removed. Agent configuration rejects a requested sandbox
reference; old unused `sandbox: null` defaults remain readable. Catalog discovery
does not offer the retired category, and both stored/native blueprint contracts
reject nonempty sandbox collections instead of discarding them. The enum/reference
identity remains only for interpreting legacy data. Six retirement contracts pass;
the engine execution profile still preserves an independent network-policy snapshot.

The earlier thirty-case tool checkpoint included three now-obsolete sandbox proxy
tests. Those three were removed with the feature; its passing result is historical.
The 27 approval/receiver/architecture contracts use real Redis. SSH ownership cases
use SDK doubles and do not establish physical SSH behavior.

### Operator-owned OpenShell policies

`PlatformSettings.execution_policy_files` optionally maps approved OpenShell profile
names to absolute JSON policy paths. Startup validates and snapshots their portable
data before acquiring clients. Files stay outside program definitions and bundles;
retries use compiled policy data. Inline/file conflicts, unknown/non-OpenShell
profiles, and policies attached to pre-existing sandboxes fail explicitly.

The companion `integrations/archive/run-engine-openshell-policy.patch` adds only generic
filesystem/process/Landlock fields, their SDK conversion, and endpoint validation.
Supplied policy replaces image policy, so the opt-in example retains the test image's
baseline instead of pretending a network-only object extends it. Current network
support is host/port plus executable paths; URL paths/methods remain unsupported.
See [configuration and ownership](program-platform-development.md#openshell-policy-configuration).

Verification on 2026-10-29:

- Eighteen file-policy/retirement cases passed in 1.62 seconds
  (`/tmp/unifai-execution-policy-contracts-20261029.xml`), included in the core run.
- Eight actual OpenShell egress cases passed: four ordinary invocation cases in
  21.96 seconds (`/tmp/unifai-openshell-egress-20261029.xml`), followed by four
  retained-environment cases in 21.69 seconds, with the four ordinary cases
  deselected (`/tmp/unifai-openshell-retained-egress-20261029.xml`). Both matrices
  cover Local/Temporal coordination, two reachable destinations, one-denied policy,
  actual server request counts, physical cleanup and Temporal history replay.
- The sandbox image was rebuilt and 1,135 Python files matched current sources:
  `unifai-sandbox@sha256:1c0eb0eda15ec60f2c4ef21deb19bc20840c485ace567060f84ca960ab360504`.
  The packaged JSON example also validated inside that image. Kubernetes receiver
  images were not refreshed in this slice.
- Companion engine checks passed 42 cleanup/TLS/policy tests and 19 configuration/
  environment tests. The first command reported a pytest cache-write warning under
  the restricted filesystem and an unset fixture-loop setting; the second used an
  explicit temporary cache and loop scope. Neither command failed. The fifth
  companion patch applies after the four earlier patches on the documented base.

This proves the supported host/port policy subset for the tested image/gateway;
it does not establish URL-path filtering, remote-agent behavior, or worker-loss
recovery. No paid provider calls were made.

The migration remains open: optional SDK-backed agent execution, remaining legacy
provider/validator helpers, and real SDK resource-factory construction need further
verification. In particular, the explicit MCP proxy resource factory still has an
old provider-constructor contract; the provider-discovered proxy path and direct
proxy execution have different construction paths. Address that concrete factory
gap during the application/plugin construction boundary work.

The receiver now notifies its owner before cancelling a native async element and
drains the element's cleanup before propagating cancellation. Repeated caller
cancellation cannot interrupt that drain. Blocking acquisition/cleanup still
finishes under the existing ownership rule. Focused receiver, construction, and
actual thread/process program tests passed 28 cases with one existing Authlib
warning (JUnit: `/tmp/unifai-native-async-cancellation-20261029.xml`). This fixes the
receiver boundary; the full agent/tool async migration remains open. Six additional
real-Redis approval cancellation cases passed across thread/process placement and
child subtrees (eight unrelated cases deselected; one existing Authlib warning;
JUnit: `/tmp/unifai-review-prerequisite-cancellation-20261029.xml`).

## Completion ledger

### Catalog/construction ownership and saved MCP tools

Catalog services, specification/factory/validator/card contracts, category builders
and owned construction now live in `mas.application.elements`. Portable bundles
live in `mas.domain.element_bundles`; `ElementInstances` owns the runtime index.
The application registry has neither filesystem discovery nor a global singleton.
Bootstrap composes outbound discovery and explicit plugin modules. Discovery uses
actual module exports, not process-global subclasses; broken/internal/incompatible
imports fail explicitly while uninstalled optional dependencies stay unavailable.

The broken `mcp_proxy` factory now requires a typed provider reference and exact
tool name. Native construction owns returned instances before awaiting optional
`prepare_element`, so real server schemas exist before dependent agents are built.
Failure/cancellation/private errors preserve cleanup and masking. Wrappers borrow
provider/tool lifetimes. Configurations with only `tool_name` must add `provider`.
MCP schema validation no longer initializes global configuration or invokes dynamic
model generation; protocol failed results remain failures. Registered specification
module paths, type keys and native engine entrypoints remain unchanged.

Verification on 2026-10-29:

- 28 final preparation/architecture/catalog/SDK cases passed in 2.77 seconds
  (`/tmp/unifai-element-preparation-final-20261029.xml`).
- Two saved MCP-agent session cases passed in 5.46 seconds
  (`/tmp/unifai-saved-mcp-agent-sessions-20261029.xml`): real local MCP service,
  two actual agents, two turns, saved provider/tool dependencies, both thread/process
  receivers, shared behavioral assertions and publication surviving provider edits.
- 420 core tests passed in 169.98 seconds, with zero failures, errors, skips or
  reported warnings (`/tmp/unifai-platform-catalog-mcp-preparation-20261029.xml`).
- Refreshed images each matched 1,141 current Python files: receiver
  `sha256:e77871396731239b28fc8490aa20747a8d1a229b696461aa97af885a28f09398`, sandbox
  `sha256:df0a8ff8b2fdbc3bd61f4ab006ecfdefa6e2e0f67a4e3e27f8bc354eda93cfe0`.
- 28 Kubernetes/OpenShell program cases passed under both hosts in 227.09 seconds
  (`/tmp/unifai-catalog-preparation-remote-matrix-20261029.xml`), covering composition,
  transitive construction, ownership/borrowing, scoped release, private settings,
  failures, physical cleanup and native replay.
- Eight OpenShell allow/deny cases passed in 44.54 seconds
  (`/tmp/unifai-catalog-preparation-openshell-policy-20261029.xml`). The 36 remote
  regression cases had no failures, skips or reported warnings.
- All 211 changed Python files pass Ruff and formatting checks. The MCP diagnostics
  skill captures async preparation and the AnyIO lifespan task-owner constraint.

Remaining scope includes remote MCP-agent placement, paid-model verification,
further plugin thinning/relocation, program/session/resource service consolidation,
ignored runtime controls and streaming deadlines, older Pydantic configuration,
human review, and product/API migration. This passing slice is not completion of
the migration and adds no new agent orchestration/delegation framework.

### Shared agent/domain extraction

The first structural slice is implemented. Shared messages, tool schema, element-card
values, agent steps and task/workspace/work-plan data moved to `mas.domain`.
Model/tool/retrieval/tool-provider contracts moved to `mas.application.ports`.
Shared agent algorithms, approval behavior, execution policies, capabilities and
workload services moved to `mas.application`. Domain dependencies are inward;
application code imports neither element plugins nor transport SDKs. Cold agent
imports load neither plugin packages nor global infrastructure settings.

This fixes actual ownership/dependency problems alongside the move: JSON Schema
validation no longer initializes global configuration; executor construction borrows
port instances instead of deep-copying resource owners; validator collections and
nested tool schemas are independent; work-item retry rules do not import a service;
workspace accessors agree on stored context and restore typed artifact values.
Unused runner/shim/duplicate phase/work-plan/retry/thread helpers and standalone
workload examples were removed after checking repository consumers. Default strategy
prompt values were compared with the original source and remain unchanged.

Registered type keys, specification module paths and native engine entrypoints
remain stable in this slice. Internal Python callers use the new owners directly;
old workers still require their compatible release while prior executions drain.
The subsequent catalog/construction extraction is recorded above. Further plugin
thinning and program/session/resource service consolidation remain; the complete
physical layout is not finished.

Verification on 2026-10-29:

- 145 focused domain/application/architecture/SDK-transport tests passed in 3.09
  seconds (`/tmp/unifai-shared-agent-boundary-focused-20261029.xml`).
- 406 core platform tests passed in 169.28 seconds, with no failures, errors, skips
  or reported warnings (`/tmp/unifai-platform-shared-agent-boundaries-20261029.xml`).
  This includes real saved-resource blueprint/session behavior, separate FastAPI/
  worker processes, thread/process receivers, Mongo/Redis/Temporal and native replay.
- The refreshed images each matched 1,133 current Python files:
  receiver `sha256:d62e361d9af1e3f3cd09cd5577077ed43a0b2e74166e541106050a747fdcb08e`,
  sandbox `sha256:ffe909c8b6951752f640825e84bc297a2e6cedd9807d6f5f9bff61c0f91c28f2`.
- Eight real OpenShell host/port allow/deny cases passed in 45.28 seconds under
  both hosts and both lifetime modes, including physical cleanup and native replay
  (`/tmp/unifai-shared-boundaries-openshell-policy-20261029.xml`).
- The complete remote program matrix passed 28 cases in 217.61 seconds with no
  failures, skips or reported warnings
  (`/tmp/unifai-shared-boundaries-remote-matrix-20261029.xml`). It covers Kubernetes
  and OpenShell under Local/Temporal coordination: transitive construction,
  invocation-owned/retained lifetimes, graph/application/graph children, continued
  parent use after child borrowing, scoped release before parent completion,
  private receiver settings, failures, physical cleanup and native history replay.
  Together with the separate policy matrix this is 36 remote cases after the move.
- All 176 changed Python files passed Ruff checks. New architecture guards cover
  relative/aggregate imports and cold imports of the extracted layers. The reusable
  `.cursor/skills/refactor-agent-boundaries/SKILL.md` records the concrete traps.

Remaining quality work includes the older class-based Pydantic configurations in
the shared phase/work-item code, ignored runtime rate controls and streaming deadline
semantics, and optional SDK-backed agent execution. These require their own changes
and evidence; this passing slice does not establish a completely clean final system.

SOLID, hexagonal boundaries, semantic correctness, explicit ownership, module-level
imports, and minimal purposeful abstractions apply to the entire application and
its tests. They are acceptance criteria throughout implementation. Test layout
must reflect dependency direction without forcing production code into a testing
framework. Remove superseded code when its replacement and drain obligations are
verified; passing tests alone do not prove completion or architectural correctness.

The following items remain open until implementation and corresponding evidence
are recorded. This ledger is a tracking aid, not proof of completion.

- [ ] Program definitions, immutable revisions, contracts, publication, and persistence.
- [ ] Element bundles: transitive closure, validation, construction, and cleanup.
- [ ] Graph compiler, typed state adapter, conditions, and domain reducer parity.
- [ ] Graph-to-graph and graph-to-application program composition.
- [ ] Application-owned execution/runtime ports and engine adapters.
- [ ] Execution records, identity, submission recovery, cancellation, reconciliation.
- [ ] Profiles, step placement, environment ownership, and explicit borrowing.
- [ ] Existing blueprint/session integration, auth, streaming, approvals, scheduling.
- [ ] FastAPI migration, thin routers, dependencies, lifespan, and async services.
- [ ] Replace multi-agent tests with the new platform suite; preserve unrelated tests.
- [ ] Local integration tests and separately identified infrastructure validation.
- [ ] Development/deployment instructions, architecture diagrams, extension guides.
- [ ] Drain-compatible legacy retirement and requirement-by-requirement final audit.

## Coordinated implementation order after the user's live-agent and placement requests

The objective remains the full platform migration. The following order coordinates
the additional requests; it does not replace the completion ledger or narrow its scope.

### Working sequence and completion gates

The foundation is implemented in part; none of the stages below is a declaration
that the entire migration is finished. The latest complete core run after the
catalog/construction and MCP-resource changes passed 420 tests, with no failures,
errors, skips or reported warnings, in 169.98 seconds.
JUnit: `/tmp/unifai-platform-catalog-mcp-preparation-20261029.xml`.
That result excludes the two separately selected remote deployment files. It includes
deterministic real-agent sessions and real SDK transports; it does not establish
live-provider, remote-agent, or optional SDK-backed agent execution. Both
receiver images were refreshed for the extraction and have the policy evidence
recorded above; broader remote-agent verification remains outstanding.

| Order | Deliverable | Gate before moving on |
| --- | --- | --- |
| 1 | Execution placement and environment contract | Resource preference survives authoring/import/publication; explicit step selection wins; invalid selections fail before dispatch; ownership and borrowing are explicit. |
| 2 | Clean construction, plugin, receiver, and secret boundaries | Registered element schemas remain extensible; transitive bundles build and close correctly; receiving environments resolve secrets without exposing them; focused boundary and failure tests pass. |
| 2a | Make multi-agent package boundaries explicit | Shared agent/domain and catalog/construction extractions plus saved-session/MCP regressions are verified. Continue with thin plugin adapters and program/session/resource service consolidation; preserve portable references and verify each structural slice. |
| 3 | Substantial deterministic agent/session E2E | Real existing agent nodes, tools, shared resources, transitive dependencies, and multiple turns succeed through FastAPI and separate workers with real services. |
| 3a | Human Review vertical slice, after the async execution refactor | A configurable review step waits through engine coordination; validated, authorized decisions survive restart; rejection, expiry, cancellation, duplicate responses, and graph routing are tested. |
| 4 | Explicit live Gemini session verification | The same scenario succeeds with bounded live calls; live tests are default-off and credentials stay private. |
| 5 | Deployment and environment-sharing matrix | The same application scenario works with thread/process/Kubernetes/OpenShell placement; sharing, child borrowing, replay, recovery, cancellation, and cleanup have evidence for each supported case. |
| 6 | Finish product/API migration and legacy retirement | Required API/client/startup/schedule behavior has parity; defaults switch only when replacements work; old executions and schedules drain before dependent workers/code are removed. |
| 7 | Final cross-cutting audit and handover | Requirement evidence, static checks, regression/E2E results, architecture/extension guides, and reusable test/investigation skills agree with the delivered code. |

Code quality is a gate in **every** stage, not work deferred to stage 7. Apply SOLID
and hexagonal dependency direction to production code and tests; review semantics,
ownership, cohesion, error handling, and cancellation as well as passing tests.
Use minimal purposeful OOP, top-of-file imports, enums for closed choices, and
Pydantic where boundary validation is needed. Remove superseded/dead code as each
replacement becomes safe, while honoring legacy drain requirements. Avoid wrappers,
classes, and abstractions without a concrete responsibility.

Each stage is a runnable vertical slice: review its design, implement it, run focused
application/adapter/integration checks and relevant real-service E2E, then record
the result. Broad final verification follows the completed slices. A known failing
case stays open; skipped, unselected, and unrun cases never count as passed.

### Detailed scope by stage

1. **Finalize application execution policy and environment contracts.** Keep agent
   behavior/vendor settings separate from application execution metadata. Permit a
   reusable agent resource to express an approved profile preference; an explicit
   step profile/environment selection overrides that preference. Effective default
   precedence is step selection, resource preference, program default, platform
   default. Mandatory element requirements and application policy constrain every
   resolved choice. A resource preference names a profile, not a caller-specific
   environment instance. Program declarations own named environments; steps bind
   to their names, and child calls explicitly import aliases. Run Engine owns
   provisioning, grants/borrowing, dispatch, reconciliation, and release. Initial
   owned environment lifetime is one root execution; session state/artifacts and
   external pre-provisioned environments have separate ownership. Do not imply
   cross-turn compute reuse from matching environment names. The existing step
   selection/declaration/import contracts already work. Resource-level preferences
   now pass through native authoring, persistence, blueprint resolution, and
   immutable program publication. Focused checks cover precedence, explicit reset,
   optimistic edits, source deletion, and actual process execution. The broad core
   regression passed 321 tests with one existing Authlib deprecation warning.
2. **Finish the supporting application boundaries before more live calls.** Preserve
   services, registry, factories, builders, transitive typed bundles, and reducers.
   Complete publication of effective placement/bindings and receiver-local secret
   resolution for selected targets. Keep backend clients and credentials outside
   agent behavior, reusable bundles, and workflow history. Resolve blueprint/plugin
   schema restrictions through the registered schema boundary rather than editing
   closed global unions for each new element. Keep all new I/O async/off-loop with
   explicit ownership. Address discovered package-initializer, cleanup, and error
   classification defects rather than hiding them with test fixtures.
   Native authoring, inspection, and import now share registry-generated schemas
   with explicit category/type dispatch. Tests cover plugins without internal type
   discriminators, transitive inline/saved dependencies, actual thread/process
   execution, and secret hints. Import now composes the async authoring and shared
   resolution services instead of its duplicate legacy import adapter. Resource
   deletion now depends on a narrow usage reader; native library composition no
   longer loads the fixed vendor configuration lists. The final broad regression
   passed 336 tests, including the usage refactor and cold-import guard.
   Receiver-local private-settings cases now pass across both backends and hosts.
   OpenShell receives an exact collector endpoint/binary rule through its typed
   deployment policy, retaining filesystem/process setup. The full 28-case remote
   matrix passes; managed OpenShell private-file provisioning remains a separate
   production deployment capability gap.
   **Next structural slice:** the user's subsequent directory-boundary request
   applies to `multi-agent`. Finish the current async regression first, then make
   domain/application ownership visible before Human Review or further provider
   feature expansion. Move shared agent execution, message models, tool/retrieval
   ports, and construction contracts out of element plugin internals. Classify
   nodes by responsibility: their registration/graph glue is an adapter; reusable
   agent behavior belongs in application services. Preserve useful factories,
   builders, registry discovery, typed references, and immutable bundles. See
   [the package-boundary status and plan](program-platform-development.md#package-boundaries).
3. **Build one substantial deterministic session scenario.** Reuse actual existing
   input, custom-agent, and final-answer nodes, existing ReAct/tool execution, shared
   LLM references, and tools with transitive dependencies. Author/save resources and
   a blueprint through FastAPI, import/publish it, and run multiple turns in the same
   session through separate workers with actual Mongo/Redis/Temporal. Verify IEM
   delivery/acknowledgments, agent success, opaque tool-derived evidence, final
   output, conversation continuity, workspace/thread state, identity, cancellation,
   and cleanup. Use application-owned scripted LLM fixtures for the ordinary suite;
   do not introduce a replacement agent framework or a new delegation product.
   The shared baseline now runs actual input/custom-agent/final-answer nodes,
   nine saved/resolved resources, one shared LLM, and tools with three-level
   transitive construction. Local thread/process tests and separate HTTP/Temporal
   worker tests pass two turns, successful agent results, opaque tool evidence,
   IEM acknowledgments, workspace continuity, signed-cookie/Redis identity, token
   streaming, API restart, and native replay. Editing a saved dependency after
   publication preserves the published session's original data. The broad core
   regression passed 342 tests with one existing Authlib warning. The subsequent
   native node/agent/LLM call-chain refactor removes the active agent-action bridge.
   Focused cases now cover native tool cancellation, trace closure, real SDK stream
   failure/early exit/cancellation, and an awaited agent deadline. Finish the
   remaining tool/approval contracts and optional SDK verification before treating
   the async migration as complete or proceeding to live-provider work.
   **Next interaction slice:** the user's subsequent Human Review request is now
   part of the implementation order, after async agent/tool execution and before
   live-provider expansion. Investigated Run Engine's actual pre-node interrupt,
   checkpoint, resume-message, and generic receive contracts. The existing UnifAI
   compiler does not currently expose graph interrupts, and existing Redis tool
   approvals do not establish durable graph-review behavior. Implement the review
   as a registered application program callable with the existing program-step
   contract, keeping response policy and records in UnifAI and waiting/recovery in
   Run Engine. See [the design and acceptance cases](program-platform-development.md#planned-human-review-step).
   This is a planned feature; no review implementation or review E2E result is
   claimed by the existing approval tests. Future agent delegation remains out of
   scope.
4. **Reuse that scenario for explicit live Gemini verification.** Add a default-off
   `--live-llm` selection and marker with bounded rounds/tokens/timeouts. Read the
   key from local private configuration or environment; never commit it, copy it
   into images, print it, or put plaintext into published execution data. The user-
   supplied key is stored in the ignored infrastructure state directory with mode
   0600. Model discovery accepted it; no generation/session result has yet been
   established. The native Google SDK is installed locally. The live tests and
   optional dependency declaration still need implementation. Explicit live
   selection should report missing prerequisites or provider failures clearly.
5. **Run the same session scenario across placements and sharing modes.** Keep
   input/final steps on the trusted worker and select thread/process/Kubernetes/
   OpenShell profiles for the agents. Cover independent invocations, one shared
   root-owned environment, and explicit child borrowing with continued parent use.
   Use deterministic coverage for the broad matrix and bounded opt-in live cases
   for actual remote Gemini calls. Verify physical receiver identity, state/result
   parity, secret absence, history replay, cancellation/recovery, and actual cleanup.
   All four Kubernetes/OpenShell private-settings cases pass. Foundation scenarios
   also prove receiver-local file reuse, child borrowing with continued parent use,
   and child-owned environment release before parent completion. Actual multi-agent
   sessions, remote active cancellation, and worker-loss recovery remain open.
6. **Complete the remaining product migration.** Finish legacy authoring/interaction,
   credential onboarding, session cost/statistics, administrative concurrency,
   schedules/client compatibility, and affected frontend/CLI/container startup.
   Keep legacy workers until their executions/schedules have demonstrably drained.
7. **Audit the full requested end state.** Check requirement-by-requirement evidence,
   import boundaries and optional dependencies, typed contracts, ownership, dead and
   duplicate code, formatting/static checks, ordinary tests, opt-in live sessions,
   and selected real deployment matrices. Update development/deployment guides and
   repository skills from verified results. Freeze code and dependencies while a
   verification run consumes them. Passing a subset is not completion.

## Current evidence

- Dedicated repository `.venv`: Python 3.14.6; local `mas`, `global_utils`, and
  Run Engine packages installed editable, with FastAPI and test dependencies.
- Element-construction modules load without importing unrelated agent SDK schemas
  after extracting shared resource models and removing eager builder-package imports.
- Run Engine mapping arguments are implemented in the local dependency checkout.
  The companion patch is `integrations/archive/run-engine-program-mappings.patch` in this
  repository. Empty mapping arguments retain the original serialized shape.
- The replacement platform suite exercises native FastAPI endpoints and actual
  Local Run Engine execution, including thread/process placement and program
  composition. It does not yet prove the full legacy session/API migration.
- Latest complete platform verification with real Temporal, Mongo, and Redis:
  **342 passed, 1 warning** in 144.35 seconds after actual-agent session, factory,
  hook-setup, and catalog-composition changes,
  excluding the separately selected remote deployment file, under the current
  pytest warning configuration. The warning is Authlib's existing HTTPX
  deprecation. The JUnit report records zero failures, errors, or skips. The native
  Gemini SDK is installed, but installing it does not establish live-provider
  coverage; the requested live-session suite remains to be implemented.
  A separate unfiltered SDK-probe audit passed eight tests and exposed nineteen
  deprecation warnings: existing Pydantic v1-style configurations, MCP factory
  `dict()` calls, and the retained A2A SDK client. Those compatibility cleanups
  remain open; the filtered full-suite count is not evidence of their absence.
  The previous full run passed 204 tests with eighteen
  additional Temporal dynamic-import notifications for Redis metrics/OpenTelemetry
  modules. A focused
  instrumented run confirmed Redis connection-pool `__del__` lazily importing its
  metrics recorder during graph-state type evaluation in a workflow thread.
  Owned Redis cleanup now drains socket closure and resets closed pool entries in
  their actual owner, before garbage collection. The focused Redis/Temporal checks
  then passed without import notifications. No replay restrictions or warning
  filters were relaxed.
  Mongo contracts require `UNIFAI_TEST_MONGO_URI`; fourteen Redis contracts require
  `UNIFAI_TEST_REDIS_URI`; nine Temporal contracts require
  `UNIFAI_TEST_TEMPORAL_ENDPOINT`. The Temporal API-restart contract also needs Mongo.
  Infrastructure contracts skip when their service URI is absent.
  Two deployment E2E cases additionally require all three services and run separate
  HTTP and native worker processes, with actual signed-cookie authentication.
  This complete run includes the native-parent observation correction and native
  tracing adapter/deployment contracts.
- All platform tests now separate application, adapter, architecture, and actual
  infrastructure integration concerns. Shared installed fixtures and scenarios
  live in `tests/support`; test cases do not import one another. Application
  lifecycle tests use a signature-checked gateway port double; integration tests
  retain actual engine execution. Resource tracking is scoped to individual tests.
- Async node calls are awaited directly in thread and process backends. Elements
  return UnifAI GraphState rather than needing an engine-specific class. Shared
  receiver construction handles nodes and conditions with one ownership scope.
- Conditions inherit approved program/platform placement and reject undeclared
  environments. Tests execute the existing Boolean router in thread and process
  backends. Invalid public schemas produce an application contract error.
- Mongo verification includes concurrent revision publication, immutable prepared
  snapshots, atomic submission claims, cancellation before submission, session
  optimistic concurrency, legacy session documents, and persisted terminal results
  after restarting the application with a fresh Local host. This proves persistence
  of completed results, not survival of active Local runs across process loss.
- Native async session services preserve turn staging, chat history, metadata,
  credential-user identity, and explicit state bindings. Tests cover multiple root
  executions per session, concurrent admission, cancellation during preparation,
  and stale result fencing. Reconciliation scans advance beyond long-running or
  temporarily unavailable executions.
- A real existing blueprint passes through BlueprintResolver, PlanBuilder, existing
  mock node/LLM factories, program publication, Run Engine, and session projection.
  BlueprintProgramImporter consumes resolved configuration without constructing
  clients or a synthetic graph for element construction. It rejects ambiguous
  entry/final topology rather than dropping disconnected steps.
- The ASGI composition root owns Mongo/Redis/HTTP clients, the engine host, and
  reconciliation tasks. `mas-platform serve` exposes the native server separately
  while the legacy default and drain workers are still needed.
  The installed native command has passed a real local health request and lifespan
  shutdown smoke check; its temporary server and Mongo containers were cleaned up.
- The selected upstream Run Engine handle/program-node/facade regressions pass:
  **48 passed, 1 warning**. New platform mapping tests additionally cover configured arguments,
  snapshot isolation, signature validation, and legacy payload shape.
- Receiver contexts now carry the actual child execution and immediate parent,
  preserve root correlation and session identity, and retain the acting human for
  credential lookup independently of team ownership. Real thread/process tests
  cover receiver dependency binding and application-to-application-to-graph chains.
- Native interactions authorize against execution ownership before accessing Redis.
  They preserve stream replay/cursors, atomic approval decisions and idempotent
  replay, expiration, cancellation, and execution-scoped rule updates. Session
  approval overrides are validated and snapshotted before receiver construction.
  Real tests cover thread/process waits, child events, late decisions, live rules,
  and explicit rejection of stream cursors outside retained history.
- Legacy channel/store approval adapters run blocking transport off the event loop;
  the native gate itself is async. A bounded channel
  drains captured events before receiver shutdown; delivery failures are explicit
  infrastructure errors and do not automatically retry tool effects. Cancellation
  notifies application waits before native cancellation and still attempts native
  cancellation if notification fails.
- The built-in receiver can reuse AuthService with the existing encrypted Mongo
  credential and server-config stores. Clients are owned per invocation and closed
  after element cleanup. Its async credential methods offload and drain legacy
  storage calls. AuthService accepts a cipher port rather than constructing a
  cryptography adapter. Real tests prove human/team separation, encrypted storage,
  thread/process resolution, and absence of secrets in prepared execution snapshots.
- `mas-platform worker` owns Run Engine's generic CoordinationWorker using the same
  host/queue settings as the API. Receiver settings are shared without requiring
  HTTP session secrets on workers. Installed entrypoints and application modules
  load before the replay sandbox; cold-process tests caught and fixed lazy schema
  imports that warm in-process tests did not expose.
- Real Temporal contracts cover graph-to-application-to-graph composition in thread
  and process targets and replay all three native histories. Separate CLI worker
  processes are killed and replaced: heartbeat redelivery repeats delivery while
  the fixture's business operation commits once, and message waits survive restart.
  SIGTERM drains the replacement worker and exits successfully.
- A real Mongo + Temporal + FastAPI contract closes and restarts the API while a
  session waits. Retrying the same turn reconnects to the same native run, input
  resumes the program, and the session projects its result. No graph child is
  introduced by session bookkeeping.
- Application child records are projected from native accepted requests, with
  pinned revisions, actual bound inputs, parent/root/session identity, and results.
  The new generic RunChildrenSource port reads existing Local retention or Temporal
  history; it does not introduce an execution journal in UnifAI. The companion
  upstream patch is `integrations/archive/run-engine-child-observation.patch`. Native
  failed child starts are excluded. Mongo child records remain readable after
  shutting down the original Local host; owner and root-submission boundaries are tested.
- Cancellation fences retain execution ancestry. HTTP and application-runtime
  child cancellation release pending grandchild approvals across thread/process
  boundaries while sibling programs continue. Runtime notification is an invoked
  effect, so durable coordination does not perform transport I/O directly.
- Installed entrypoints and the typed state adapter declare explicit Run Engine
  compatibility contracts. Future incompatible deployment changes must version
  those contracts and retain compatible workers for existing runs.
- Prepared snapshots and records pin the coordinator configuration by digest;
  Local locations identify one host instance. Drift blocks submission recovery,
  observation, messages, and cancellation without rewriting the original record.
  The real Mongo/Temporal API-restart contract changes the queue, observes HTTP
  503, then restores the original settings and resumes the same native run.
  Accepted work with missing observation becomes unknown rather than being
  redelivered. Successful observation/result clears the transient failure.
- Authored configuration fields marked SecretHint, ENCRYPTED_FIELDS, or SecretStr
  use immutable owner-scoped references backed by encrypted Mongo values.
  Program save normalizes configurations before persistence; element construction
  resolves credentials locally through a secret-store port. Existing factories
  and typed dependencies remain in use. Nested application element bundles,
  aliases, enum mapping keys, owner isolation, and immutable revision references
  are covered. Actual thread/process receivers get the right values; Mongo drafts,
  revisions, requests, failure records, and Temporal success/failure histories
  exclude the tested plaintext credentials. Those histories also replay.
  Protected invocation errors omit provider details while retaining failure kind.
  Secrets require declared schema metadata; arbitrary provider dictionaries are
  not automatically classified. Immutable snapshot cleanup and key rotation are
  operational follow-up work, documented with retention requirements.
- Native `PUT /api/programs/{id}/blueprint` reads existing stored authoring data
  through BlueprintService, BlueprintResolver, and the existing resource services.
  Ownership is enforced in the application service before interpreting the draft.
  Library composition owns one synchronous Mongo client; adapters run legacy calls
  off-loop and drain cancellation before releasing resources. The stored source is
  an application-owned port; the HTTP route delegates to BlueprintProgramService
  and normal program save/protection. Actual user/team, thread/process contracts
  verify transitive resources, caller overlays, encrypted values, native sessions,
  immutable revision snapshots, and rejection of foreign/private/missing resources.
  Typed SecretStr credentials retain their real values until protection rather
  than becoming display masks. Library import remains read-only against source
  documents. The separate native authoring service now supports async create,
  read/list, update, deletion, metadata merging, shortcuts, and schema access.
  Its schema is injected, keeping provider modules outside cold API/application
  imports. Writes protect credentials and use owner-scoped compare-and-replace;
  legacy writes increment the shared version. Actual Mongo contracts cover stale
  versions, concurrent edits, versionless records, mixed legacy writes, safe errors,
  and published revisions surviving source deletion. Old HTTP aliases, raw/form
  payloads, administrative authoring, and client migration remain open.
- Deployment E2E runs separate HTTP and worker processes against actual Mongo,
  Redis, and Temporal for thread/process targets. It verifies signed-cookie identity,
  encrypted resource/node authoring, referenced blueprint import/publication, session execution,
  events, API process restart, durable messages, cancellation, history replay, and
  graceful cleanup. Shared owned-process support replaces duplicated lifecycle code.
  File parsing now belongs to an inbound adapter shared by the retained CLI path;
  the same parser handles JSON and YAML. Its unused broken JSON loader and
  single-implementation abstract base were removed. These checks establish the
  tested native workflows, not completion of the remaining platform migration.
- Native resource CRUD uses application-owned storage ports, async Mongo, installed
  schemas, typed dependency extraction, ownership/built-in write policy, and version
  fences. Actual Mongo contracts cover concurrent writes, versionless records,
  legacy edits, usage guards, and published execution after source deletion.
  Native per-user/team built-in configuration shares the retained overlay format,
  validates effective configuration, accepts schema aliases, encrypts typed secret
  values, and rejects non-configurable fields. Reset retains its version fence.
  Public built-in reads omit shared private values and ciphertext while projecting
  only the caller's allowed fields. Shared schema walking now preserves actual
  SecretStr values and nested configuration across native and retained writes;
  nested caller-configurable secrets do not inherit shared private defaults.
  The MAS cipher adapter implements the app-owned cipher port and reads the
  existing encrypted format without importing cryptography in application services.
  Administrative descriptor transitions, cascades, and edit locks are not yet
  atomic with custom-resource mutations. Native deletion intentionally retains
  credentials potentially used by immutable program snapshots. These remaining
  lifecycle policies and legacy/client migration require follow-up evidence.
- Native resource inspection exposes saved/batch/inline validation and single/batch
  cards through an application-owned async port. The adapter reuses existing
  resource policy, validators, and card builders, runs storage/probes off-loop,
  and drains sibling work on cancellation or failure. Real Mongo contracts verify
  dependency results, caller overlays, team ownership, encrypted human credential
  lookup, safe provider failures, and access-denied inline dependencies. The
  retained inline-validation route now also requires authentication and forwards
  caller/credential identity. The shared library dependency resolver rejects
  missing resources and cycles. Deployed thread/process E2E exercises native
  validation/cards before authoring a referenced blueprint and executing it.
  Remaining legacy client contracts are still open.
- Native saved/draft blueprint validation and cards use an independent application
  service and an off-loop library-resolution port. Saved ownership is checked
  before schema parsing or dependency resolution. Configurations normalize through
  installed schemas, and typed construction dependencies determine validation/card
  order. Missing/inaccessible resources become invalid results; incompatible
  categories, duplicate identifiers, and cycles have explicit failures. Local
  inspection resolves owner-scoped secret references, accepts unsaved literal
  credentials without writing snapshots, and leaves execution literal rejection
  intact. Actual Mongo contracts verify caller overlays, human credential lookup,
  reference ownership, unchanged authoring/secret records, safe provider failures,
  and legacy stored-field tolerance. Application/adapter tests cover cancellation
  and off-loop ownership. Shared validator/card services redact declared private
  values from diagnostic content while preserving IDs, codes, and model types.
  Separate API/worker E2E exercises saved blueprint inspection before publication.
  Native MCP/A2A probes now await their async SDK paths directly. The synchronous
  entry points retain bridge compatibility for legacy callers.
- Native graph analysis now shares the blueprint-resolution port with inspection.
  It authorizes saved drafts before parsing, enforces referenced-resource visibility,
  and preserves raw YAML/JSON validation aliases behind native authentication.
  Validators/fix providers are explicit scoped dependencies. Root-node orientation,
  cycle-edge removal, and required-node removal suggestions are corrected; unused
  validator scaffolding was removed. Bounded iterative path enumeration prevents
  exponential analysis from running without limits. Real application/Mongo tests
  verify transport parity, ownership, safe errors, cancellation, meaningful fixes,
  and read-only source records. Old Flask graph-route authorization still needs
  the remaining compatibility migration.
- UnifAI owns independent test infrastructure in `multi-agent/tests/infra`, with
  loopback Mongo/Redis/Temporal ports, a dedicated kind kubeconfig, and a client-
  certificate-authenticated OpenShell gateway. Receiver images install wheels from
  the actual local sources and keep OpenShell's supervisor entrypoint. The explicit
  test profile selects its installed Python environment. The complete rebuilt
  receiver matrix passed **28 tests, 1 Authlib warning** in 200.46 seconds across
  Kubernetes/OpenShell and Local/Temporal. These cases exercise transitive
  dependencies, ordinary/retained lifetimes, graph/application/graph ancestry,
  failure cleanup, child borrowing with continued parent use, and native replay.
  Shared receiver-local files and hostname continuity prove reuse before, inside,
  and after a borrowing child. A child-owned environment is physically removed
  while its parent remains waiting and later completes. Four private-settings
  cases verify repeated authenticated OTLP export and raw/encoded key absence in
  records and native history. Kubernetes uses existing secret mounts; OpenShell
  uses an externally owned sandbox with private files and a narrowly scoped
  collector rule, retaining its filesystem/process setup. The replayer preserves the
  real namespace and module preload. The original failing history also replays in
  a fresh process; no production decision code or replay restrictions were changed.
  These checks do not prove remote approvals, network-policy enforcement, or
  worker-loss recovery.
  At that remote checkpoint, both rebuilt images matched 1,147 source Python files
  by SHA-256. Subsequent actual-agent/factory/hook changes require rebuilding and
  verifying images before the next remote agent test; this earlier result is not
  a source-match claim for those later changes.
  The executable verifier now includes shared utilities and every installed fixture,
  expanding the earlier runtime/application/selected-fixture comparison.
  Current image identities:
  `unifai-receiver@sha256:61f9a1126443627afd1638133cbb2fb0f781050b43981fdeade753ca0157e302`
  and `unifai-sandbox@sha256:cbfca1ae6637a8a49d24e82003301a5be57b7c73d11a2871e1dc1ce2b0d6c6e0`.
  The generic TLS adapter extension has 44 passing upstream configuration/lifecycle
  tests and is recorded in `integrations/archive/run-engine-openshell-tls.patch`.
  Its four affected production modules also pass the upstream strict mypy
  configuration. All four companion patches apply in sequence to the documented
  clean baseline. The E2E extra installs the backend SDK requirements explicitly.
  Repository testing and infrastructure skills link to the maintained test guides.
  Mongo/Redis/Temporal readiness checks were exercised through Compose `--wait`;
  the full core suite then passed again with the corrected replay helper and
  refreshed editable package metadata. The redundant task-created Mongo container
  was removed. Pre-existing user services and the global Kubernetes context were
  left unchanged.
- Element validation now has an async path shared by native resource and blueprint
  inspection. Async SDK probes own one deadline and drain cleanup through repeated
  parent cancellation; synchronous validators and storage calls stay off-loop.
  AuthService exposes owned async credential binding. Actual SDK HTTP protocol
  tests cover success, rejected credentials, timeout, and cancellation without a
  bridge. Real Mongo/API contracts cover saved/inline resources and saved/draft
  blueprints with actual encrypted human credentials and substituted transports.
  MCP initializes and closes SDK contexts in their entering task; A2A closes
  partially entered HTTP clients. Missing/expired/empty MCP credentials cannot
  fall back to anonymous transport. Architecture guards cover the validation
  service and common validator contracts as well as the native application paths.
- API, receiver, cancellation-effect, and infrastructure-test Redis clients share
  an explicit ownership scope. Cleanup drains through cancellation, then releases
  disconnected pool entries. This avoids the SDK metrics import from a later
  pool finalizer running in Temporal's workflow thread; the traced warning path
  is confirmed rather than attributed to application coordination I/O.
- Native program schedules use the same immutable preparation path and generic
  engine worker as interactive execution. Business admission records the actual
  owning run before creating its session; it never starts a second host or graph
  child. Ten actual calendar deployment cases cover graph thread/process and
  application composition, API restart, pinned revisions, overlap policies,
  finite/manual budgets, confirmed edits, concurrent writers, owner checks, and
  retained session history after calendar deletion. Six application and two
  adapter cases separately cover retry/admission, mutation isolation, owner-first
  access, validation, and safe infrastructure failure translation.
  Real rapid triggers exposed native workflow-ID reuse within a second. The
  generic identity extension now pins namespace/workflow/generation and includes
  that generation in child identities. Ordinary submitted IDs and old unmarked
  histories retain their behavior; an actual pre-extension calendar history also
  replays. Pinned ordinary roots retain accepted-child observation, and child
  status validates and returns its recorded parent identity against native parent
  metadata. Ninety-two selected upstream regressions, including fixed histories,
  pass. Three affected engine modules and eight scheduling application/adapter
  modules pass strict type checking. The fourth companion patch applies after
  the preceding three and exactly reproduces the changed dependency files.
  Calendar updates confirm the applied registration after native acknowledgment;
  the SDK serializer needed for the fenced RPC remains isolated in the Temporal
  adapter. These results do not complete legacy schedule/client migration, quota,
  authoring retention, credential revocation, or deployment drain obligations.
- Lint passes for the new platform code and refactored construction components;
  `git diff --check` and environment dependency checks pass.
- Native tracing preserves the application tracing port while exporting session,
  node, LLM, tool, and iteration observations through independent OTLP providers.
  The port now returns abstract context managers rather than requiring one concrete
  generator implementation. Six adapter cases verify independent concurrent/later
  owners, deterministic session correlation, masking, unchanged global provider,
  physical batch-thread teardown, cancellation during resource acquisition/export,
  and validated configuration. Eight real deployment cases exercise both hosts,
  thread/process child execution, failure classification, collector outages, and
  Temporal replay. These cases plus process-settings and architecture checks passed
  together (**20 passed, 1 Authlib warning**, 23.18 seconds), then the complete
  core suite passed with all fourteen new tracing cases included.
  Five affected port/adapter/settings modules pass strict mypy. The HTTP endpoint
  decodes actual authenticated OTLP protobuf requests; it is a protocol fixture,
  not evidence of live Langfuse persistence or aggregation. The native adapter owns
  no process-global SDK singleton and creates no client during workflow decisions.
  The telemetry dependency is explicit in receiver images. Native tracing and
  image-verification workflows are captured in repository skills and an executable
  source-hash verifier. Remote tracing credential injection and legacy session-cost
  HTTP migration remain open alongside the broader deployment/API work.

## Remaining migration details

1. Extend remote environment validation to worker loss, recovery, cancellation,
   and cleanup uncertainty. Basic retained lifetimes and explicit graph-child
   borrowing now have real Kubernetes/OpenShell evidence on both hosts, including
   replay, using the existing engine journals. Native
   worker assembly, replay, crash recovery, API restart, and child projection now
   work. Local observation still has bounded in-process retention; it is not durable.
2. Complete legacy authoring HTTP compatibility and admin migration, including
   the retained Flask graph-route authorization/client audit.
   Native blueprint/resource CRUD, built-in caller overlays, metadata, and shortcuts
   now use async storage.
   Native resource validation/cards reuse existing services through async ports
   wired into the production library lifespan. Blocking library reads/card builders
   remain owned off-loop operations; MCP/A2A validation awaits SDK clients directly.
   Native blueprint inspection now resolves protected configuration locally and
   preserves existing validation/card services. Synchronous provider compatibility
   remains only at retained legacy entry points. Remove deprecated Pydantic model
   configurations and migrate the retained A2A SDK client before retiring broad
   legacy warning filters; keep unfiltered warning audits visible in the meantime.
   Audit remaining legacy inspection authorization during route/client migration.
   The native stored-blueprint import now reuses the existing services, including
   caller overlays and protected configuration, and executes through native sessions.
   The complete legacy authoring HTTP path remains open.
   Credential, channel, approval, and native tracing receiver wiring now work.
   Native tracing uses invocation-owned private OpenTelemetry providers/exporters
   through Langfuse's supported OTLP endpoint. This avoids the retained SDK's
   shared-by-public-key shutdown coupling without adding an application singleton.
   Concurrent receivers, acquisition/export cancellation, protocol payloads, and
   collector outages have adapter and real process/deployment evidence. Live
   Langfuse ingestion/aggregation and legacy session-cost HTTP compatibility remain
   unverified/unmigrated; retain that distinction during the API rollout.
   Native library imports now use the protected configuration save path. Keep all
   remaining authoring paths on that boundary while preserving editing, sharing,
   and export behavior. Typed SecretStr extraction now precedes encryption on
   retained resource and overlay writes too. Finish the administrative mutation
   boundary and its cross-collection concurrency guarantees, and define credential
   retirement against immutable revisions rather than only live resource counts.
3. Migrate the remaining HTTP endpoints and legacy interaction contracts, then switch the
   default commands/container startup and affected clients. Native program,
   execution, session, approval, and streaming endpoints plus cookie/team authentication now exist;
   the old Flask endpoint set is still needed during migration.
4. Migrate legacy schedule records and clients to the native program schedule
   integration. New calendars now run pinned programs in their owning engine run,
   with durable session history, native generation pins, and confirmed edits.
   Legacy quotas, authoring retention beyond the calendar's lifetime, credential
   revocation policy, and deployment drain checks still need implementation/audit.
   Keep existing workers for their schedules and executions until that migration
   and drain are verified.
5. Finish operational documentation and the full completion audit, including unused
   code, import boundaries, dependency contracts, ownership, and cleanup. Retire
   replaced execution code after its drain obligations are satisfied.
   Audit execution-context timestamp semantics and compatibility rollout. Coordinator
   drift and Local retention-loss fences now have application and real API evidence.
   Keep SDK lifecycle/replay isolation checks in the final audit; the traced Redis
   metrics-finalizer import now has explicit owner cleanup and regression evidence.


## Codex coding element and node convention (2026-10-29)

Implemented `codex_agent_node` with `CodexAgentNodeConfig`, `Identifier`/`META`,
`CodexAgentNodeFactory`, concrete `CodexAgentNode`, and `CodexAgentNodeElementSpec`.
The concrete node inherits reusable `mas.application.coding.node.CodingAgentNode`,
which depends on a coding-agent port and the shared application base node. Shared
`BaseNode` and `NodeBaseConfig` moved from plugin common code to
`mas.application.elements`; all active users import the canonical classes without
compatibility aliases. The optional custom validator/card extension points are
preserved; this element uses Pydantic and the existing default card builder.

The vendor adapter owns a native asynchronous `codex exec` subprocess, sanitized
JSONL parsing, typed usage/results, command/output/time limits, private CLI home,
and process-group cleanup. Resources use the existing protected credential path,
or a receiver-only operator private-file binding when sandbox database access is
unavailable. The operator alone may select external isolation for a profile that
already enforces it. Workspace-write remains the default, with no automatic
fallback and no element-config field to disable it.

The dedicated OpenShell derivative pins CLI 0.166.0 and installs its native
executable, Bubblewrap helper and ripgrep. The live OpenShell fixture uses explicit
external isolation because nested user namespaces are disabled on this host.
OpenShell continues to enforce filesystem/process/network policy. Each coding step
selects the same pre-existing sandbox profile; the fixture owns and deletes the
sandbox. This does not claim automatic secret provisioning into an engine-owned
named environment. `sandbox_id` cannot be adopted by a managed environment.

The default-off live workflow passed on Local and Temporal: 2 tests in 59.08
seconds, no failures/errors/skips (`/tmp/unifai-codex-openshell-live-20261029.xml`).
It creates saved coding resources, imports their references through a blueprint,
publishes a graph, writes and tests Python in the same environment, reads physical
file evidence in a separate element, checks credentials are absent from published
and execution data, verifies teardown and replays native Temporal history. It uses
`gpt-5.4-nano` with low effort and short time/command bounds. These are execution
bounds, not a strict API token/dollar cap. The API accepts this model currently,
but its official page marks it deprecated; do not silently switch paid tests to
an expensive model.

Focused coding/application/architecture checks passed 28 tests in 5.33 seconds
(`/tmp/unifai-codex-contracts-20261029.xml`), including real subprocess protocol,
timeout/cancellation, workspace escape rejection, operator-file credentials,
explicit isolation selection, actual factory/base-node participation and
owner-scoped protected resource credentials. This complements the live file
workflow rather than substituting for it. A package-local `debug-coding-elements`
skill records the image-helper, policy, transport and ownership findings.

All three final images matched 1,153 Python files against source
(`/tmp/unifai-codex-final-images-20261029.jsonl`):
- receiver `sha256:42487136c05bb56110a92671f06eeb9760f80ca8dba8936a1228dfd9b2efcb9c`;
- sandbox `sha256:338d3b0da1c22f303aa0e681b1800e5a64dee167bf8cb903b8a340bd40d2b913`;
- Codex `sha256:56f11af499a2b7db176c18e5a8963135c2b4f2f7d89966aba0d1ab9e70626aa7`.
The successful live run used the preceding Codex image
`sha256:1c957cf4e65153978561dc81bb0b0d6c58bfd85f77072bcec95dc3f4eaed77c5`.
The subsequent source change rejects a missing root execution identity before
creating any coding workspace; its focused regression passed. It prevents
legacy/incomplete invocation context from sharing an unscoped directory.

Additional terminal verification:
- 438 platform tests passed in 181.87 seconds, zero failures/errors/skips or
  reported warnings (`/tmp/unifai-codex-platform-core-20261029.xml`). The later
  missing-root guard is included in the 28 focused cases above.
- 28 Kubernetes/OpenShell + Local/Temporal remote cases passed in 229.03 seconds,
  zero failures/errors/skips (`/tmp/unifai-codex-remote-matrix-20261029.xml`).
- 8 actual egress policy cases passed in 44.76 seconds, zero failures/errors/skips
  (`/tmp/unifai-codex-openshell-policies-20261029.xml`).
- All changed node-import users and new coding implementation/tests passed Ruff;
  formatting, `git diff --check`, the aligned architecture diagram, and package
  skill validation passed. The private credential file is ignored and mode 0600
  beneath a 0700 directory; no supplied OpenAI key was found in tracked or
  unignored package/documentation/skill files.

The overall migration remains incomplete: the previously listed
FastAPI/client cutover, legacy drain, remaining plugin thinning/relocation,
Human Review element, optional provider/live-agent coverage and remote worker-loss
recovery still require work.


### Existing UI compatibility requirement (2026-10-29)

The user explicitly requires retaining the existing UI. Inspection confirms that
`ui/client/src/api/sessions.ts`, `blueprints.ts`, `catalog.ts`, `schedules.ts`, and
the session-stream hook still call legacy RPC-style routes. Vite proxies `/api2`
to `/api` on `MULTIAGENT_HOST`; changing that host alone does not migrate request,
response or streaming contracts. For example, legacy session creation/submission
use `/api/sessions/user.session.create` and `/api/sessions/user.session.submit`,
while native FastAPI exposes `POST /api/sessions` and
`POST /api/sessions/{id}/executions`. The full current UI is not yet verified against
the native API. Retain the existing UI, adapt its API/stream client boundary,
complete missing user-facing contracts (including catalog, auth/team scope and
scheduling), and verify the actual browser flows before retiring the legacy
backend. Backend API/service tests are not evidence that current UI flows work.
The browser must consume UnifAI application contracts, never engine/worker SDK
contracts or direct infrastructure services.


### UI catalog and custom-resource vertical slice (2026-10-29)

Native FastAPI now composes the existing application catalog and serves both
canonical REST metadata paths and the existing UI catalog requests. A separate
inbound editor-resource adapter translates the current UI's resource CRUD paths,
camel-case fields and pagination to native application services. There is no
Flask forwarding, duplicate registry, alternate resource writer or execution
framework. Static UI routes precede dynamic resource-ID routes. The UI's Axios
boundary presents native structured errors through the existing UI message
contract; retired sandbox fallback entries are removed.

Verification:
- 14 focused catalog/resource/lifespan/architecture tests passed in 2.80 seconds,
  including actual Mongo encryption, stale edit conflicts, hidden-owner reads,
  denied writes and owner-spoof rejection (`/tmp/unifai-editor-resources-20261029.xml`).
- The actual production TypeScript catalog/resource modules passed against a
  separate production-assembled HTTP server and Mongo, without response mocks:
  1 test in 4.72 seconds (`/tmp/unifai-ui-clients-20261029.xml`). It covers dynamic
  Codex schema, native validation error presentation without echoed private input,
  encrypted resource round trips and deletion.
- The broader platform suite with UI clients enabled passed 443 tests in 176.54
  seconds, zero errors/failures/skips (`/tmp/unifai-ui-catalog-resource-platform-20261029.xml`).
  Subsequent TypeScript error-shape assertions were independently rerun above.
- `pnpm run build` passed (4.37 seconds), retaining existing circular/manual-chunk
  and bundle-size warnings. Actual production `/login` rendered in the browser;
  the identity server was absent, and its expected unreachable-service message
  was visible. The temporary preview process and browser tab were closed.
- The UI configuration explicitly requested Node types but did not declare the
  package. Added locked `@types/node` 22.20.5 to enable a real type audit. The
  audit now reaches 33 existing errors across unchanged UI files, including
  missing shared activity schema, legacy graph examples/types, undefined
  AuthSelector, ref/timer types, old sandbox graph layout and stream declarations.
  None are reported in the changed Axios or catalog modules. Audit log:
  `/tmp/unifai-ui-types-20261029.log`. Production build success is not a claim that
  the full UI type-check passes. This initial audit was resolved in the next slice
  recorded below.

Remaining UI migration includes actions/configuration discovery, complete
blueprint and built-in/admin contracts, sessions and program publication,
streaming/approvals, schedules, collaboration/share/analytics surfaces, real
cookie/team browser flows, and default container/CLI cutover. Keep the existing
UI and legacy deployment available while these finish. The overall goal remains
active and incomplete.

The updated UI lockfile was additionally verified with the declared pnpm 10.13.1
using a successful noninteractive frozen reinstall (`--ignore-scripts`).

### UI type audit and display/session contracts (2026-10-29)

The full TypeScript audit now passes, including both contract suites. Fixed
active form/chat/ref/timer types, carried validated configuration through saved
graph reference display, restored the graph-creation approval-mode overlay and
defined the activity DTO in the UI that owns it. Session-output parsing now
rejects malformed values with a fixed message, and collaboration submission
failures propagate instead of falling through to a success result. The obsolete
auth selector branch, unreferenced graph example and unused stream parser were
removed; the stream parser's unused `oboe` dependency was removed as well. The
existing auth-hint renderer and active streaming client remain in use.

Verification:
- Full `tsc --noEmit` passed, zero diagnostics
  (`/tmp/unifai-ui-types-clean-20261029.log`).
- Production build passed in 4.32 seconds with the existing vendor chunk/size
  warnings (`/tmp/unifai-ui-type-cleanup-build-20261029.log`).
- 11 UI-client/architecture cases passed in 4.44 seconds, no failures/errors/skips
  (`/tmp/unifai-ui-type-cleanup-20261029.xml`). The API-client case calls actual
  native FastAPI/Mongo; graph-reference and session-output contracts use plain
  data and an Axios transport double. Both share the Vite test runner.
- The pure contract case also passed independently without a Mongo setting
  (`/tmp/unifai-ui-pure-contracts-20261029.xml`). Ruff and `git diff --check` passed.

An initial restricted-network invocation could not connect to the isolated Mongo
endpoint; the final real HTTP/Mongo verification above ran with local-service
access. No paid model calls or remote receiver image rebuilds were needed for
this UI slice. This does not establish logged-in browser coverage or complete
the remaining API/client cutover listed above.

### Existing blueprint editor transport and safe display queries (2026-10-29)

The existing blueprint client now works against native FastAPI for schema,
YAML/JSON-string authoring, draft/saved validation, draft and summary lists,
resolved single/paginated display, metadata and prompt shortcuts. The thin
inbound adapter preserves current UI routes during migration; source parsing is
owned off-loop and writes still use the single native authoring service.
`BlueprintQueryService` authorizes saved data through that service, resolves
transitive resources, preserves missing-resource reports and shortcuts, and
masks registered private fields without changing documents or adding secrets.
Editable drafts retain opaque credential references; display snapshots are
separate read models. Summary payloads omit configuration, while their storage
query currently still retrieves authoring documents before projection.

The editor sends the loaded version on update, retains each successful save's
version and surfaces stale-write conflicts. Editing/deletion/sharing-metadata
requests now carry explicit team scope; request-authored user identity was
removed from metadata updates. Native ownership and membership checks remain
authoritative. Editor load cleanup resets its load guard so a changed workspace
or document can load after cancellation.

Verification:
- 452 platform tests passed in 181.06 seconds, zero failures/errors/skips
  (`/tmp/unifai-ui-blueprint-platform-20261029.xml`), with actual isolated Mongo
  `27018`, Redis `6380/15` and Temporal `7234`, and `--ui-clients`. The remote
  program, OpenShell policy and live Codex deployment modules were explicitly
  excluded; no remote receiver matrix or paid calls were repeated for this
  HTTP/query/UI slice.
- The final version-aware TypeScript client and signed-cookie/team contracts
  passed 7 cases in 6.13 seconds, no failures/errors/skips
  (`/tmp/unifai-ui-blueprint-clients-final-20261029.xml`). The extra POST-body
  authentication case was added after the broad suite's collection. Its session
  and membership providers are port doubles, distinct from the real HTTP/Mongo
  client fixture and full browser proof.
- 9 initial editor/authoring/TypeScript cases passed in 7.61 seconds
  (`/tmp/unifai-editor-blueprints-20261029.xml`); 4 application query cases use
  port doubles and were also included in the broad suite.
- The real blueprint client scenario creates a saved node/model dependency
  graph, authors and edits its blueprint, then imports/publishes it and completes
  a native session turn. The final session calls use canonical APIs directly;
  they do not certify compatibility of the legacy session/chat client.
- Final full TypeScript audit passed with zero diagnostics
  (`/tmp/unifai-ui-blueprint-types-20261029.log`); production build passed in
  4.30 seconds with existing vendor chunk/size warnings
  (`/tmp/unifai-ui-blueprint-build-final-20261029.log`). Ruff, formatting,
  `git diff --check` and the updated package test skill validator passed.

The full migration remains active: session/chat/stream/approval clients, shared
chat authorization, raw multipart authoring, editor discovery actions,
built-in/admin and schedule surfaces, complete authenticated user/team browser
flows and default deployment cutover still need work. This slice preserves the
existing deployment startup. It does not rebuild current remote receiver images
or close the remaining architecture, plugin, human-review or legacy-drain work.

### Native sessions behind the existing UI contracts (2026-10-30)

UI session creation now delegates to an application-owned blueprint snapshot
service: authorize/resolve/protect, publish under a unique program draft ID, then
create the session pinned to that immutable revision. No engine run starts at
creation and there is no session wrapper child graph. Later authoring/resource
changes and blueprint deletion do not rewrite the session's published program.
Published revisions have retention independent from chat records.

Native application services also back the UI's turn submission, chat/state/status,
paginated lists, metadata, cancellation and deletion paths. Requests derive the
acting user from authentication and carry explicit team scope. Turn IDs can be
retained across an explicit retry. Query filters are typed, ordering is stable,
and memory/Mongo share contract scenarios. Mongo indexes cover owner and
owner/blueprint pagination. Deletion refuses active sessions and uses the observed
version to avoid deleting a record that has admitted a concurrent turn.

The UI stream adapter converts application events to NDJSON, pins each connection
to one execution, supports retained-history cursors and rejects explicit stale
turn subscriptions. Final observation uses the pinned execution even after the
session advances. The native SSE endpoint is retained. Human decision submission
uses the same native interaction service; cancellation returns its observed
status rather than inventing immediate completion. Unknown count/timing data is
null, and uncertain submission phases are reported as unknown while remaining
reconnectable.

The UI now uses a shared NDJSON reader with incremental UTF-8 decoding, final-line
handling and reader ownership. The hook passes fetch's actual abort signal,
guards replacement subscriptions and reports transport errors. Reader disconnect
does not cancel backend work. Accepted cancellation continues observation until
the server's terminal result; a running result is not presented as success after
a stream failure. Duplicate unused session-state transport/types were removed.

Verification:
- 463 platform cases passed in 194.38 seconds with no failures/errors/skips or
  reported warnings (`/tmp/unifai-chat-platform-20261030.xml`). This uses the
  isolated Mongo `27018`, Redis `6380/15`, Temporal `7234` and `--ui-clients`.
  Remote-program, OpenShell-policy and live-Codex deployment modules were explicitly
  excluded; this is not a fresh remote receiver or paid model matrix.
- 37 final UI-client, Redis interaction, Mongo persistence and architecture cases
  passed in 23.62 seconds with no failures/errors/skips or reported warnings
  (`/tmp/unifai-chat-final-contracts-20261030.xml`). This follows the final
  pagination-index, status/reader-cleanup and architecture-guard refinements.
- 4 shared two-agent scenarios passed in 6.81 seconds through canonical and UI
  session routes across thread/process workers
  (`/tmp/unifai-chat-agent-sessions-20261030.xml`). They use the same actual
  agents/tools, shared transitive resources, two turns and post-publication edits.
- 3 focused snapshot/chat cases passed in 1.70 seconds
  (`/tmp/unifai-chat-sessions-20261030.xml`), and 2 focused turn-stream/approval
  cases passed in 4.10 seconds (`/tmp/unifai-chat-streams-20261030.xml`, 14 other
  cases deselected in that focused invocation). Both sets are included in the
  broad suite.
- Actual TypeScript session exports run against separate production ASGI assembly,
  HTTP/Mongo/Redis and a registered deterministic approval element. They verify
  reader abort without execution cancellation, approval, replay, stale subscription
  rejection, a second cancelled turn and deletion. Pure tests verify framing and
  reader cleanup. These are separate from React/browser workflow evidence.

- Final full UI type checking passed with zero diagnostics
  (`/tmp/unifai-chat-ui-types-20261030.log`); the production build passed in
  4.48 seconds with existing vendor chunk/size warnings
  (`/tmp/unifai-chat-ui-build-final-20261030.log`).

Package testing instructions are updated and `debug-session-ui` records the
identity, snapshot, stream and cancellation investigation. The new/updated skills
validate. Native changed-path Ruff/formatting and `git diff --check` pass; a wider
lint read still finds existing issues in retained legacy runner modules, which
remain part of the planned drain/removal work.

Still required: bind approval responses explicitly to their originating execution,
migrate selective approval-rule updates, finish shared-chat authorization and
collaboration/presence, validate pending UI callbacks across session/workspace
switches in real authenticated browsers, and finish discovery/admin/schedule and
deployment cutover. The Human Review element, remaining package-boundary/plugin
refactors and legacy drain also remain open. Existing deployment startup is
unchanged, keys were not read and no paid LLM calls were made. Remote images have
not been rebuilt to match these current sources. The full goal remains active.

## Codex placement matrix and context walkthrough (2026-10-30)

The optional live scenario now runs the same two saved Codex resources through
Kubernetes and OpenShell, under Local and Temporal coordination. Kubernetes uses
the existing private Secret fixture and an engine-owned named environment shared
by the writer, verifier and deterministic file reader. The worker has an explicit
environment journal; completion verifies physical pod/Job cleanup. OpenShell
continues to use its fixture-owned pre-provisioned sandbox and private credential
file. The scenario checks real files, Linux/namespace/image evidence, token usage,
credential absence in published/execution data and Temporal history replay.
This is sequential collaboration, not concurrent editing or CLI thread resumption.

The initial Kubernetes attempt failed before model execution: `runAsNonRoot`
could not verify the image's named `sandbox` account. That matrix was interrupted
after its first failed case. The corrected image declares the same verified
numeric identity, `998:998`; pod non-root enforcement remains enabled.

Verification:
- All 4 explicit backend/host live cases passed in 90.91 seconds with zero
  failures/errors/skips or reported warnings
  (`/tmp/unifai-codex-placement-fixed-live-20261030.xml`). This includes two Codex
  resources per case, uses the existing authorized cheap-model fixture, and
  removes owned sandboxes/workspaces and Kubernetes resources. A subsequent
  dedicated-cluster query found no fixture-owned namespaces.
- The tested image `unifai-codex:placement-fixed-20261030`, identity
  `sha256:88ee5993571fb04c143698476ba1492ba5b4f087819082a41be8a56692500641`,
  matched 1,163 installed Python files to the checkout before execution
  (`/tmp/unifai-codex-placement-fixed-images-20261030.jsonl`).
- 24 coding/architecture checks passed in 5.31 seconds
  (`/tmp/unifai-codex-placement-contracts-final-20261030.xml`), and the default-off
  live gate produced 2 intentional skips without selecting infrastructure or
  enabling paid calls (`/tmp/unifai-codex-live-gate-20261030.xml`).

The UI/profile/auth walkthrough found two remaining boundaries worth making
explicit. Resource and blueprint-reference placement metadata, program defaults
and immutable per-execution prepared snapshots exist. The UI has no working
profile-selection flow yet: its generic form misclassifies top-level execution
metadata as element configuration, and chat creation has no program-default
override. This is required UI migration work, not a finished feature.

Login credentials terminate at the HTTP authenticator. Engine context carries
owner/acting-user IDs and run ancestry; receiver-local services resolve provider
credentials. The native receiver settings now refuse Mongo credential mode
without an encryption key. This follow-up validation change is later than the
live image above; that image is not claimed to contain it. It passed 41 focused
receiver/coding/architecture cases in 5.32 seconds
(`/tmp/unifai-placement-auth-contracts-20261030.xml`) and 14 actual Mongo
credential/configuration-secret/resource-authoring cases in 4.73 seconds
(`/tmp/unifai-placement-auth-mongo-20261030.xml`), all without failures/errors/skips.
The existing credential adapter's legacy plaintext compatibility and old records
still need an explicit retirement/migration policy; the startup guard does not
retroactively encrypt old data or establish a complete production security audit.

The development guide now includes separate submission and receiver sequences.
Test instructions and coding diagnostics cover both backends, ownership modes,
numeric image identity and the unverified concurrent-coding case. The earlier
approval-rule/turn-binding changes remain work in progress and need their own
recovery/concurrency regression tests. The full goal remains active.

## Execution-bound approvals and durable session rules (2026-10-30)

The native UI approval and selective-rule routes now require the originating
root execution ID. NDJSON carries both that root and the actual source execution
ID for child events. Cards/callbacks retain the root/request identity and resolved
events are handled even without node metadata. Missing identities are rejected;
stale cards cannot affect a later turn reusing the same request ID. Compatibility
with retained legacy transports does not infer a missing root from the latest turn.

Scoped rule commands persist session defaults through optimistic concurrency,
then publish a revision-fenced Redis copy through a narrow application port.
Concurrent pure commands merge; they do not retry agent/tool effects. Redis keeps
the fence within the cached JSON and preserves empty arrays. Its private marker
is omitted from domain/public policy. Execution-only full replacement retains
the marker, survives same-revision reconciliation, and yields to a newer session
policy. Lost cache or failed synchronization is repaired by the existing session
reconciler. A retryable synchronization error explicitly distinguishes saved
defaults from unconfirmed live publication. Rule-save and current-decision errors
remain separate in the UI.

Turn admission now observes an apparently busy predecessor before refusing the
next turn. Concurrent identical submissions recover the winning admission and
stage one user message; different inputs/scopes or competing turn identities
remain conflicts. Observation avoids needless session version increments. All
policy writes/observations check session ownership and execution membership.

Verification:
- **480 passed** in 214.22 seconds, zero failures/errors/skips or reported warnings
  (`/tmp/unifai-approval-platform-complete-20261030.xml`). The run uses isolated
  Mongo `27018`, Redis `6380/15`, Temporal `7234`, separate production API/worker
  processes and `--ui-clients`. Remote-program, OpenShell-policy and paid Codex
  modules were excluded; remote images were not rebuilt for this slice.
- 30 focused Redis, architecture and actual API-restart cases passed in 29.24
  seconds (`/tmp/unifai-approval-restart-e2e-final-20261030.xml`). Both Temporal
  thread/process scenarios retain a pending ticket while the API is down,
  deliberately lose its live-rule cache, restore defaults from Mongo, approve
  the original ticket, run a second auto-approved turn and replay histories.
  These cases are included in the 480-case run.
- Application port tests cover concurrent policy merging and recovery from a
  publication failure after persistence, including service reconstruction.
  Local engine tests force identical-admission conflicts with an explicit
  repository barrier. Real Redis tests cover stale turns, child root IDs,
  inheritance/clear behavior, cache reconstruction and delayed publication.
- Actual TypeScript API clients verify rule save/read/clear, persistence across
  turns, missing/stale identity rejection, stream replay and cancellation. Pure
  UI tests prevent same-request-ID status updates from crossing execution roots.
  The full UI static audit has zero diagnostics
  (`/tmp/unifai-approval-ui-types-final-20261030.log`); production build passed in
  4.36 seconds with existing vendor chunk/manual-chunk size warnings
  (`/tmp/unifai-approval-ui-build-final-20261030.log`).

The earlier broad attempt exposed a Codex test startup deadline race. The test
fixture now atomically announces readiness after descendant acquisition, owns
cleanup even on setup failure, uses a realistic CLI deadline and allows bounded
OS reaping observation. All 14 subprocess cases passed, followed by the complete
480-case run. An initial new-E2E teardown used a private Mongo document shape;
it now uses the typed execution repository, drains native work and cleans only
owned keys. The earlier attempt's four known roots/14 residual Redis keys were
identified from completed test logs and removed without flushing shared storage.

Native changed-path Ruff/formatting, `git diff --check` and the updated session
diagnostic skill pass. The pnpm wrapper attempted a noninteractive dependency
reinstall; no dependency purge was performed, and the installed Node runner,
TypeScript compiler and Vite entrypoints completed verification directly.

This closes the approval-rule/turn-binding slice, not the whole platform migration.
Profile controls, existing condition correctness, remaining API/browser behavior,
Human Review, package consolidation, deployment/security gaps and legacy drain
remain on the current implementation queue above.

## Condition audit and Run Engine handoff — in progress (2026-10-30)

Condition contracts now live in application/domain modules rather than plugin
common code. Built-in registrations retain config/factory/spec conventions.
Threshold selects explicit `output` or `nodes_output/<uid>` paths, validates finite
numbers and normalizes the retained top-level `input_key` format. Its specification
now declares actual channel reads. UnifAI normalizes symbolic/direct results and
rejects undeclared outcomes instead of silently accepting a routing mistake.

New branch-and-rejoin tests revealed a generic engine gap: default static
all-predecessor gating waits for an unselected branch and can complete without
executing the declared exit. An independent SDK-only reproduction also confirms
that an unknown label silently completes. These observations are separate from
UnifAI's threshold/configuration defects.

The [Run Engine handoff](../integrations/archive/run-engine-conditional-routing-request.md)
records exact reproductions, requested contracts, compatibility/replay constraints
and acceptance tests. The [integration README](../integrations/README.md) separates
earlier companion patches from the experimental active-join prototype. That
prototype is applied locally and uncommitted; UnifAI's compiler currently opts into
it. It is not an upstream-ready or production-verified dependency change.

Five prototype engine units passed; 69 focused UnifAI cases passed in 6.15 seconds
(`/tmp/unifai-conditions-active-joins-20261030.xml`). The original focused run had
16 missing-rejoin failures and 53 passes. SDK-only default-mode reproductions
return `completed` with visits `[choose, yes]` for a valid choice and `[choose]`
for an unknown choice; neither runs the declared exit. The engine prototype still
needs full SDK regression, Temporal replay/upgrade tests, matched receiver images
and final lint/type cleanup. It does not implement generic unknown-label policy or
completion diagnostics. The 480-case result above predates these condition changes.

UnifAI changed-path condition lint and `git diff --check` pass. The handoff diagram
is aligned and its standalone reproduction runs without importing UnifAI. This
slice remains open pending the engine contract work and integrated validation;
the overall goal remains active.

## Approved-profile resource editor and durable routing evidence (2026-10-30)

The resource editor now selects a deployment-approved profile for nodes and
conditions using authenticated catalog discovery. The public catalog contains
only names and the platform default; runner images, policies, mounts and environment
values remain private. Configured profiles are deployment-approved, not subject to
a newly implemented per-user ACL.

The editor's generic form combines only the resource name and element schema.
Execution metadata no longer enters `cfg_dict`. Shared client mapping preserves
the preference and loaded version for ordinary/nested resource editors. Save/update
requests retain selected team scope and optimistic versions. Omitted preferences
preserve the saved choice; an explicit null profile restores inheritance. Failed
discovery preserves the selected value, and a removed profile is displayed as
unavailable. The retired OpenShell tool-guidelines component was removed.

Actual TypeScript clients verify catalog discovery, metadata save/get/list/update,
explicit reset, stale-write rejection, saved-reference resolution, program import,
and publication pins. The authored graph executes successfully after its shared
resource is changed to another profile; the published revision retains its original
selection. Pure UI contracts guard the resource/config schema boundary and metadata
mapping. These do not establish authenticated React/browser behavior.

Current-source verification:

- **538 passed in 216.95 seconds**, with zero failures/errors/skips or reported
  warnings: `/tmp/unifai-profile-condition-platform-20261030.xml`. This includes
  actual own Mongo/Redis/Temporal, separate API/worker processes and all selected
  production TypeScript suites. Remote-program, OpenShell-policy and paid-Codex
  deployment modules were explicitly excluded. No remote images were rebuilt here.
- **Six additional cases passed in 7.19 seconds**:
  `/tmp/unifai-conditions-durable-20261030.xml`. Separate native Temporal workers
  run both exclusive threshold outcomes and direct selected fan-out, followed by
  history replay after worker shutdown. Conditions use thread/process invocation;
  work nodes use the thread default. The module was added after the combined suite
  collected, so its evidence is reported separately.
- UI type checking passes. The production build completes in 4.64 seconds with
  existing circular-vendor/chunk-size warnings; output is
  `/tmp/unifai-profile-resource-ui-build-20261030.log`.
- Changed Python paths pass Ruff lint/format; the updated UI and testing skills
  validate, and `git diff --check` passes.

The Run Engine handoff now distinguishes the two reproduced default-mode routing
outcomes, generic requests, five earlier patches and the experimental active-join
dependency. This turn changes no Run Engine source. Completed-history replay does
not establish deferred-join checkpoint recovery, old-history upgrades, remote
backends or full SDK regression. Generic strict-label/completion requests are still
open. Next placement work is blueprint defaults, step/environment controls and an
effective-placement view, followed by authenticated browser verification. Remaining
API parity, Human Review, package cleanup and legacy drain remain in the queue.

## Workflow defaults, step placement and named environments (2026-10-30)

Blueprint authoring/resolution now carries `execution_profile` and named
`environments`. Plan steps carry independent `execution` and
`condition_execution` selections using the same SDK-free value model as native
programs. Condition placement without a condition, ambiguous profile/environment
selection and undeclared environment references are rejected. The reusable resource
preference remains separate from these caller-owned choices.

The importer preserves these settings in a normal program definition. Ordinary
blueprint chat creation therefore pins the saved workflow default and step choices
in its unique published revision. An omitted/null step choice inherits the resource
preference; an explicit empty selection bypasses that preference for workflow/
platform defaults. Different steps may reuse one resource with different placement
without editing the resource. Named environments compile to existing engine-owned
bindings; no UnifAI environment manager or scheduler was added.

Approved-profile discovery now includes only the names whose engine factories
support retained environments, using the SDK's existing factory protocol rather
than another backend registry. Compilation rejects an unsupported retained profile
before dispatch. Public responses still omit images, policies, mount details and
environment values.

The workflow save dialog offers defaults, shared environments and independent
node/condition choices, showing the inherited source and per-run lifetime. Loading
and saving preserve those choices; removing a condition removes its placement.
The preview currently uses loaded resource preferences. An authoritative server
projection and authenticated React/browser validation remain required; API-client
and pure-data checks do not prove them.

Verification: **552 passed in 230.08 seconds**, zero failures/errors/skips or
reported warnings, at `/tmp/unifai-workflow-placement-platform-20261030.xml`.
The same isolated Mongo/Redis/Temporal and actual-client matrix was used; remote
program, OpenShell policy and paid Codex deployment modules were excluded. All six
separate-worker conditional replay cases are included. Focused application/
architecture/Local blueprint checks passed 172 cases; Mongo chat checks passed nine
cases, including multiple turns after blueprint edits. The six selected actual UI
client/editor cases passed separately; their `not sessions` filter deselected the
chat module, which was verified by its own run and then by the combined gate.

UI types and pure contracts pass. The production build completes in 4.57 seconds
with the existing vendor-cycle/chunk-size warnings at
`/tmp/unifai-workflow-placement-ui-build-20261030.log`. Changed Python paths pass
Ruff lint/format, the updated UI skill validates and `git diff --check` passes.
Run Engine source was not changed in this slice. Remote images have not been
refreshed for these source changes, and the experimental active-join dependency
and generic engine requests remain explicitly open.

## Read-only placement preview and authenticated dialog verification (2026-10-30)

New application-owned placement models/preview port and `BlueprintPlacementService`
authorize saved reads, resolve the normal authoring resources and inspect current
selection through the compiler adapter. Draft and saved HTTP endpoints return only
approved profile names, environment names and logical binding scope. Shared compiler
selection/capability checks and the normal dependency-closure validator are reused.
Preview performs no graph invocation, environment allocation, publication or secret
write. It validates static placement/construction references, not external provider
connectivity or arbitrary application-program behavior.

The first real preview tests exposed the normal bundle's literal-credential guard.
That guard remains intact. `ElementBundleResolver.validate` now shares the private
typed closure traversal with `resolve` but returns no portable bundle. The preview
therefore accepts local authored configuration without persisting it or putting raw
credentials into invocation payloads. A regression proves normal bundle creation
still refuses those credentials. Database snapshots and safe response assertions
cover draft and saved preview, inheritance, explicit reset, retained environments,
unsupported placement and owner rejection.

The editor uses the server response instead of client-computed effective placement.
It hides old results immediately after edits and discards unobserved preview cache
entries. Requests carry abort signals; query keys contain instance/generation
identity rather than authored configuration. The result is a current inspection,
not a reservation or persisted execution snapshot. Normal preparation validates
again and freezes the concrete backend configuration before submission.

The maintained isolated browser fixture renders the production workflow dialog,
auth provider and clients. Its native API uses the real signed-cookie authenticator
and Redis session; the fixture issues only a synthetic test identity. In the browser,
the dialog selected a workflow default, shared environment and independent condition
profile, saved/reloaded version 1, hid stale validation after an edit, canceled
unsaved changes, and updated/reloaded version 2. Used environments could not be
removed; removing an unused one was tested before cancellation. The server validated
all visible profile/binding results. The test did not start remote compute or paid
model calls. It does not establish full OAuth, resource-editor navigation or team
workspace switching.

The fixture tab closed, API process shut down and its own database/login session
were removed. A separate read found zero remaining browser fixture databases or
synthetic identity sessions. After final CLI cleanup handling was improved, a second
startup/shutdown check exited zero and printed the removed database identity.
The verified dialog screenshot is retained outside the repository in the thread's
visualization directory as `placement-browser-verified.png`. The UI diagnostics
skill documents building, running, exercising and cleaning this fixture.

Verification: **563 passed in 237.00 seconds**, zero failures/errors/skips or
reported warnings, at `/tmp/unifai-placement-preview-platform-20261030.xml`.
The matrix includes own Mongo/Redis/Temporal, separate API/worker processes and
production TypeScript clients. Remote-program, OpenShell-policy and paid-Codex
deployment modules remain excluded; no refreshed remote-image claim is made.
The focused core gate passed 163 cases and the nine preview/client cases passed
with the session-client case deselected; the latter is covered by the combined
gate. Expanded import/cold-import guards passed all nine architecture cases after
adding the preview service explicitly. Changed-path Ruff lint/format, UI types,
pure contracts, skill validation and `git diff --check` pass. The production UI
build completes in 4.82 seconds with existing vendor-cycle/chunk-size warnings
(`/tmp/unifai-placement-preview-ui-build-20261030.log`).

The full platform goal remains open, including remaining API/client parity,
Human Review, package cleanup, security/deployment validation and legacy drain.
Run Engine source was not changed in this slice; its documented prototype and
generic routing requests retain their prior status.

## Committed Run Engine adoption (2026-10-30)

The Run Engine owner delivered clean commit
`da10d1ac32e93a9752b9b5db1e0c71eced2f4b16`. It includes the earlier five
integration extensions and revised durable ACTIVE joins. UnifAI now imports
`GraphBuilder` / `JoinPolicy` from the public SDK and explicitly requests ACTIVE.
Historical patches moved to `integrations/archive/`; development, infrastructure
and diagnostic skills now use the committed baseline. No Run Engine source was
changed by this adoption pass. A local commit is verified; a push/release is not.

The original SDK reproduction now visits `[choose, yes, finish]` for a valid
selection. An unknown label still completes after `[choose]`: RE-07 remains open
and UnifAI retains its label validation. ACTIVE unresolved-frontier errors address
the corresponding stalled-join part of RE-08 without imposing a universal exit
requirement. See `integrations/README.md` for current handoff status.

Independent SDK checks: **135 passed**, no skips, one existing
`MapReduceState.items` warning, 30.40 seconds. This includes native Temporal on
UnifAI's dedicated `127.0.0.1:7234` plus thread/process invocation, deferred joins,
checkpoint policy checks and replay. JUnit:
`/tmp/unifai-engine-joins-temporal-adoption-20261030.xml`. The owner's much broader
SDK regression/lint/type evidence remains separately attributed in the integration
README; it was not rerun in full here. The earlier limited 95-pass/40-skip check is
superseded by the enabled run. UnifAI's focused condition/blueprint/Temporal check
also passed **45 cases** in 12.96 seconds.

Initial attempts under restricted execution could not bind/connect to local test
services: the SDK attempt had 40 setup errors, and the interrupted platform attempt
reported 333 passed, 3 binding failures and 5 setup errors. Those are environment
permission failures, not accepted regression results. Subsequent service-enabled
runs are authoritative. The restricted platform log is retained at
`/tmp/unifai-committed-engine-platform-restricted-20261030.log`.

Upgrade boundary: new builders default to ACTIVE; explicit ALL and old recorded
plans without policy retain ALL. Unreleased prototype policy/checkpoint layout is
incompatible. Rebuild unsubmitted prototype graphs and finish submitted runs on
their original compatible workers. Archive retention is not proof of actual drain.
The current combined and matched-image gates are recorded below.

### Native team-editing slice

An application-owned `TeamEditService` delegates entity authorization to existing
resource/blueprint services and atomic leases to a narrow store port. Its async
Redis adapter fences acquire/heartbeat/release by authenticated actor and editor
occurrence, refuses corrupt state, and never reacquires through heartbeat. Thin
FastAPI routes preserve resource/blueprint collaboration shapes and omit occurrence
IDs from holder replies. Membership and actor identity are authenticated; body
user/display fields do not confer authority. Composition owns the Redis client.

Native clients carry per-editor nonces, refuse failed renewal, guard saving until
acquisition, and release only their own occurrence. Workspace identity keys
remount the resource provider/editors. These are cooperative leases plus existing
document version checks, not transactional write locks. The feature is opt-in
with `UNIFAI_EDIT_LOCKS=true` and library enabled. Legacy Flask clients do not
provide full occurrence fencing; matched cutover and drain remain required.

Dedicated earlier checks passed 7 application, 16 real Redis and 3 authenticated
HTTP/Mongo/Redis cases; the final combined gate includes them and the single-status
route added afterward. TypeScript compile, UI contract checks and production
build passed; build retains existing vendor-cycle/chunk-size warnings. Full
workspace/resource editor/team-switch browser verification and same-workspace
request-race cleanup remain open. The focused placement browser evidence above
does not validate these new workspace changes.

### Current-source regression and remote adoption evidence

- Combined platform gate: **589 passed**, 239.65 seconds, zero failures/errors/
  skips or reported warnings. Includes TypeScript API clients and the new native
  team editing routes. Excluded the three explicitly separate remote-program,
  policy and paid coding modules.
  JUnit: `/tmp/unifai-committed-engine-platform-20261030.xml`.
- Remote programs: **28 passed**, 275.58 seconds, zero failures/errors/skips or
  reported warnings. Local/Temporal × Kubernetes/OpenShell; actual installed
  receivers construct transitive dependencies, execute graph/application/graph
  calls, project ancestry, share/borrow/release environments, load private settings
  outside payloads, replay native histories and verify physical cleanup.
  JUnit: `/tmp/unifai-committed-engine-remote-20261030.xml`.
- OpenShell policy: **8 passed**, 73.17 seconds, zero failures/errors/skips or
  reported warnings. Local/Temporal × invocation-owned/retained environments ×
  positive control/restricted egress. Actual allowed service receives requests;
  denied service receives none. Supported policy remains host/port/executable
  scope, not URL-path/method filtering.
  JUnit: `/tmp/unifai-committed-engine-policies-20261030.xml`.

Fresh images, built from committed SDK and current application source:

| Image | Verified identity | Source match |
| --- | --- | --- |
| `unifai-receiver:engine-da10d1ac-20261030` | `sha256:faf789433e7c03961c0a2c8d2f781dc68acb7370fcc6055e2f4d03d412af3758` | 1,173 Python files |
| `unifai-sandbox:engine-da10d1ac-20261030` | `sha256:426e01e60e51b270931ff7a63a4870b830b3ab72476d3f5dce4b109e601b5aaf` | 1,173 Python files |

Image report: `/tmp/unifai-engine-da10d1ac-images-20261030.jsonl`. The Kubernetes
image was loaded into `unifai-e2e` using its dedicated kubeconfig/context; the
OpenShell image preserves its supervisor entrypoint. Gateway 0.0.103, dispatcher
OpenShell SDK 0.0.104, Temporal SDK 1.35.0. Services remained UnifAI's independent
Mongo 27018, Redis 6380/15, Temporal 7234 and mTLS gateway 8090. No paid provider
calls, global context change or engine source edits were made. Fixture teardown
verified receiver absence and removed its namespaces/workspaces; shared test
services and fresh images remain available for subsequent authorized checks.

SDK joins, full UnifAI and remote checks overlap in contract coverage; their counts
are separate suite results, not a claim of that many distinct behaviors. They do
not close remaining full-workspace browser/API parity, Human Review element,
package consolidation, remote worker-loss/concurrent-coding, secret provisioning,
Celery, or actual legacy drain/cutover work in the ordered queue.

## Full workspace browser and strict-label follow-up (2026-10-30)

The previous goal turn made concrete SDK adoption progress. This continuation
worked the next workspace/parity item, then incorporated the owner's additional
strict-label commit. The migration goal remains active; the results here do not
close the full ordered queue.

### Actual workspace behavior and corrections

The maintained browser build includes the full production `App`, not only a dialog.
The runner's `--workspace` mode owns a separate synthetic membership HTTP service,
two unique teams and a personal identity with a real signed cookie in Redis.
Native MAS authoring, inspection and edit-lease routes use real Mongo/Redis and
the production session authenticator. Only external identity/terms/settings/
analytics are fixture responses. No OAuth provider or administrative configuration
service was started. MAS action/share responses were not replaced by fixtures.

The initial full App run found an optional-field JSON-schema bug: `required` was
assumed iterable even when Pydantic omitted it. The editor now treats absence as
empty and its TypeScript contract reflects valid JSON Schema. A real missing
`resource.validate` compatibility POST also caused invalid badges; a thin typed
route now delegates to the existing async inspection service and ignores the
request-authored credential user. A Mongo HTTP assertion checks the forged field
does not change the result or expose the stored credential.

Selection requests now have one cancellable lifetime each for instances, schema
and actions. Replacement/unmount aborts the old request; completed/error/finally
callbacks check the signal before changing selection state. Pagination forwards
the signal to all pages. Schema/actions loading states are independent, and schema
metadata requests run concurrently. `WorkspaceContent` keys resource, notification
and sharing provider lifetime by authenticated workspace; the layout still waits
for valid team selection before mounting resources.

Observed through the actual browser:

- Personal saved agent profile changed process -> thread, persisted as version 2
  and reopened as thread, preserving its LLM reference.
- Alpha/Beta team switches cleared prior selection/editor and loaded only the
  selected team's saved resources. Closing an editor during its displayed pending
  acquisition did not leave a lease.
- With actual mock-agent schema/list responses delayed, selecting Mock Agent Node
  then Router Boolean kept the condition's card and schema after the delay.
- A Beta condition profile changed to process, persisted as version 2 and reopened
  correctly. Store inspection confirmed profile metadata remains outside cfg_dict.
- After the final provider-boundary refactor, a fresh fixture repeated team profile
  save/reload and a team switch. The Alpha condition reopened as process/version 2.

The final screenshot is
`/Users/odaiodeh/.codex/visualizations/2026/10/28/01a183fd-8230-74d3-a2f0-9abb2671a4cc/workspace-team-profile-verified.png`.
Both owned API/membership servers and tabs were closed. Initial and final fixture
cleanup reads found zero remaining browser databases, synthetic browser sessions
and owned team leases. Reports:
`/tmp/unifai-workspace-browser-cleanup-20261030.json` and
`/tmp/unifai-workspace-final-cleanup-20261030.json`. Shared services remain running.

Focused inspection/team-edit/architecture check: **14 passed**, 4.70 seconds,
`/tmp/unifai-workspace-validation-20261030.xml`. TypeScript compilation, pure UI
contracts and browser build passed; existing vendor-cycle/chunk-size build warnings
remain. A broader workspace run passed 589 cases in 239.30 seconds, but the SDK
checkout changed during that run and the compiler/provider changes followed it.
It is not the final strict-label baseline gate; use the fresh result below.

Confirmed unfinished parity: `/actions/actions.list` and share notification list
return 404 in the native API. The separate `/api4` admin check was unavailable in
this fixture. The old action package still imports a sync bridge and singleton
registry; migrate its discovery/execution through clean async application contracts
and adapters rather than wiring that legacy package into native cold imports.
Notification/share callback behavior with successful real responses, account
switches, full workflow editor navigation and broader session callbacks still need
coverage. This browser result does not certify whole-application parity.

### Strict routing SDK

Clean owner commit `60393440efd3876cd6c81e0b013e8bf6d9167659` fixes RE-07.
UnifAI's adapter explicitly selects public `UnknownLabelPolicy.ERROR` beside
`JoinPolicy.ACTIVE`; its compiler integration asserts the serialized policy.
Product boolean/END normalization and application label validation remain in UnifAI.
The unchanged SDK reproduction still reaches finish for yes and now raises
`UNKNOWN_CONDITION_LABEL` for typo, with contract origin and only the configured
source node in details. No returned value is echoed by that failure.

New plans default ERROR; old recorded inputs/checkpoints without policy retain
IGNORE. Whole selections are validated before scheduling successors. Empty list/
tuple means no route; string labels have no implicit terminal spelling. Checkpoint
policy mismatches are refused. Old strict coordinators reject ERROR inputs. Deploy
matched implementations and review graph construction within durable programs;
these checks do not establish arbitrary upgrades or actual legacy drain. Ordinary
condition return values may still occur in native invocation histories.

Independent focused SDK gate: **232 passed**, no skips, one existing
`MapReduceState.items` warning, 49.37 seconds. Covers strict/legacy routing, privacy,
atomic successor scheduling, label/checkpoint compatibility and native replay plus
active-join regressions, using UnifAI Temporal 7234 and thread/process receivers.
JUnit: `/tmp/unifai-engine-label-policy-adoption-20261030.xml`. Broader SDK gates
in the owner's verification document are separately reported, not rerun here in
full. Current-source UnifAI and fresh remote-image results follow when complete.

Current strict-label UnifAI gate: **589 passed**, 301.45 seconds, zero failures/
errors/skips or reported warnings. Includes the compiled ERROR-policy assertion,
actual native Temporal conditions/replay, sessions, authoring, inspections, edit
leases and production TypeScript API clients. Excluded the three separately selected
remote program, OpenShell policy and paid coding modules.
JUnit: `/tmp/unifai-strict-label-platform-20261030.xml`. Source stayed fixed for
this fresh run. TypeScript compile/browser build and focused Python lint/format
checks passed. Updated session/UI and platform-test skills pass quick validation.

Plan recorded before the native action implementation below: preserve stable action UIDs
and schema hints, but put the async action contract/metadata/registry/service in
application ownership. Inject registrations and dependencies per composition; do
not reuse the legacy singleton or subclass-global discovery as native runtime
state. Keep provider SDK/network implementations in adapters and use the existing
async provider/auth services. The legacy RAG action implementations still call
async provider operations as if synchronous, and some auth actions omit awaits
after earlier service migration. OpenAI capability loading also has a process-
global cache that can cross injected readers. Correct those behaviors with
instance-owned dependencies/cache and actual port/adapter tests; wiring only the
list endpoint would leave action execution broken. Credential identity comes from
authentication, separate from workspace ownership. No native action import may
load the old sync bridge; any still-required Flask compatibility belongs at its
legacy adapter boundary until full cutover. These are next-step constraints, not
a claim that native actions are already migrated.

### Final strict-label remote evidence

The rebuilt receiver images each match **1,175 Python files** from SDK, shared
utilities, current UnifAI application/adapters/bootstrap/config and installed test
fixtures. Report: `/tmp/unifai-engine-6039344-images-20261030.jsonl`.

| Image | Verified identity |
| --- | --- |
| `unifai-receiver:engine-6039344-20261030` | `sha256:aa1759021d030cf68870fdd654c3c0ea360274160c486030f3a3ea8eabced9bf` |
| `unifai-sandbox:engine-6039344-20261030` | `sha256:106ffd3ea2c037c9793c23f142b239107c1e80607bc61bdc6b0358d7f13c5ac1` |

**28 passed**, 358.81 seconds, zero failures/errors/skips or reported warnings:
`/tmp/unifai-strict-label-remote-20261030.xml`. This is the actual existing program
composition/dependency/ancestry/private-settings/environment lifetime/borrowing/
failure cleanup matrix across Local/Temporal and Kubernetes/OpenShell. Native
histories replay and fixtures verify physical receiver removal. It does not claim
remote unknown-label condition invocation specifically; those routing contracts
were checked with thread/process invocation in the 232-case SDK gate.

OpenShell allow/deny policy's 8-case result remains dated to `da10d1ac`; it was not
repeated for this label-only SDK change. Paid coding/LLM tests, Celery, remote
worker loss and concurrent coding remain outside this verification. No Run Engine
source edits or commits were made by UnifAI; the owner checkout remains clean at
`60393440efd3876cd6c81e0b013e8bf6d9167659`. A published release/push was not checked.
Matched images and independent test services remain available for subsequent work.
The active goal is not complete: continue with the native action/share parity
prerequisite and the remaining ordered migration requirements.

## Native async action migration (2026-10-30)

The missing native discovery/execution routes are implemented through thin
authenticated FastAPI adapters. `mas.application.actions` now owns typed contracts,
metadata, instance registrations, dispatch and credential use cases;
`outbound.actions` owns provider/SDK/model configuration probes. `bootstrap.actions`
injects dependencies and explicit registrations. Stable UIDs and element form
schemas are preserved. The old `mas.actions` package is removed rather than kept
as forwarding modules. These authoring operations are not persisted graph
entrypoints; installed graph element references were not renamed by this slice.

This fixes the old RAG actions' unawaited async operations, missing auth awaits,
blocking credential reads on the event loop, global capability-cache mixing and
type-only metadata filtering. The service rejects synchronous/class registrations,
validates results and keeps raw provider/input values outside public errors.
Credentials always use the authenticated human, independently of verified team
ownership. RAG headers are per request; no shared mutable authorization headers.
RAG/A2A HTTP clients close on success, failure and cancellation. A2A cards become
portable JSON at the adapter boundary. Retained blocking credential stores are
awaited off-loop under ownership. The legacy Flask action endpoint alone adapts
this service through the old bridge until cutover; this is not a claim that all
legacy bridges have been removed.

Native settings use the composition-owned asynchronous Mongo client; the
`openai_model_capabilities` reader/cache is injected per composition. Both OpenAI
dropdowns share that cache. RAG uses its own async probe client and shared wire
models without importing the old Flask client. Optional Vertex registration is
absent in this environment because its external SDK is missing; no live Vertex
or paid provider behavior is certified.

Evidence:

- Broad gate: **611 passed**, 245.53 seconds, no failures/errors/skips or reported
  warnings: `/tmp/unifai-native-actions-final-platform-20261030.xml`. The separate
  remote-program, policy and paid coding modules were excluded. The subsequent
  disabled-auth error-classification correction has focused current-source evidence.
- Current action/architecture/cache/provider/credential/shared-edit-fixture gate:
  **35 passed**, 7.45 seconds, no failures/errors/skips or reported warnings:
  `/tmp/unifai-native-actions-current-20261030.xml`. Uses real signed-cookie Redis,
  encrypted Mongo credentials and separate native API/MCP/RAG protocol services.
- Expanded static/cold-import guards pass **9 cases**, 1.83 seconds:
  `/tmp/unifai-native-actions-boundaries-20261030.xml`. They now cover action adapter
  imports/composition and credential-action imports, in addition to application dispatch.
- Strict mypy passes **45 source files** for the action slice; focused Ruff lint
  and formatting pass. This does not claim repository-wide strict typing.
- The actual full App builds and its OpenAI form populates model and reasoning
  selections via successful native requests. Synthetic capabilities are seeded in
  the fixture's unique Mongo database; no LLM call or resource save occurs. Browser
  proof: `native-actions-browser-verified.png` in this thread's visualization folder.
  The tab and both fixture servers are closed. Cleanup independently found zero
  browser databases/sessions: `/tmp/unifai-native-actions-browser-cleanup-20261030.json`.

The full App still exposes missing share notifications and does not start the
separate admin configuration service. OAuth onboarding/callbacks and the remaining
queue are unfinished. The new tested
[action diagnostic skill](../.cursor/skills/debug-native-actions/SKILL.md) records
the boundary/identity/lifetime workflow; it and the updated session/platform test
skills pass validation. Current receiver identities and remote results follow.

Both fresh images match **1,178 Python files** against SDK/application/adapter/
composition/configuration/fixture source:
`/tmp/unifai-actions-images-20261030.jsonl`.

| Image | Verified identity |
| --- | --- |
| `unifai-receiver:actions-20261030` | `sha256:a633cfe8b54bcaf815fbe8d428fb9600255f2ea067e97f0709a532522e70bb3f` |
| `unifai-sandbox:actions-20261030` | `sha256:382727ea5307f92cf28614f1b82bbcf1e0f5b20243daab93cd5f2be8ef36738b` |

The rebuilt Kubernetes receiver was loaded into dedicated `unifai-e2e`.
The current-source remote matrix passes **28 cases**, 358.78 seconds, zero
failures/errors/skips or reported warnings:
`/tmp/unifai-native-actions-remote-20261030.xml`. Includes Local/Temporal hosts
with Kubernetes/OpenShell, actual dependency construction, program ancestry,
private receiver settings, owned/borrowed environments, cleanup and native replay.
It does not invoke unknown-label conditions remotely or certify live provider,
concurrent coding, Celery or worker-loss scenarios. The test services remain
available; Run Engine source is still clean at `6039344`.

## Native invitation notifications (2026-10-30)

Native list/details/decline/cancel now delegate to `ShareNotifications`, an async
application service over a narrow repository port. Shared invitation values moved
to `mas.domain.sharing`; legacy sharing consumers use the same models. The native
path does not import the old cloner, singleton services or bridge. Cleanup-only
legacy models remain with the old sharing implementation. Canonical SDK-free
identity data remains in `mas.core.identity`, explicitly covered by inward/cold
import guards rather than duplicated in a second identity hierarchy.

The Mongo adapter borrows the owned async client; memory storage retains independent
snapshots. Native reads accept legacy JSON string dates and BSON datetimes, normalize
UTC and sort by converted creation time plus share ID. Literal escaped user matching
is rechecked against domain identity before pagination, preventing regex Unicode
equivalents from widening access. Team names remain exact and type-scoped. Review
complete arbitrary Unicode legacy user-alias discovery before cutover: safe
authorization filtering does not establish discovery of every historical alias.

The inbound adapter preserves flattened sender/recipient labels and existing
request fields; internal authorized-owner pools are omitted. Authentication supplies
the selected typed workspace. Team detail/decision requests require explicit
`teamId`. Pending decline/cancel changes are conditional and atomic; identical
retries succeed, competing outcomes conflict, and stored accepted outcomes are
preserved. This claim covers native decisions, not concurrent legacy acceptance.

The UI carries team scope and abort signals. Notification refreshes and mutation
callbacks are fenced to their workspace lifetime; replaced polling cannot overwrite
a newer refresh. Successful mutations reload actual data. Expired invitations do
not contribute to the unread pending count. The full App fixture seeds actual
personal and two-team Mongo invitations; Alpha responses are deliberately delayed.

Evidence:

- **627 passed**, 249.38 seconds, zero failures/errors/skips or reported warnings:
  `/tmp/unifai-native-notifications-platform-20261030.xml`. Includes domain/app/
  architecture, shared memory/Mongo storage contracts, signed-cookie Redis/Mongo
  ownership, real provider protocol tests, native Temporal/replay and all selected
  production TypeScript clients. Remote programs, policy and paid coding modules
  are selected separately. The earlier 27-case integrated gate was superseded.
- Strict mypy passes the **6 new sharing source files**. Focused Ruff lint/format,
  UI typechecking and the actual App browser build pass. The build retains the
  existing vendor chunk/size warnings; these checks do not establish repo-wide
  strict typing or full product parity.
- The actual App displays personal/team invitations, declines them via native
  requests and retains the resolved team outcome after reload. A rapid Alpha/Beta
  switch leaves the current team's empty pending state intact. Screenshots:
  `native-team-notifications.png`, `native-notification-declined.png` and
  `native-notifications-verified.png` in this thread's visualization folder.
  All notification requests observed in the API log returned 200.
- Browser tab and both fixture processes were closed. Independent cleanup found no
  owned database or browser identity session:
  `/tmp/unifai-notifications-browser-cleanup-20261030.json`. Test services remain.
- The new [sharing diagnostic skill](../.cursor/skills/debug-sharing/SKILL.md) and
  updated session/platform test skills pass validation. Domain test scenarios
  import domain values only; shared repository contracts belong to application
  support and are reused by actual adapters.

The initial receiver verification correctly rejected a support-fixture edit made
after image build started. Both fixture layers were rebuilt; final images match
**1,186 Python files**: `/tmp/unifai-notifications-images-20261030.jsonl`.
The verifier now reports the actual mismatched source names instead of only a
generic subprocess exception.

| Image | Verified identity |
| --- | --- |
| `unifai-receiver:notifications-20261030` | `sha256:dca7cd114d2b06c856218b1ed7a02927c35a9ee359eb6d6215ae6a0fe0ce7dc2` |
| `unifai-sandbox:notifications-20261030` | `sha256:61010a443aca07842c776cce708d898aba3766ab93889228a1967d4b7b3d7d3b` |

Remaining sharing work is substantive: native create/accept/team-copy use cases,
typed ownership across the complete dependency closure, registered secret-field
treatment, built-in/public references, portable graph remapping and resumable or
compensated copy failure. Repair TTL/retention semantics before writing new BSON
expiries into a collection with the legacy TTL index: its old ISO-string records
do not expire automatically, while accepted audit records must be preserved.
Do not expose old cloning through a generic off-loop
facade and call the migration complete. Existing resource factories, reference
walkers and application authoring boundaries should be reused. Check whether graph
step identifiers are local before regenerating them or replacing arbitrary strings.
No advanced agent orchestration is added. Default startup remains legacy until
complete parity, deployment checks and actual legacy drain are verified.

Final matched-image remote gate: **28 passed**, 403.32 seconds, zero failures/
errors/skips or reported warnings:
`/tmp/unifai-native-notifications-remote-20261030.xml`. This reruns the existing
program/dependency/ancestry/private-settings/environment borrowing/failure-cleanup
matrix across Local/Temporal and Kubernetes/OpenShell, including native history
replay and physical receiver cleanup. It verifies the module/composition changes
in those environments; invitation operations themselves run in the API and were
tested through real HTTP/Mongo/Redis above. No paid provider/coding calls, Celery,
worker-loss scenario or legacy drain is claimed. Production UI build and current
UI typechecking also pass; vendor chunk/size warnings remain as recorded.
