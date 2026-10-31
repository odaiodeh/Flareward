# Program platform development

This describes the implemented foundation. The full migration is still in progress;
see [the completion ledger](execution-platform-migration.md).

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

UnifAI explicitly selects public `JoinPolicy.ACTIVE` and `UnknownLabelPolicy.ERROR`.
Earlier serialized plans without these policies retain ALL/IGNORE behavior.
Strict routing validates the entire result and fails with `UNKNOWN_CONDITION_LABEL`
before scheduling successors. Safe diagnostics do not remove return values from
native invocation histories; keep private values outside routing output. The unreleased local ACTIVE prototype uses
an incompatible payload/checkpoint layout: rebuild unsubmitted graphs and finish
submitted prototype executions on their original compatible workers. Do not remove
old workers until drain is verified. Rebuild matched coordinator/receiver images
before remote deployment; historical remote test results do not validate new SDK
source. See [integration status and recovery notes](../integrations/README.md).

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
Native async element calls are awaited directly. Elements can return UnifAI's
GraphState; the receiver adapts it to the engine state contract and retains
program-specific channels outside that result.

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
         |                    |                    | invoke coding node |
         |                    |                    |-- coding port ---->|
         |                    |                    |                    | run CLI
         |                    |                    |<-- typed result ---|
         |                    |<-- state update ---|                    |
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
Only nodes and conditions accept that preference; a dependent LLM or tool is
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

Further consolidation remains: program/session/resource services retain their
existing `mas.programs`, `mas.execution`, `mas.session`, `mas.resources` and related
paths. Concrete plugins and their schemas/factories remain in `mas.elements` for now.
Further plugin thinning and physical plugin relocation are the next structural slice;
this extraction does not claim that the whole package migration is finished.
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

Extract shared domain/application code first, then thin plugin adapters. Audit
duplicates and unused legacy helpers during that move. Check published revisions,
prepared execution snapshots, installed function/spec references, and compatibility
requirements before changing module paths. Retain compatibility only where an
actual public/persisted contract requires it, with a drain/removal condition.
Update bootstrap/package discovery and imports together. Extend architecture and
cold-import checks so the directory names correspond to enforced boundaries; run
saved-resource/blueprint/session E2E and replay as behavioral regression. Remote
images require rebuilding after installed-module moves. No unrelated service
reorganization is included.

The shared Python import paths changed in this development migration; repository
callers use the new owners directly. Registered element type keys, specification
module paths and installed engine entrypoints remain unchanged in this slice.
Published resource configuration keeps its existing JSON shape. This does not
promise replay compatibility for arbitrary old Python references: keep older
workers on their compatible release until their executions drain. Do not add
forwarding aliases solely to preserve the old folder layout.

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

Define an installed async function accepting `(runtime, inputs, configuration)`.
`runtime` implements the application-owned `ProgramRuntime` protocol. Register the
function, its configuration schema, and its stable implementation key/version using
`ApplicationRegistry` in the composition root.

Create an `ApplicationDefinition` referring to that registration, save it through
`ProgramService`, and publish a revision. A graph calls it with `ProgramCallStep`.
Declare child program revisions explicitly; the runtime starts those prepared
children through Run Engine instead of importing repositories in coordination code.

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
defaults. The save response is the normalized definition. Callers should retain
that response when editing an existing definition, including opaque credential
references, rather than reconstructing private values from display masks.
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
the resolved configuration and returns the normalized definition. Publish it
through `POST /api/programs/{program_id}/revisions`; later edits or reimports alter
the draft while earlier published revisions keep their original configuration.

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
special authority. Administrative lifecycle operations remain on the migration ledger.

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
quota policy, and deployment drain checks remain on the full migration ledger.
Native run history lives in Mongo and survives deletion of its calendar.

## Durable worker and deployment

Run the API and a separate worker with the same `UNIFAI_HOST` endpoint, namespace,
and task queue. The default queue is `unifai-programs-v2`; keep legacy workers and
their original queues available to drain earlier executions.

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
file path through that selection. All configured profiles are available to program
authors; this is not a per-user profile authorization system. Expose only profiles
appropriate for the deployment's authors.

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
validation remain separate gates in the migration ledger.

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

Active native-preview records without a stored location cannot be safely recovered
by the new application. Finish those runs with their compatible deployment before
upgrading. This is separate from draining legacy UnifAI workers and queues.

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

## Planned Human Review step

Status: investigated design, not implemented. Implement after the native async
agent/tool refactor, before expanding live-provider tests. This adds the explicitly
requested human-interaction behavior; it does not introduce agent delegation.

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
tool approvals use a different synchronous gate and Redis tickets; those tests
do not prove durable Human Review.

**Application representation.** Call the feature **Human Review**. Implement one
registered, versioned application program. Use the existing `ProgramCallStep` so
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
this use case. Database access, notifications, and opening/finalizing the request
run as invoked effects through the existing runtime boundary. The application
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
contracts stay on the migration ledger.

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

`codex_agent_node` is a catalog element backed by the installed Codex CLI. Its
`CodexAgentNodeFactory` builds the concrete `CodexAgentNode`, whose adapter binds
`CodexCodingAgent` to the application-owned `CodingAgent` port and `CodingAgentNode`.
The package follows sibling node naming: `config.py`, `identifiers.py` with
`Identifier`/`META`, `codex_agent_node.py`, `codex_agent_node_factory.py`, and
`spec/spec.py` declaring `CodexAgentNodeElementSpec`. Like the existing simple
nodes, it uses Pydantic validation and the default card builder rather than empty
custom validator/card classes. Shared node contracts now live in
`mas.application.elements.node` and `node_config`; vendor plugins import inward.
The coding workflow implementation has no CLI, OpenShell or Run Engine imports.

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

The receiver-local `UNIFAI_CODING_WORKSPACE_ROOT` defaults to `/tmp/unifai-coding`.
Within it, a hash of the root execution identity and a validated workspace name
select the work directory. Sibling steps and child programs in the same imported
environment can deliberately share that directory; other root executions use a
different directory. The initial contract supports sequential work on a shared
workspace. Authors should use different names for parallel independent edits.
These files belong to the execution environment, not durable artifact storage.
Local thread placement leaves files on the operator's worker; choose a disposable
remote environment when its destruction should remove the workspace.

Each invocation starts a fresh noninteractive `codex exec --json --ephemeral` turn.
Workflow state carries the previous step's answer; files carry repository changes.
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
flows remain outstanding; see the migration ledger.

These leases coordinate cooperative editors; resource/blueprint version checks
remain the persistence conflict boundary. They do not make writes transactional
with Redis. Older Flask clients use user-only leases, so a mixed deployment does
not provide complete occurrence fencing. Cut over matched clients/routes and
verify legacy-editor drain before claiming that guarantee.
