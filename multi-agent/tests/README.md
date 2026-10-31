# Platform tests

Tests follow the application's dependency direction and use small, explicit
compositions rather than a shared test superclass.

- `domain/` checks portable values and pure invariants: independent JSON tool
  schemas, typed workspace artifacts/results/variables after persistence, and
  retry budgets without application services.
  `test_sharing.py` checks shared invitation TTL/UTC compatibility and typed
  participant namespaces; its scenarios import domain values only.
- `application/` tests publication, execution lifecycle, and resource construction.
  Execution tests use a signature-checked double of the application-owned gateway
  port. They do not construct an engine, HTTP server, or database client.
  `test_actions.py` verifies instance-owned registrations, typed dispatch,
  trusted credential identity, private failures and cancellation using the shared
  application-only `support/action_scenarios.py`.
  `test_share_notifications.py` checks invitation authorization, repeated/racing
  decisions and cancellation through a signature-checked async storage port.
  Resource/overlay authoring uses signature-checked repository ports and a scoped
  cipher double; actual encryption-format compatibility is tested in adapters.
  `test_element_preparation.py` verifies that native preparation finishes before
  dependent factories run, and that failure/cancellation/private errors retain
  cleanup and masking.
  `test_session_approval_rules.py` uses signature-checked persistence/publication
  ports to verify concurrent policy commands, persisted-but-unsynchronized
  recovery after service restart, denied/stale writes and stable observation
  versions. No Redis or repository adapter is constructed in those tests.
- `adapters/http/` tests authentication transport contracts with controlled Redis
  and HTTP collaborators.
  `adapters/test_action_capabilities.py` checks concurrent cache loads, detached
  values and independent readers. Action HTTP/credential integration uses
  `support/team_http.py` and `integration/redis/test_actions.py` with actual Redis,
  Mongo and signed-cookie authentication. Provider action tests exercise actual
  MCP/RAG HTTP plus success/failure/cancellation and concurrent identity headers
  for owned HTTP clients. No paid model calls are required.
  `support/share_notification_contracts.py` runs the same notification behavior
  against actual memory and Mongo storage. Mongo cases mix legacy string/BSON
  dates, stable sorting, escaped identities and concurrent pending decisions.
  Signed-cookie Redis/Mongo cases verify user/team scope and HTTP response privacy.
- `adapters/mongo/` verifies that legacy blueprint resolution runs off the event
  loop, drains on cancellation, preserves application access denials, and omits
  private configuration from translated storage/validation errors.
- `adapters/test_async_provider_validation.py` verifies native MCP/A2A deadlines,
  repeated cancellation, human credential binding, and rejection of missing/expired
  credentials before transport entry. Application tests separately verify async
  validation dependency reports and owned blocking credential-store calls.
- `adapters/test_native_tracing.py` checks actual OTLP HTTP export, independent
  concurrent/later owners, masking, unchanged global provider, physical batch-thread
  teardown, and cancellation during resource acquisition and pending export.
- `adapters/test_execution_policies.py` checks operator-file validation, startup
  refusal before opening clients, environment configuration, independent compiled
  snapshots, and keeping local paths outside portable program requests.
- `integration/providers/` uses the installed MCP client/server SDK and A2A card
  resolver through HTTPX ASGI transports. It verifies real authenticated protocol
  handshakes, HTTP rejection, timeout, cancellation, and closed HTTP clients without
  an async bridge. It does not require a live external provider or service container.
  Selected-provider-tool cases build actual MCP provider/tool specs through the
  bundle builder, bind real server schemas and check missing tools and failed
  protocol results. AnyIO-backed server lifespans enter and exit in the same task;
  pytest async fixture setup/teardown may use distinct tasks, so the fixture supplies
  the app while the test owns its lifespan.
