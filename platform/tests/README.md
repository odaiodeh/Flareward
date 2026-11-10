# Platform tests

Tests follow the application's dependency direction and use small, explicit
compositions rather than a shared test superclass.

Use focused checks while implementing and reserve expensive Docker/Temporal/
Kubernetes/OpenShell/full E2E gates for planned milestones. Batch related changes
and do not repeat green heavy gates without a relevant reason. The user's
[verification cadence](../../docs/plan.md#verification-cadence)
governs selection; the suite examples below are not a per-edit checklist.

Generic element cold-import checks also initialize catalog/construction without
loading `lumora.programs.graph`. Graph channel declarations specialize `GraphElementSpec`;
`application/test_graph_element_contracts.py` checks separation, metadata validity
and dependency-versus-workflow semantics. Adapter payload tests distinguish an
operation key from graph context. The shared typed-operation fixture deliberately
has a coincidentally named `set_context` method which must never receive graph
injection. Actual graph/code thread/process cases exercise that boundary.

Program/domain boundary checks cold-import definitions and pure bindings without
loading application services, plugins or SDKs. Retired import paths must remain
unavailable. Program services/ports/registrations live under `lumora.programs`;
shared values come directly from domain owners. Image verification also checks
the installed canonical imports and absent old namespaces before remote execution.
Execution values cold-import from `lumora.executions.domain` without loading application
delivery models or mutable runtime holders. `domain/test_execution_context.py`
checks explicit identity, rejected unknown fields/live objects, and separation of
team ownership from the acting credential user. Submission/services/ports and
receiver-local holders live in `lumora.executions`.

Core composition shares installed pure child programs/definitions in
`support/composition.py`. `application/test_composition.py` controls child lifetimes
through owned ports to check bounds, ordering, failure/cancellation, strict loop
predicates, branch admission and deadlines. `integration/run_engine/test_composition.py`
executes pinned graph/code/operation children on actual Local thread/process
receivers. `integration/temporal/test_composition.py` replays descendant histories,
executes nested Map/Repeat and restarts a worker during Wait. The production
TypeScript program clients run through `integration/ui/test_editor_client.py
--ui-clients`; the actual App browser fixture is `support/program_browser.py`.
Shared signed-session server settings live in `support/native_settings.py`, separate
from business policy fixtures. These are initial composer/core-program cases, not
full visual-editor, Map worker-loss or remote environment evidence.

The draft/publication boundary uses `domain/test_program_publication.py` and
`application/test_draft_validation.py`: incomplete topology can persist, executable
revisions remain complete, typed configuration/secrets stay protected and readiness
is fenced by observed version. `support/program_store_contracts.py` checks both
memory and Mongo. `support/program_authoring.py` shares public HTTP assertions
between ASGI-memory and actual TCP/Mongo/thread/process cases, including execution
of a pinned older revision after later incomplete edits. The TypeScript program
suite checks the production validation client. Readiness is not placement admission
or native engine-plan validation; broader execution tests remain necessary.

Saved-resource capture shares `support/resource_snapshots.py` for application-owned
source doubles and `support/library_resources.py` for native resource creation.
Application tests cover authorized closure, source races, explicit shared adoption
and protected-reference reuse. Native Mongo/HTTP cases execute frozen operation
and agent snapshots on thread/process receivers, including caller-only built-in
overlays. `support/construction_values.py` supplies deep-chain data for iterative
bundle integrity/resolution and depth admission, including the all-selected-roots
bypass regression. These bounds do not establish execution-tree budgets.

Human Review scenarios share `support/reviews.py` for application-port doubles,
`support/review_programs.py` for ordinary bundles/program calls and
`support/review_api.py` for real signed-cookie users and private workflow access.
`application/test_reviews.py` and `test_review_program.py` cover immutable decisions,
schema admission, lifecycle, lost acknowledgements, untrusted wakeups and bounded
waiting. `integration/reviews/test_workflow.py` exercises graph/code callers on
thread/process receivers plus native expiry/cancellation/supersession and scope
denial. `integration/temporal/test_reviews.py` stops the worker during an observed
native timer, accepts a human decision while it is stopped, restarts both API and
worker, and replays root/child histories. Its finalizer cleans only accepted native
identities from that test's unique Mongo database after worker contexts exit.
`integration/ui/test_editor_client.py --ui-clients` executes production reviewer
TypeScript exports. `support/review_browser.py` renders the actual App and executes
a real workflow with an assigned reviewer; see the Human Review diagnostic skill.
These cases do not prove retained remote environment behavior or a complete visual
program editor.

Automatic manual/canonical Session admission shares `support/managed_access.py`,
which starts the actual API without pre-issued grants or test-written token files.
`integration/http/test_workflow_admission.py` exercises both purposes on thread/
process receivers, frozen human approval, invalid scopes and terminal collection.
The production TypeScript manual/Session clients run through the `workflow_access`
cases in `integration/ui/test_editor_client.py --ui-clients`. The older review/
verification API fixtures deliberately pre-issue access for purpose-specific
scenarios; they do not prove automatic admission. Recurring consent shares
`support/workflow_consents.py` for memory/Mongo contracts; application cases check
expiry, revocation, superseded definitions, lost acknowledgement and original actor
binding. `deployment/test_scheduled_workflow_access.py` uses actual Temporal
thread/process receivers, worker restart during review, replay, managed cleanup
and a denied direct native tick after revocation. Production schedule clients use
the `schedule_consent` case in the UI client suite. Multi-purpose partial admission
uses actual stores in `integration/mongo/test_workflow_admission.py`; the fault is
at the issuer port, not a substitute persistence/execution implementation.
`deployment/test_managed_workflow_recovery.py` runs two roots with both purposes,
duplicate concurrent requests and an API restart while the worker remains live.
Its shared application-only graph/scopes live in `support/managed_workflow.py`.
The borrowed listening socket belongs to the test and outlives both API processes;
normal `api_process` calls continue owning their own sockets. Independent root
cleanup and thread/process replay are checked. Remaining recovery combinations,
provider-specific ingress and isolated remote acceptance remain open.

Generic event starts use the shared Memory/Mongo source contract in
`support/event_sources.py`. `application/test_program_events.py` exercises source
authority and canonical deduplication. `run_engine/test_execution_templates.py`
proves actual frozen graph binding, pinned revision and private policy/parser refusal.
`http/test_program_events.py` covers typed operations plus nested Human Review with
both automatically provisioned purposes on thread/process receivers.
`deployment/test_program_events.py` adds source/occurrence recovery after API and
worker replacement, native history privacy/replay and cleanup. The production
TypeScript clients use the `program_event` UI-client case. These tests do not prove
live Jira signatures, event-to-wait routing, source-key rotation or traffic limits.

Root admission recovery uses `support/execution_claims.py` for the same ownership/
expiry/stale-token/cancellation-intent assertions against Memory and Mongo storage.
`integration/run_engine/test_recovery.py` holds original submission before native
acceptance, observes it from another service, forces lease takeover and a late old
reply, and covers bounded I/O plus cancellation before acceptance. The existing
foreign-collision test must continue to refuse ownership. Deployed agent-session
tests exercise real Temporal, API restart and native replay. See the execution-
admission diagnostic skill for the boundary between delivery claims and engine
worker/environment lifetimes.

Typed-operation scenarios live in `support/operations.py`: the registered
specification/factory and transitive dependencies run through production builders.
`application/test_operations.py` checks typed contracts, safe errors, ownership,
and cancellation. `integration/run_engine/test_operations.py` exercises graph and
custom-program calls on real thread/process receivers; `integration/http` checks
catalog-to-publication-to-execution, and `integration/temporal/test_operations.py`
uses a separate worker and native replay. The fresh platform does not preserve
older serialized revisions. Test current contracts and remove legacy-only cases
when their corresponding implementation is replaced.
Production coding scenarios in `integration/coding` use the installed
`plugins.codex` factory/adapter through graph and code programs. The
shared protocol executable in `support/coding_cli.py` makes real subprocesses
without model calls; cases prove overlapping isolated calls, private-home cleanup,
workspace containment, failures, timeout and cancellation. Application coding
policy has separate port-double tests. The removed Codex node is not retained as
an alias.

`adapters/run_engine/test_program_placement.py` checks approved selections and
bundle-specific specification dispatch. `integration/deployment/test_remote_programs.py`
adds real custom-program operation placement and parent/child environment borrowing
across both hosts/backends. Its receiver proofs and cleanup checks do not certify
paid Codex behavior. The opt-in paid scenario is converted to saved operation
resources and explicit shared workspaces. Use [current status](../../docs/status.md)
and selected [evidence](../../docs/evidence/README.md) for current-image acceptance;
no suite here establishes a complete visual typed editor.

Optional Git capability scenarios share `support/repositories.py` and real local
repositories. `application/test_repository_operations.py` checks typed contracts
and workspace policy through an application port; `integration/repositories/`
checks full commit resolution, branch movement, annotated tags, SHA-256 checkouts,
owner/namespace/path denial, existing-work protection, inherited Git configuration,
private failures, bounded output, timeout and cancellation. The program scenario
executes graph -> code child -> operation on thread/process receivers using the
existing dependency builder. `integration/catalog/test_git_plugin.py` installs the
optional module through production discovery and exposes its schemas without
constructing a repository. These tests do not certify private HTTPS authentication,
remote images, source retention or trusted verification/acceptance. Git remains
optional; other operation results do not adopt its source-reference model.

Verification scenarios share `support/verification.py` (application-owned port
double, controlled clock and policy data). `application/test_verification.py` and
`domain/test_verification.py` check exact JSON identity, immutable checks/receipts,
idempotency, owner/issuer boundaries, expiry, cancellation and concurrent updates.
`integration/mongo/test_verifications.py` exercises the actual async Mongo adapter.
`integration/http/test_verifications.py` checks separate HTTP roles and reconstruction.
`integration/redis/test_verifications.py` uses signed sessions, a separately started
native API, actual Mongo/Redis, exact Git materialization and an independently
executed content check; accepted/rejected receipts survive API restart and retries.
The executable check is a deterministic CI fixture, not a production CI runner.
`application/test_verification_access.py` and `test_verification_program.py` cover
bounded workflow authority, native-runtime timer use and borrower cancellation.
Shared definitions in `support/verification_programs.py` and owned native transport
in `support/verification_api.py` support both local and durable scenarios.
`integration/verification/test_workflow.py` executes request/inspect/cancel with
graph -> reusable code waiting on thread/process runners, including failed-service
classification. `integration/temporal/test_verification.py` stops/restarts a real
worker during an observed timer and replays both root/child histories. Explicit
operator-only worker environment bindings supply endpoint/private directory paths,
not raw capabilities. `integration/http/test_verification_access.py` verifies
independent root/policy/action authority. Push updates, report provenance,
automatic credential lifecycle and UI acceptance/review remain open.
No paid model calls are required for these cases.

Trusted CI checks share `support/check_runs.py` application-port doubles and
`support/github_checks.py`'s explicit GitHub wire fixture. Application tests cover
concurrent dispatch, lost acknowledgements, immutable evidence, authority, deadlines
and cancellation without retrying an uncertain effect. `integration/verification/`
checks the production GitHub adapter, actual Mongo/native API reconstruction,
wrong provenance and bounded ambiguous searches. `test_check_workflow.py` executes
graph -> registered request/submit -> reusable waiting code child through real
thread/process receivers and a separate signed-cookie native API. `test_check_restart.py`
stops/restarts the API between dispatch and reconciliation, using a durable protocol
peer owned by `support/check_api.py`. That peer is not a live GitHub runner. These
tests do not prove external GitHub execution, CI-specific Temporal
recovery, remote images or the complete software delivery/review workflow. Never
turn missing provider matches into permission for another dispatch POST.

`application/test_verification_reports.py` checks required-report policy, reference
ownership, immutable provenance and deadline admission through application ports.
`integration/verification/test_check_reports.py` combines the real GitHub adapter
and filesystem artifact store to verify streamed bytes, deny wrong/expired/ambiguous
manifests, close sources on failure, prevent redirect credential leakage and recover
committed reports after acknowledgement loss/provider expiry. Report-enabled native
restart cases retain downloadable bytes after provider deletion; graph/code cases
use the same published workflow on thread/process receivers with and without
required reports. Human run-attachment intervention has stale/idempotency/authority
tests and is distinct from the still-pending Human Review business program.

Artifact foundation scenarios reuse `support/artifacts.py`. Application tests
use the artifact storage port; `adapters/test_artifact_filesystem.py` uses real
private files, atomic concurrent publication, cancellation and corruption.
`integration/http/test_artifacts.py` restarts an actual native API against the
same durable directory, checks owner denial, admission, conflict handling and
stream cleanup for ASGI 2.3/2.4. These cases prove the initial API/storage component;
worker-scoped transfer now has explicit capabilities and registered operations.
`integration/coding/test_artifact_handoff.py` uses actual graph/code programs,
thread/process receivers, workspace deletion and API restart; it makes no model
calls. `application/test_artifact_access.py` checks expiry and bounded grants,
`integration/http/test_artifact_access.py` checks roles/scopes/revocation, and
`integration/redis/test_artifact_access.py` uses actual signed cookies and the
native API. `integration/coding/test_workspace_files.py` checks pinned-path access,
atomic/idempotent writes, special-file denial, cancellation and error ownership.
Remote destroyed-environment handoff and workflow-integrated trusted checks remain
separate acceptance work. Keep this focused gate at feature milestones;
repeat broad regression/remote matrices when the affected execution boundaries
change or at completion, rather than after each edit.

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
  MCP/A2A HTTP plus success/failure/cancellation and scoped identity headers
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
  closes each Local host. Mongo tests require `LUMORA_TEST_MONGO_URI` and create
  uniquely named databases that the fixture removes afterward. Redis tests require
  `LUMORA_TEST_REDIS_URI` and remove only their unique execution keys. Both exercise
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
- `integration/temporal/` uses `LUMORA_TEST_TEMPORAL_ENDPOINT` with unique queues.
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
  The [independent infrastructure guide](infra/README.md) provides Lumora-owned
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
.venv/bin/python -m pytest platform/tests/application platform/tests/architecture -q
.venv/bin/python -m pytest platform/tests -q
.venv/bin/python -m pytest platform/tests/integration/providers -q -W default
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27017 .venv/bin/python -m pytest platform/tests -q
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27017 \
LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6379/0 \
LUMORA_TEST_TEMPORAL_ENDPOINT=127.0.0.1:7233 \
.venv/bin/python -m pytest platform/tests -q
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
.venv/bin/python -m pytest platform/tests/integration/ui/test_editor_client.py \
  --ui-clients -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

An explicit API-client selection fails if its Mongo endpoint, Node runtime or
installed UI dependencies are missing. Without `--ui-clients`, the optional UI
cases skip.
The `sessions` case additionally requires an isolated `LUMORA_TEST_REDIS_URI`;
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
