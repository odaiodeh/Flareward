---
name: run-platform-tests
description: Run and diagnose Flareward platform architecture, application, adapter, and deployment tests, including actual Temporal, Kubernetes, and OpenShell execution.
---

# Test Flareward's program platform

Read [the test layout](../../../platform/tests/README.md) and the selected
suite's fixtures. Use the repository's Python 3.14 `.venv` and local Run Engine
checkout at the committed baseline in [integration status](../../../integrations/README.md).
Do not apply archived prototype patches. Tests from unrelated services remain outside
the replaced platform suite.

Start with the relevant application/adapter/architecture cases. For infrastructure
or deployment changes, use [Flareward's own infrastructure guide](../../../platform/tests/infra/README.md).
Inspect existing services and use explicit service URIs; do not rely on another
repository's infrastructure or silently reduce a requested backend matrix.

Follow the user's milestone cadence in
[the active plan](../../../docs/plan.md#verification-cadence). Start/resume with
[current status](../../../docs/status.md); use [selected evidence](../../../docs/evidence/README.md)
for source/image/proof questions. Write focused milestone records there; do not
load full archives or append running command logs to status/plan.
Expensive Docker builds, Kubernetes/OpenShell matrices, broad Temporal/recovery
and full E2E gates are milestone checks, not the default after each edit. Batch
related changes; use focused application/adapter/static/client checks meanwhile.
Run a heavy gate once for a coherent frozen snapshot and its acceptance criteria.
Do not repeat green gates without relevant changes, failures or unresolved concerns.
Use a targeted rerun to diagnose a specific failure. Defer unrelated policy/provider
suites to their appropriate milestone while preserving required final coverage.
The commands below are examples for those gates, not a per-edit checklist.

```sh
.venv/bin/python -m pytest platform/tests/application platform/tests/architecture -q
.venv/bin/python -m pytest platform/tests --ignore=platform/tests/integration/deployment/test_remote_programs.py --ignore=platform/tests/integration/deployment/test_openshell_policies.py --ignore=platform/tests/integration/deployment/test_codex_agents.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
.venv/bin/python -m pytest platform/tests/integration/deployment/test_remote_programs.py --platform-hosts=local,temporal --platform-backends=k8s,openshell -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

Host selection and invocation backend selection are independent. Remote cases
skip without `--platform-backends`; selected unavailable infrastructure fails.
For the production service image, use the package README's named Run Engine build
context and Dockerfile-specific allowlist. `verify_images.py --platform --image ...`
checks installed packages without requiring test fixtures. Stream
`tests/infra/smoke_platform.py` into the image's Python entrypoint for an isolated
CLI/API/core-Wait/shutdown check. Its default mode is Local; `FLAREWARD_SMOKE_HOST`
selects a matching separately started Temporal worker and requires actual pollers
plus Mongo (`FLAREWARD_SMOKE_MONGO_URI`, default `mongodb://mongo:27017`). Use only the
dedicated test network, unique queues and owned-container cleanup. No host ports,
credentials or socket mounts are needed. This does not certify remote execution.
A partial namespace dependency (for example `google` installed without
`google.genai`) can hide missing extras in a full dev venv: import the optional
SDK's fully qualified module so discovery distinguishes absence from a broken
installed SDK. Preserve failure for incompatible installed SDK imports.

At a remote milestone, rebuild and load receiver images whose installed runtime,
application code or fixtures changed since their last verification. Queue this work
between milestones instead of rebuilding after each small change. Check the tested
image identity and code against the frozen checkout; old image results remain
historical evidence for later edits.
The FastAPI and Temporal worker processes have separate lifetimes: HTTP health
does not establish worker readiness. The harness waits for task-queue pollers.

For native scheduling, use [the schedule diagnostics](../debug-program-schedules/SKILL.md).
Its deployment tests exercise actual calendar actions, native generation pins,
finite/manual budgets, and confirmed concurrent updates. A workflow ID alone
does not identify a rapid calendar tick, and a queued update is not applied-state
confirmation.

For `RUN_ALREADY_EXISTS` during an original start, uncertain submission, or early
cancellation, use [execution-admission diagnostics](../debug-execution-admission/SKILL.md).
Preserve active delivery claims, expired-owner fencing and first-collision refusal;
do not fix admission races by adopting arbitrary existing native runs.

For exact-candidate acceptance and evidence authorization, use
[verification diagnostics](../debug-verification-evidence/SKILL.md). Its native
restart test uses actual Mongo/Redis and an independent executable source-content
check. Graph/code verification and native timer/worker replay use the registered
wait program. The CI-specific suite exercises the production GitHub adapter and
native API restart against an explicit durable protocol peer, not live GitHub jobs
or remote placement. Uncertain dispatch is never permission to repeat its POST.

Cancellation scenarios need a live resource and a separate operation budget from
short timeout scenarios. A deadline can legally expire during process startup;
do not require a readiness marker in that case. Check every acquired subprocess
was reaped and staging was removed, rather than hiding early task failures while
waiting for a marker. Dedicated-service startup failures require a health check
and explicit failed/rerun evidence; do not count a partial gate as green.

For OpenShell policy configuration or allow/deny failures, use
[the execution-policy diagnostics](../debug-execution-policies/SKILL.md). Policy
files are operator inputs, and supplied policy replaces image policy. The separate
deployment module verifies actual host/port enforcement, not just acceptance.

For shared-agent extraction or hidden plugin-import failures, use
[the boundary-refactor workflow](../refactor-agent-boundaries/SKILL.md). The domain
and application packages have direct-import and cold-import guards; verify those
before rebuilding receiver images and running saved-session/remote regressions.

For saved MCP-tool construction, use [the MCP element diagnostics](../debug-mcp-elements/SKILL.md).
Native async preparation must complete before dependents bind the server's schema;
the real SDK fixtures and saved-session tests cover distinct layers.

For editor action discovery, credential operations and provider probes, use
[native action diagnostics](../debug-native-actions/SKILL.md). Those tests cover
the application registry, signed-cookie human/team scope, actual MCP/A2A HTTP,
private failures and provider client cleanup; no paid call is needed.

For invitation notification queries and decisions, use
[sharing diagnostics](../debug-sharing/SKILL.md). Its memory/Mongo contract handles
UTC dates, type-scoped owners and concurrent pending transitions.
Notification tests do not certify the still-unmigrated create/accept/copy flows.

For curated-library transactions, dependency publication and admin edit leases,
use [built-in administration diagnostics](../debug-builtin-administration/SKILL.md).
Its replica-set fixture uses `FLAREWARD_TEST_MONGO_TRANSACTION_URI`; the standalone
Mongo refusal check uses the ordinary Mongo URI. Do not silently replace atomic
publication with separate writes to make a standalone service pass.

Native reporting uses `application/test_reporting.py`, Mongo `test_reporting.py`
and HTTP `test_reporting.py --ui-clients`. The last gate runs the production
dashboard/analytics clients against real signed sessions, Mongo and Redis. Count
root records separately from nested children and conversation sessions; preserve
user/team identity, pinned revision names, null completion and bounded UTC history.
An empty persisted admin list revokes flareward.bootstrap authority; directory failure must
not restore it. Reports are stored projections, not live engine or acceptance proof.
The old statistics service/routes are removed; verify their absence on the next
coherent image rebuild, without rebuilding per reporting edit.

For tracing ownership and actual OTLP transport, use
[the native tracing diagnostics](../debug-native-tracing/SKILL.md). Its deployment
cases cover both hosts and thread/process receivers; a local protocol endpoint
does not establish Langfuse server-side persistence or cost aggregation.

For blueprint/plugin failures, check `flareward.programs.templates.schema.blueprint_schemas` and
the catalog supplied to library composition. Native authoring, inspection, and
import share registry-generated schemas; changing legacy global type unions is
not a plugin registration step. The resource's outer type key selects its schema,
including schemas without internal type fields. Use `test_blueprint_schema.py`
for parsing/type/reference contracts and `test_registered_blueprints.py` for real
HTTP/Mongo/thread/process and secret-hint behavior. A cold library-composition
test catches accidental imports of closed vendor configuration lists: resource
deletion needs only `BlueprintUsageReader`, not the whole legacy blueprint
repository. Generated authoring model classes do not belong in portable engine
payloads; published resources/bundles carry validated configuration data.

For actual agent-session behavior, use the shared `support/agent_session*` fixtures
and the Mongo/deployment `test_agent_sessions.py` cases. Fresh evidence comes from
real tool execution with transitive resources and execution identity; assertions
also require successful agent results, conversation/workspace continuity, and IEM
acknowledgments. `/events` carries engine lifecycle events; `/stream` carries node
tokens and tool events. The deployed case restarts the API between turns and
replays native history. These deterministic tests make no paid calls and do not
certify that legacy agent/tool internals have completed their async migration.
For core Map/Repeat/Choose/Wait, pinned child aliases and program-composer behavior,
use [composition diagnostics](../debug-program-composition/SKILL.md). Its policy,
Local/Temporal and native UI-client cases share application-only program data.
Bounded iteration completion is distinct from verified ADLC acceptance, and a
passing local map does not establish retained remote environment cleanup.
For business Human Review, use
[review diagnostics](../debug-human-reviews/SKILL.md). Its signed-session native
cases prove assigned-human authority, graph/code/thread/process composition,
expiry/cancellation/supersession, separate API/worker restart and native replay.
The actual App browser fixture and TypeScript clients are separate evidence.
Receiver-side tool approval tests do not certify this business review contract.
For automatic capability provisioning, use `support/managed_access.py` and
`integration/http/test_workflow_admission.py`; they start without pre-issued grants
or test-written token files. The `workflow_access` TypeScript-client cases exercise
manual and canonical Session admission. Existing purpose fixtures deliberately
pre-issue grants and cannot establish this automatic path. Keep scheduled/event
consent and isolated remote proof scoped to actual evidence. The focused
`deployment/test_scheduled_workflow_access.py` gate now exercises Human Review on
thread/process receivers, worker restart/replay and denied revoked native ticks;
it does not prove all purposes, API restart or remote delivery. Use schedule
diagnostics for private authority and deterministic coordinator resolution.
Multi-purpose partial/lost-acknowledgment recovery uses
`integration/mongo/test_workflow_admission.py` with actual stores and a narrow
issuer-port fault. `deployment/test_managed_workflow_recovery.py` adds concurrent
automatic roots, both purposes, API-only restart with the worker still running,
independent cancellation/approval cleanup and replay on thread/process receivers.
Keep these focused gates separate from broad remote/recovery acceptance.
Generic event starts use [event diagnostics](../debug-program-events/SKILL.md):
shared store contracts, actual template binding, native HTTP thread/process
review/verification and a focused Temporal source/occurrence restart/replay test.
Its TypeScript case uses the existing execution inspector. Provider-specific
ingress, event-to-wait routing, traffic limits and remote delivery are not certified.
For native agent/LLM execution and stream ownership, use
[the provider stream diagnostics](../debug-provider-streams/SKILL.md). Those tests
use installed SDKs with in-memory HTTP transports and make no paid model calls.
Construction omits dependency keywords for unset optional references: factories
should supply their optional defaults rather than requiring dummy resources.
Catalog composition may repeat an identical registered class; a different class
claiming the same category/type remains a conflict.

Keep scenario data and installed deterministic elements in application-only
support modules. Backend clients, process ownership, and history replay belong
in infrastructure support. Reuse production ports/factories/builders; do not
create a test scheduler or import other test cases. Preserve cold-import and
module-level-import guards. Use port doubles in application tests and actual
adapters for integration evidence.

For conditional rejoins, reuse `support/condition_scenarios.py` and installed
`support.conditions` specs. Local factory/backend contracts live in
`integration/flareward.executions.adapters.run_engine.shared/test_conditions.py`; `integration/temporal/test_conditions.py`
uses separate worker processes and replays completed exclusive/fan-out histories.
Its thread/process selection applies to condition invocation; work nodes use the
thread default. These tests do not prove restore while a join is deferred, old
history upgrades, or remote images. The committed SDK provides public ACTIVE joins. Consult `integrations/README.md`
for exact source identity, owner-reported SDK coverage and incompatible unreleased
prototype payloads. The fresh platform does not preserve earlier Flareward workers,
formats, or histories; test current-source execution and replay.
The strict-label SDK commit now rejects unknown selections atomically. Retain Flareward
normalization/label validation for product semantics; verify strict ERROR routing,
checkpoint consistency, and native replay. Diagnostics/events
must not echo invalid labels; ordinary invocation histories still carry return data.

Remote placement needs image/namespace/hostname/context evidence; container PID
inequality alone is insufficient. Verify actual construction, result bindings,
child ancestry, and physical cleanup. Replay native histories after coordination
changes with the original namespace and the worker's preloaded modules. Temporal's
default replay namespace changes environment-owner/grant identities and can produce
an artificial replay failure. Keep test services, unique databases/queues/workspaces/namespaces, and
owned process handles scoped; clean only resources created by this run. Do not
switch global Kubernetes context or enable paid model scenarios implicitly.

On a slow run poll the known process handle. A polling timeout is not a terminal
test outcome. On failure read the owned API/worker logs and concrete backend error
before retrying. Record the exact suite and matrix, passed/failed/skipped counts,
warnings and active filters, image identities, and unverified contracts. Passing
tests do not certify completion of the migration or absence of layer violations.

For Codex coding elements, use [coding diagnostics](../debug-coding-elements/SKILL.md).
Paid tests require explicit `--live-coding` and private credentials; the ordinary
subprocess contract tests make no model calls.

For UI transport migration, use `--ui-clients` on
`tests/integration/ui/test_editor_client.py` after installing the UI's locked
Node dependencies. This compiles actual production TypeScript client exports
with Vite and calls a real native API/Mongo fixture; no mock response can prove
compatibility. Preserve the existing camel-case request fields and pagination
shape in inbound HTTP adapters, and register static editor paths before
`resources/{rid}`. Owner-hidden reads return 404 while denied writes return 403.
Do not turn these API-client tests into claims about full browser flows. Check
build, static types, actual screen rendering and authenticated workflows as
separate evidence. Run `pnpm run typecheck`, `pnpm run test:contracts`, and
`pnpm run build` in `ui/`. The static audit includes the contract suites. The
plain-data graph and session-output contracts use an Axios transport double and
require no services; they are distinct from the real HTTP/Mongo API-client test.
Both suites share the temporary Vite runner and are selected by `--ui-clients`
in the Python harness. Require Mongo only for the API-client fixture, so selecting
pure contracts does not silently depend on external services.

The API runner also selects `blueprints`, exercising real `blueprints.ts` exports
and a saved-reference graph's transitive resources. Source parsing belongs in the
inbound adapter; reuse `parse_blueprint` off the event loop and preserve the
native authoring service's version/ownership checks. Register dotted editor paths
before `blueprints/{blueprint_id}`. Resolved display is a read snapshot: use
registered secret-field metadata to redact credentials, preserve missing-resource
reports and shortcuts, and assert that reads neither modify documents nor add
secret records. Keep editable protected drafts separate from display snapshots.
The native execution at the end of that client case uses canonical session APIs;
it is not evidence that the old session client or public sharing is migrated.
Keep selected team scope explicit in requests and acting-user identity derived
from authentication. Pin the loaded draft version when editing; a stale save
must surface a conflict instead of overwriting another edit.

For session/chat migration, use [session UI diagnostics](../debug-session-ui/SKILL.md).
The `sessions` TypeScript suite uses actual HTTP/Mongo/Redis and the existing
creation/submission/stream/approval clients. Selected missing prerequisites fail;
pure framing/data contracts stay independent of services. Shared memory/Mongo
query/deletion tests use the same application-owned persistence contract.