- `integration/` tests the actual Run Engine, native FastAPI composition, existing
  blueprint resolver/factories, and persistence adapters. Its fixture owns and
  closes each Local host. Mongo tests require `UNIFAI_TEST_MONGO_URI` and create
  uniquely named databases that the fixture removes afterward. Redis tests require
  `UNIFAI_TEST_REDIS_URI` and remove only their unique execution keys. Both exercise
  actual thread and process receiver boundaries.
  Redis interaction scenarios additionally verify execution-bound decisions,
  child event roots, same request IDs across turns, persistent defaults, cache
  reconstruction, delayed revision fences and execution-only replacement.
  `mongo/test_mcp_agent_sessions.py` starts a real loopback MCP service with the
  shared owned ASGI process helper. Two actual agents execute a selected saved
  tool through its saved provider dependency across two turns. Shared behavioral
  assertions require successful results, conversation/workspace continuity and IEM
  acknowledgments. Editing the saved provider after publication leaves the next
  turn on its original snapshot. These cases use deterministic model behavior.
  Stored-library contracts use real Mongo documents, existing blueprint/resource
  services and factories, user/team overlays, protected program publication, and
  native session execution. Those tests do not replace the remaining authoring
  HTTP compatibility work.
  Workflow placement contracts preserve defaults, named environments and separate
  node/condition overrides through schema parsing, resolution, import and immutable
  publication. Mongo chat cases run multiple turns after authoring changes; shared
  resource preferences remain unchanged. Null step placement inherits the resource;
  an explicit empty selection bypasses it for workflow/platform defaults. Compiler
  cases verify engine-owned environment bindings and reject unsupported retained
  backends before dispatch; these are not physical remote provisioning tests.
  `mongo/test_blueprint_placement.py` inspects draft/saved placement through the
  application preview port and real compiler adapter. It verifies approved names,
  inherited/overridden preferences, run-scoped bindings, unchanged database records,
  foreign-owner rejection and absence of secrets/backend settings from responses.
  The read-only dependency validator shares the execution resolver's traversal;
  it does not export a bundle or weaken literal-secret protection.
  Registry-driven blueprint contracts also author, inspect, publish, and execute
  installed plugins absent from legacy category unions. They cover inline/saved
  transitive dependencies in thread/process receivers, outer type dispatch for
  configurations without internal discriminators, and protection of plugin secret
  hints before persistence.
  Native resource contracts also cover encrypted round trips, transitive reference
  usage, owner/team/built-in visibility, concurrent versioned edits, legacy writer
  interference, overlay reset fences, and published snapshots surviving deletion
  of their authoring resources. Shared built-in ciphertext is absent from public
  responses; only the caller's own allowed overlay appears.
  Inspection contracts use actual deterministic validators and card builders to
  verify dependency results, caller overlays, team ownership, and encrypted human
  credential lookup. They also cover missing/cyclic dependencies, safe provider
  exceptions, inline dependency authorization, and request bounds.
  Blueprint inspection additionally verifies local hydration of opaque references,
  no writes during draft validation/cards, saved ownership before parsing, copied
  foreign-reference rejection, typed dependency order/category checks, and preserved
  stored records. Shared diagnostic tests verify declared-secret redaction without
  mutating configuration, identifiers, validation codes, or nested model types.
  Native MCP/A2A API contracts use actual installed validators and encrypted Mongo
  credentials while substituting only provider transports. Saved/inline resources
  and saved/draft blueprints must all use async provider entry points on the caller
  loop, preserving human/team identity separation.
  Infrastructure fixtures share the production owned Redis scope, including pool
  cleanup after socket closure; cancellation ownership also has an adapter test.
- `integration/temporal/` uses `UNIFAI_TEST_TEMPORAL_ENDPOINT` with unique queues.
  It exercises actual coordination, child projection, history replay, CLI worker
  crashes and replacement, and durable message waits. The HTTP restart test also
  uses Mongo and rejects coordinator configuration drift before reconnecting to
  the original run. Configuration-secret contracts also need Mongo; they inspect
  durable history for tested plaintext values on success/failure and replay it.
  Test support owns and reaps only the worker processes it starts.
- `integration/deployment/` requires Mongo, Redis, and Temporal. It starts a real
  HTTP server and separate worker, verifies signed-cookie identity against Redis,
  creates an encrypted LLM and dependent node through HTTP, authors/imports/publishes
  a referenced blueprint after validating resources and inspecting the saved blueprint,
  runs a session in thread/process targets,
  reads events, restarts the API, sends durable input, and cancels work. It checks
  history replay and graceful shutdown. POSIX socket inheritance avoids claiming
  an ephemeral port and then racing another process for it.
  `test_session_approvals.py` restarts the actual API while a Temporal worker is
  waiting for a human decision, deletes only its owned live-rule cache and checks
  reconstruction from Mongo, the surviving pending ticket, the decision, a second
  auto-approved turn and replay on thread/process backends. It uses the same
  cookie, resource, pending-ticket, server and worker helpers as other cases.
  Teardown resolves native identities through the typed execution repository,
  releases pending gates and waits for owned workflows before deleting Redis keys.
  `test_remote_programs.py` additionally selects actual Kubernetes/OpenShell
  placement with `--platform-backends=k8s,openshell` and independent coordination
  hosts with `--platform-hosts=local,temporal`. It uses installed deterministic
  elements with transitive dependencies, verifies physical receiver identity,
  ordinary/retained lifetime, graph/application/graph ancestry, failure cleanup,
  explicit child environment borrowing, and native history replay. Receiver-local
  files prove shared workspace reuse; a child-owned scope must release before its
  parent finishes. Private-settings cases verify authenticated collector traffic
  while keeping raw/encoded keys out of execution records and history. Each
  backend/host pair has seven cases. Without an
  explicit backend selection remote cases skip; selected unavailable backends fail.
  The [independent infrastructure guide](infra/README.md) provides UnifAI-owned
  Docker services, images, mTLS gateway, and a dedicated kind kubeconfig.
  `test_openshell_policies.py` uses those same API, worker and backend fixtures.
  It runs an installed HTTP-probe element with operator-file policy data and checks
  real allow/deny behavior against two reachable local services. Local/Temporal
  hosts and invocation-owned/retained environments are independent dimensions.
  Successful HTTP bodies identify the actual service; denied destinations must
  receive zero requests. The separate positive control allows both destinations.
  This tests host/port rules, not HTTP path or method filtering.
  `test_schedules.py` uses real calendars and separate API/worker processes for
  graph/thread, graph/process, application, and composed programs. It verifies
  pinned revisions, owner-scoped creation keys, execution while the API is down,
  actual automatic firing, finite-budget reactivation, manual one-off semantics,
  all overlap policies, pause/resume, history after deletion, and concurrent edits.
  Controlled SDK interceptors hold two real descriptions with the same native
  conflict token; the test still uses the actual calendar service for both writes.
  Native generation pins distinguish rapid actions sharing a workflow ID. Replay
  selects the original namespace and exact native generation. Shared application
  requests live in `support/scheduling.py`; native calendar ownership and controlled
  transport observation live in `support/calendar.py`.
  `test_tracing.py` runs real API/worker processes and concurrent graph children
  in thread/process receivers under both hosts. It verifies nested observations,
  session/root/parent identity, safe failure classification, collector outages,
  and replay. `support/telemetry.py` owns a local OTLP HTTP endpoint and decodes
  actual protobuf requests; `support/tracing_elements.py` is application-only
  deterministic instrumentation. These tests do not require a vendor account or
  claim to verify Langfuse's server-side ingestion and aggregation.
  `test_agent_sessions.py` uses the actual question, custom-agent, and final-answer
  nodes, a scripted tool-calling LLM, and transitive shared tool resources authored
  through HTTP. It verifies two turns with API restart, signed-cookie/Redis identity,
  tool-derived evidence, agent success, workspace/IEM continuity, token streaming,
  thread/process placement, and replay. Its Mongo counterpart also edits a saved
  dependency after publication. Domain assertions and scenarios are shared in
  `support/agent_session*`; HTTP/process/backend work stays in infrastructure support.
  These scenarios provide the behavioral baseline for the native async
  node/agent/LLM call chain. They make no paid model calls; tool/approval contract
  migration and optional SDK-backed agent execution still need their own evidence.
- `architecture/` checks production import direction, imports hidden by package
  initializers, native async boundaries, and test-layer separation. The extracted
  `mas.domain` and `mas.application` packages cannot import element plugins or
  transport SDKs. Cold agent imports also reject global infrastructure settings.
  Shared agent tests compose real application capabilities with a model-port double;
  saved-resource session tests exercise the actual registered graph nodes.
- `support/` contains reusable data/scenarios and deterministic installed elements
  and application programs. Those fixtures use application contracts.
  `engine_functions.py` contains engine-specific state fixtures; `temporal.py`
  contains infrastructure replay support. `processes.py` owns the shared API/worker
  process lifecycle; `server.py` owns real HTTP startup and shutdown checks.
  `remote.py` and `remote_scenarios.py` use application contracts. Backend-specific
  support modules isolate their SDKs and own unique namespaces/workspaces.

The root composition creates application services without an execution host.
Native agent iteration and tool cancellation contracts are covered by
`application/test_agent_execution.py`. The three LLM adapter protocols use real
async SDKs with in-memory HTTP/SSE transports in `adapters/test_async_llms.py` and
shared `support/llm_wire.py`. Completion, early exit, mid-stream errors,
cancellation, and client ownership are checked without live model calls. The
`dev` extra includes the OpenAI and Gemini SDKs; standalone adapter development
can install `mas[openai,gemini]`.

Integration setup extends that composition with explicit adapters. Program
registrations have one shared definition, and resource tracking is scoped to each
test. Test modules do not import other test modules. Assertions target observable
behavior and contracts; runtime integration tests exercise real execution rather
than substituting an application-side scheduler.

Run from the repository root:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/architecture -q
.venv/bin/python -m pytest multi-agent/tests -q
.venv/bin/python -m pytest multi-agent/tests/integration/providers -q -W default
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27017 .venv/bin/python -m pytest multi-agent/tests -q
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27017 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6379/0 \
UNIFAI_TEST_TEMPORAL_ENDPOINT=127.0.0.1:7233 \
.venv/bin/python -m pytest multi-agent/tests -q
```

The Python test path includes this directory so process workers can resolve the
installed fixture functions under `support`. These fixtures are test support and
are not packaged as production application implementations.

For a fully independent service run, follow [the infrastructure guide](infra/README.md)
rather than assuming the default development ports. The repository skills
[`run-platform-tests`](../../.cursor/skills/run-platform-tests/SKILL.md) and
[`prepare-platform-infra`](../../.cursor/skills/prepare-platform-infra/SKILL.md)
capture the verified test and setup workflows. Report warnings and skipped cases
separately; existing pytest deprecation filters do not prove warning-free code.

The Codex subprocess contract tests in `integration/coding` use a real local
fixture executable without network calls. Application coding tests use the
application port. Paid workflow tests require `--live-coding` explicitly and the
independent OpenShell infrastructure; see [setup and command](infra/README.md#optional-live-codex-coding-workflow).

## Actual UI API clients

Install the UI's locked development dependencies with the declared pnpm 10.13.1
(`cd ui && pnpm install --frozen-lockfile`). Headless reinstallations can set
`CI=true` to avoid package-manager confirmation prompts.
With the independent Mongo and Redis test endpoints configured, run:

```sh
.venv/bin/python -m pytest multi-agent/tests/integration/ui/test_editor_client.py \
  --ui-clients -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

An explicit API-client selection fails if its Mongo endpoint, Node runtime or
installed UI dependencies are missing. Without `--ui-clients`, the optional UI
cases skip.
The `sessions` case additionally requires an isolated `UNIFAI_TEST_REDIS_URI`;
selecting all UI clients therefore needs both Mongo and Redis.
The fixture uses the production ASGI assembly and real HTTP/Mongo. The Node
runner compiles and calls the existing `catalog.ts`, `resources.ts`,
`blueprints.ts`, `sessions.ts` and `shares.ts` exports,
including schema loading, secret-safe create/list/read/update/delete and native
error presentation. It requires no additional JavaScript test framework. A
single owned Node process executes the test and removes its temporary bundle
under ignored `node_modules/.cache` on normal completion. It does not test a
logged-in browser session or replace the remaining browser end-to-end coverage.

The notification client case uses actual seeded invitations and checks sender
labels, list/detail shapes, pagination, decline persistence/idempotency, denied
access and request cancellation. Signed-cookie user/team authorization is covered
separately by `integration/redis/test_share_notifications.py`; development identity
in the TypeScript fixture is not proof of team membership integration. Native
creation/acceptance/team-copy flows remain outside that case.

The blueprint client scenario uses YAML source, saved node references and their
transitive model dependency. It exercises authoring, validation, metadata,
shortcuts, summaries, redacted display and stale-version conflicts. It then
imports/publishes that saved blueprint and executes a native session through
direct canonical API calls. This verifies the connection to native execution;
it does not verify the legacy session/chat client or its streaming protocol.
Application query tests use port doubles; Mongo editor tests verify user/team
ownership, missing references, safe parsing, unchanged stored data and stable
secret counts across display reads. Summary responses omit configuration; the
current query service still reads authoring documents from storage.

The session case uses a registered deterministic approval element, the actual
production API process and real Redis. It submits a pinned turn, disconnects its
reader without cancelling the run, approves it, replays the stream, then starts
and cancels a second turn. Its fetch shim only translates the browser-relative
base URL. It checks stale-subscription rejection and session deletion after the
terminal result. The Python fixture stops the API before removing only this
database's owned execution keys from Redis. This remains API-client evidence,
not a browser test of React state or workspace switching.

The shared agent scenario also runs through the existing UI session routes with
the same two agents, actual tools, transitive dependencies and two turns used by
native API tests. Memory and Mongo share query/deletion contract data, including
user/team separation, stable pagination, filters and stale-version deletion.

The same runner also checks saved-reference graph display and session-output
validation with plain data and an Axios transport double. These contracts run
without Mongo, an HTTP server or paid model calls:

```sh
cd ui
pnpm run test:contracts
pnpm run typecheck
pnpm run build
```

`typecheck` includes the TypeScript contract suites as well as application code.
It is separate from the production build. Both currently pass; the build retains
existing vendor chunk and size warnings. These checks do not establish complete
browser compatibility with the native API.
