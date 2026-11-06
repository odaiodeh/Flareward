# Historical execution-platform record (frozen 2026-11-04)

This is an archived snapshot, not the working plan. Statements such as "current",
"active", "next" and old compatibility requirements describe their recording
context. The current goal and [target architecture](../../architecture/README.md)
govern. Start with [current status](../../status.md) and [the active plan](../../plan.md).

Do not read this entire file during routine work. Use the
[evidence index](../README.md), search for the relevant heading, and retrieve only
that section. Do not append new work here; write a focused evidence record instead.
Historical passing gates prove only their recorded source/image and test scope.

Original record follows, with relative Markdown links rebased to this location
and one unavailable historical handoff link annotated as removed.

---

# Execution platform migration

Implementation follows the program-platform objective supplied in this chat.
Completion requires the full migration, not only the first passing vertical slice.

The [target architecture](../../architecture/README.md) records the agreed platform
direction and architectural acceptance criteria. This ledger tracks implementation
and evidence; the target does not mark proposed capabilities or migration work done.

Fresh-platform decision (2026-11-01): old code, stored formats, workers, import
aliases, and dual APIs are not compatibility requirements. Convert useful behavior
to the target and remove superseded implementations, tests, dependencies, and
misleading guidance. Earlier old-worker retention and migration/drain requirements
are superseded. Safe cancellation and cleanup of current owned work still apply.

## Verification cadence (2026-11-01)

**User clarification, 2026-11-03:** prioritize implementation progress. Expensive
Docker builds, Kubernetes/OpenShell matrices, broad Temporal/recovery suites and
full E2E gates belong at planned, meaningful milestones, not after every edit or
small refactor. Batch related backend changes and use focused domain/application,
adapter, typing/lint and small client checks between milestones. Do not repeat a
green heavy gate without new relevant changes, a specific failure or an unresolved
concern. A targeted failing scenario may be rerun when needed to diagnose a fix;
that is not a reason to restart the entire matrix. Defer unrelated heavy suites
(for example unchanged egress policy) to their own milestone. Keep their evidence
honest and retain all required backend/security/recovery/cleanup coverage at the
appropriate milestones and final acceptance audit.

Use focused checks while implementing behavior, integration checks when a coherent
vertical slice works, and broad regression/remote gates at major architecture
milestones and completion. Do not rerun the whole platform after each small edit.
Remote matrices are required for changes to dispatch, placement, environment
ownership, recovery or cleanup; unrelated application work uses targeted evidence
until the next milestone. Keep paid tests opt-in. A running gate validates its
recorded source snapshot: do not change the modules it exercises mid-run or treat
that run as evidence for later edits. Progress on independent design/components
while long gates run, and record affected checks for subsequent changes explicitly.

## Active target implementation queue (2026-11-01)

Priority updated 2026-11-03 by the replacement goal: backend-led milestones govern
the remaining work. Finish canonical domain/application contracts, composition,
reliability/security/control and observability, then prove reusable Engineering
before substantial UI convergence/polish. Use small production-client/browser
checks during backend milestones to validate the intended user journeys. The
standalone Programs screen remains interim. The detailed capability rows below
retain their obligations; they are not permission to prioritize UI expansion over
unfinished backend foundations.

The active goal now implements the target README, including typed operations,
composition, UI integration, durable reviews/artifacts, and controlled dynamic
work. Earlier sections that called these post-migration proposals describe the
previous scope. The queue below governs the expanded target; the dated legacy
migration queue supplies historical evidence and product requirements, not a
requirement to preserve its old execution architecture.

| Order | Slice | Required evidence and current status |
| --- | --- | --- |
| 1 | Typed operation invocation through the existing construction/execution path | In progress: operation category/reference, input/result schemas, BaseOperation/OperationInvoker, operation graph calls with explicit projections, catalog schemas, and custom-program invocation are implemented. RootModel array/scalar contracts now run through the same path. Historical baseline: 660 platform cases and 40 remote cases; these do not validate subsequent installed-source changes. Current focused evidence is recorded below; matched-image remote/recovery acceptance remains pending. Input/result/internal model-contract errors have safe diagnostics. Visual typed ports, execution-requirement admission and the wider composition model remain open. |
| 2 | Production coding capability and explicit operation placement | Implemented backend slice: `operations/codex_coding` outer plugin, application-owned typed coding operation, deleted former Codex node, graph/code invocation, default workspace isolation and explicit sharing. Custom programs select profiles/environments and publish fixed child imports. Dependency-specific dispatch fixes unrelated optional SDK imports on minimal receivers. Execution-milestone baseline: 660 passed, including UI API clients and real data/Temporal services; strict typing passes. Complete remote matrix passed 40 cases after service recovery; visual workflow composition and real-model verification remain open. Resource form supports operation placement; visual typed-port/nested-program editing remains row 5. Paid CLI scenarios were converted and collected, not rerun. |
| 3 | Durable artifacts, change sets, and executable verification | In progress: managed blob transfer, optional Git source operations and verification plans/evidence admission are implemented. Root/policy/action-scoped workflow credentials and reusable waits compose through graph/code. Trusted CI dispatch now includes frozen report manifests, verified durable report bytes, immutable evidence provenance and audited attachment of provider-confirmed runs to uncertain intents. Native API restart and thread/process composition use an explicit GitHub protocol fixture; live GitHub execution is not established. Full milestone status and limits are below. External cancellation/permanent-absence handling, automatic credential lifecycle/admission, change sets, retained commit publication and remote destroyed-environment handoff remain open. No agent self-report substitutes for trusted checks. |
| 4 | Durable Human Review program and interaction UI | Implemented native slice: registered `human_review@1`, ordinary review operations, Mongo CAS decisions/outbox, assigned-human sessions, scoped workflow capabilities and actual App inbox. Focused graph/code/thread/process, lifecycle, API/worker restart and native replay evidence is below. Visual palette/nested authoring, parallel/repeated occurrence coverage and retained remote environments remain open. Operational interrupts remain distinct. |
| 5 | Unified composition and UI/runtime mapping | In progress: registered controls, declared-child admission, whole-value projections, scoped input/results interfaces, bounded acyclic activation/order/type checks, canonical routing modes, explicit join preferences, schema catalog, versioned program library, program-call canvas and server-resolved saved-resource blocks are implemented. Indexed results are current data, not occurrence history. Evidence is below. Follow the 2026-11-03 integrated UI direction: evolve the existing builder/resource/session journeys into one authoring workspace and shared execution workbench. Cyclic/complex-flow guarantees, richer writable-state/merge contracts, structured invocation UI, authoritative live nested execution, inline controls, typed ports, definition/occurrence expansion and the reusable ADLC workflow remain open. |
| 6 | Controlled dynamic work and production policy | Recorded/admitted plan changes, compatible program selection, fenced stale attempts, root budgets, tenant profile/credential policy, and external-effect reconciliation. Preserve all explicitly deferred mechanisms. |
| 7 | Product parity, deployment validation, and retirement | Complete outstanding existing API/UI obligations below. Rebuild matched receiver images; verify required remote/recovery/isolation/load/upgrade behavior. Remove replaced entrypoints, modules, tests, dependencies, and misleading skills; old formats/executions do not delay removal. |
| 8 | Requirement-by-requirement completion audit | Map all eight replacement-goal milestones, their carried-forward requirements and the target checklist to current-source implementation and actual verification evidence. Documentation, skills, startup paths, packaging, typing, lint, and boundary checks agree. No goal completion claim before this audit passes. |

### Backend-led implementation order (2026-11-03)

The goal resumed with a replacement objective emphasizing these dependencies:

1. Finish canonical draft/publication, resource/Program and application-port
   boundaries. Keep unfinished authoring safe and executable revisions complete.
2. Consolidate domain/application/adapters/plugins and preserve one construction,
   invocation and engine integration. Complete inline composition and validation.
3. Complete ownership/recovery, placement, durable human interaction, credential
   lifecycle, tree-wide budgets, dynamic admission and tenant controls.
4. Provide authoritative revision/occurrence-aware execution views and resumable
   observation contracts before substantial execution presentation work.
5. Prove reusable Engineering independently and unchanged inside Jira-to-CI/CD
   delivery, with trusted exact-candidate checks, review and bounded repair.
6. Deliver unified library/builder/workbench UI, reusing useful existing behavior
   and allowing major visual improvements. Retire competing experiences.
7. Complete required current-image matrices, product/API obligations, cleanup,
   documentation/skills and the full requirement-by-requirement audit.

Application/adapter and small production-client checks accompany backend slices;
full visual UI work follows the foundations and proving workflow. The UI order
below records the product direction and is subordinate to this backend-led order.

### Integrated UI direction and next implementation order (2026-11-03)

This direction was recorded during the pause; the goal has since resumed with
the backend-led order above. Read [the unified UI target](../../architecture/README.md#unified-ui-and-live-execution-experience)
before changing presentation. Preserve useful existing behavior and permit substantial layout,
navigation and interaction improvements. Live execution visualization is an
explicit acceptance requirement, including nested/repeated occurrences and safe
placement. The separate Programs editor/runner is an interim surface to converge,
not a second permanent authoring/execution product. Conversation is optional;
structured manual, Session and trigger-based invocations share one workbench.

When backend foundations and Engineering are established, use this order within
the UI slice:

1. Integrate the established canonical draft/published-revision contracts and
   unfinished authoring, preserving secret protection and strict publication.
2. Converge the existing builder and library with canonical Program authoring;
   reuse resource forms, dependency selectors, validation and placement behavior.
   Keep resources distinct from Programs and allow multiple calls per resource.
3. Reuse/evolve the existing session execution layout into one workbench, with
   schema-driven inputs, optional conversation and durable execution navigation.
4. Complete inline controls, typed bindings, explicit child environment imports,
   placement preview and pinned-definition expansion within that workspace.
5. Provide revision-aware, occurrence-aware snapshots and resumable live views;
   integrate reviews, artifacts and operational controls through authorized APIs.
6. Prove standalone/composed Engineering and the required execution/recovery
   matrix, then retire superseded UI/API paths and complete the full goal audit.

Check actual browser journeys and accessibility/responsive behavior alongside
application/adapter/client contracts. Visual status must reflect observed work;
disconnected observation is not completion, and execution success is distinct
from verified acceptance. The findings came from source inspection and the actual
inventory, builder, session selector and Programs screens in an isolated fixture;
this investigation did not establish new execution/backend acceptance evidence.

Historical paused source checkpoint: `application/test_draft_validation.py` was added before
the pause to describe unfinished drafts. Its initial focused run failed at the
existing GraphDefinition entry/exit validation, before implementation. That work
was unfinished at that checkpoint; resumed backend work is recorded below. Earlier
passing gates do not include that new test.

Operation call data is independent of GraphState. The graph adapter projects
inputs/results. A distinct `operation` discriminator describes the typed call
contract; remaining node-state paths are conversion/removal targets. This is one
registry, factory/bundle builder, receiver ownership scope, and engine integration,
not another runner. The current UI has not yet gained typed operation blocks or
input/output port editing; catalog/API tests are not full browser evidence.

Evidence so far:

- Local/API gate: `/tmp/unifai-typed-operations-local-20261101.xml`, 289 passed in
  12.22 seconds, zero failures/errors/skips.
- Separate worker/native replay: `/tmp/unifai-typed-operations-temporal-20261101.xml`,
  4 passed in 5.34 seconds, zero failures/errors/skips, actual Temporal at 7234.
- Fresh-platform local/API gate after removal of compatibility scaffolding:
  `/tmp/unifai-typed-operations-fresh-local-20261101.xml`, 288 passed in 11.60
  seconds, zero failures/errors/skips. Blueprint execution tests now use the
  catalog-generated schema; no old closed-schema fallback was added.
- Strict mypy passes for the two new application operation source modules.
  Focused lint/format passes; full-platform and deployment checks remain open.
- Full nonremote gate before fresh-platform cleanup:
  `/tmp/unifai-typed-operations-platform-20261101.xml`, 649 passed in 262.81 seconds,
  using dedicated Mongo/Redis/Temporal and production TypeScript API clients. The
  subsequently removed old-revision test was included; rerun affected contracts.
- Removed 11 obsolete MAS reference/recipe files and the old Temporal-worker skill.
  Replaced the MAS skill with current platform guidance and corrected refactor,
  test, schedule, pipeline, and codebase guidance. Removed the new compatibility-only
  frozen-revision fixture/test. Skills must not reintroduce old-worker retention.
  Corrected engineering standards that treated all `lib/mas` as domain, required
  an ABC per adapter and enums for extensible identities, or retained unnecessary
  compatibility facades. The guide now follows the target's actual boundaries.

### Coding operations and placement slice (2026-11-01)

The production provider integration is now at
`multi-agent/plugins/mas_plugins/coding/codex`; shared application coding behavior
is in `mas.application.coding.operation`. The former Codex node package and
application node wrapper are deleted. `CodingInput`/`CodingOutcome` are independent
of graph state. Existing registry, specifications, factories, resource-secret
handling, dependency bundles, builders, and receiver ownership remain authoritative.

`WorkspaceMode.ISOLATED` distinguishes stable call keys and child execution IDs
inside a root namespace. Retries keep the same logical workspace. Explicit
`SHARED` mode permits sequential handoff in the same retained/imported environment;
it does not provide concurrent repository editing or durable artifact storage.
A deterministic CLI protocol fixture proves real overlapping subprocesses, separate
workspaces/private homes, file writes, and credential-home cleanup without model calls.

Custom program definitions now declare named environments and fixed child imports.
The runtime accepts the application-owned `ExecutionSelection`; adapter payloads
freeze approved concrete choices and dispatch only the invoked bundle's transitive
specification closure. The initial remote gate exposed whole-catalog imports of
unrelated optional SDKs; that defect is fixed by keyed specification selection,
not by adding unrelated providers to every image. Runtime tests include an
uninstalled unrelated provider identity and verify it never reaches dispatch.

Current evidence:

- Before the dependency-selection fix: 76 focused coding/placement/architecture
  cases passed in 14.85 seconds. After that fix: 70 affected adapter/coding/graph/
  architecture cases passed in 13.99 seconds; the six application coding cases
  are also included in the full gate.
- Current-source local gate: 332 passed in 24.74 seconds, zero failures,
  errors or skips; domain/application/architecture, engine adapters, graph/code,
  native HTTP and deterministic coding cases.
  `/tmp/unifai-coding-operations-local-20261101.xml`.
- Strict mypy passes for ten new/affected operation, coding, plugin, and adapter
  payload source modules. Focused lint/format and diff whitespace checks pass.
- UI TypeScript checking and the production Vite build pass using installed
  dependencies. The build retains its large-chunk warning. The editor API-client
  scenario now authors the coding operation; the resource form offers operation
  profile placement. This is not full browser evidence for a typed graph editor.
- Both rebuilt dedicated receiver images match 1,189 local Python files each,
  including installed `mas_plugins` source. Receiver identity:
  `sha256:4ac3fcb317cd9e5ebe7bc8a6d4f153f65aa80fd40f46218c14b876cba6b349c0`;
  OpenShell receiver:
  `sha256:83b14f6cb98cb28ebee38a91eddc11dc94e002ce7c387fd37c8ebb876fbf2e7a`.
- The first post-fix remote run passed all 12 new profile/environment/borrowed-child
  cases across Local/Temporal and Kubernetes/OpenShell, plus four existing
  Kubernetes lifetime cases. It then failed in an existing OpenShell lifetime
  case when both dedicated Mongo and Redis stopped responding. Final report:
  16 passed, 1 failed, 1 teardown error in 320.05 seconds;
  `/tmp/unifai-coding-placement-remote-fixed-20261101.xml`. That interrupted run did not pass the full 40-case
  matrix; the successful recovered run is recorded below. Mongo's own health checks timed out and a direct client
  ping also failed; container state reported no OOM kill.
- Recovered stable-source full nonremote gate: **660 passed in 250.06 seconds**,
  zero failures/errors/skips; dedicated Mongo/Redis/Temporal, separate API/worker
  processes, native replay and production TypeScript API clients.
  `/tmp/unifai-coding-operations-platform-recovered-20261101.xml`. Paid coding,
  remote programs and OpenShell policy modules are separate gates.
- The earlier stable-source nonremote gate was stopped after the same service outage;
  it is not acceptance evidence and has no finalized JUnit result. SIGINT did not
  stop repeated fixture timeouts, so the owned pytest process was terminated after
  confirming it had no active API/worker children. Fixture database cleanup needs
  reconciliation after service recovery. An earlier full run overlapped a payload change
  and exposed one stale UI test; that run is also not current-source acceptance.
  Dedicated Mongo/Redis restart restored direct health checks in about 11 ms.
  The sequential full-gate rerun passed; the complete remote rerun is underway. Finish cleanup and remote verification before
  accepting the slice. Do not mask the outage by weakening assertions or raising
  timeouts. Infra commands/default tags now select the current receiver generation;
  the optional Codex derivative must be rebuilt against it before paid testing.
- Four optional real-model deployment cases collect after conversion, but no paid
  calls were made in this slice. New-image deterministic placement proof is
  separate from actual paid Codex behavior and workspace artifact durability.

The recovered remote gate passed **40 cases in 432.26 seconds**, zero failures,
errors or skips: `/tmp/unifai-coding-placement-remote-recovered-20261101.xml`.
It covers both coordination hosts and invocation backends, custom-program typed
operations, parent/child borrowing, child-owned scopes, failure cleanup and replay.
The exact database of failed execution `703779f3bef4474b84c32ae7ece38fb5` was
identified by its execution record and removed after recovery. No prefix-wide
resource deletion was used.

Subsequent privacy correction: model-validation failures inside operation work
now become safe `OperationContractError` diagnostics. Focused application and
real thread/process coding cases passed 17 tests in 3.01 seconds, including a
composed coding prompt exceeding its request bound before CLI start.
`/tmp/unifai-operation-execution-privacy-20261101.xml`.
The 660/40 gates above precede this small correction and the artifact work below;
they do not certify later code or current image parity. Rebuild receivers at the
next remote handoff milestone rather than rerunning every broad gate after edits.

### Durable artifact foundation (2026-11-01)

Implemented an initial usable API/storage component:

- Domain `BlobArtifactRef` identifies immutable bytes by artifact ID, SHA-256 and size.
  `ArtifactRecord` carries owner, display metadata, authorized input references and
  creation time. The old workload-local path value is renamed `WorkspaceArtifact`;
  no compatibility alias conflates it with durable storage.
- `ArtifactService` owns publication identity, per-object admission and owner/lineage
  access. Stable owner/type/key identities retain identical prior commits and
  reject conflicting content/metadata. It depends on `ArtifactRepository` only.
- `FileArtifactRepository` streams through private staging, checks actual size/hash,
  syncs content/metadata, and atomically publishes one directory. Concurrent retries
  cannot replace committed bytes. Failed/cancelled uploads close files and remove
  their staging. Reads verify the recorded content identity.
- Native authenticated `POST /api/artifacts`, metadata GET and streaming content GET
  use the same service. Enable an absolute `UNIFAI_ARTIFACT_DIRECTORY`; set
  `UNIFAI_ARTIFACT_MAX_BYTES` for per-object admission. The filesystem backend is
  intended for durable POSIX server storage, separate from execution environments.
- The HTTP response owns and closes its body stream on disconnect. Content headers
  carry the expected digest and private/no-store caching. A consumer must finish
  integrity verification before accepting downloaded work; stream failure after
  headers cannot retroactively turn the response into a JSON validation error.
- First focused gate: 28 passed in 11.37 seconds, including a separately running
  API restarted against the same directory, foreign-owner denial, actual concurrent
  storage, conflicts, corruption, cancellation and disconnect release. Strict mypy
  passes eight operation/domain/application/storage/HTTP modules. Expanded affected
  HTTP/privacy/boundary gate: 57 passed in 16.14 seconds,
  `/tmp/unifai-artifact-api-milestone-20261101.xml`. The subsequent disconnect
  check passed both ASGI 2.3 and 2.4 variants (2 selected tests). No full platform rerun is required here.

This does not complete slice 3. Scoped transfer and registered operations are now
implemented as described below. Remote handoff after engine-owned compute
destruction, exact repository/change-set identities, trusted executable verification
and acceptance outcomes remain unfinished. Artifact metadata proves
byte identity and access, not that an agent's claim or submitted lineage is a
trusted verification result. Global retention/quota policy and recovery of staging
left by hard process death remain open; graceful cancellation is covered.

### Scoped workflow artifact transfer (2026-11-01)

The optional managed-file value is explicitly named `BlobArtifactRef`. The core
operation contract still permits any validated result: ordinary data, a Git commit
reference, an image digest or other integration-specific values. Committed source
should use repository + immutable commit identity directly when appropriate; it
need not be uploaded as another snapshot. Git checkout and candidate integration
remain part of slice 3, not implemented functionality.

Implemented:

- `ArtifactAccessService` issues owner-bound, expiring, revocable capabilities with
  explicit read/publication actions, namespaces/blob IDs and byte limits. SQLite
  stores only credential hashes and metadata in the server's private `.access`
  directory; revocation survives restart. Namespace now participates in stable
  publication identity. Human sessions manage grants; artifact bearer credentials
  cannot authenticate unrelated routes or issue/revoke credentials.
- The API checks scoped read admission before sending content headers. Managed bytes
  use attachment/nosniff/restrictive CSP responses, so untrusted HTML is not served
  as ordinary active application content. MIME values are bounded concrete ASCII.
- Three normal specs use the existing catalog, factory, dependency resolver,
  preparation and receiver lifetime: `providers/artifact_store`,
  `operations/publish_artifact`, `operations/materialize_artifact`. No runner,
  compiler branch, parallel registry or new scheduling framework was added.
- The HTTP provider checks its credential owner, uses private receiver binding or
  existing protected resource secrets, requires HTTPS unless an operator enables
  local testing, refuses redirects and bounds whole transfers. Returned execution
  data contains blob references, not credentials or byte payloads.
- Shared domain `WorkspaceLayout`/`WorkspaceMode` serve coding and materialization.
  `UNIFAI_WORKSPACE_ROOT` replaces the coding-specific name, with no old alias;
  default `/tmp/unifai-workspaces`. The workspace adapter pins directory handles,
  rejects symlinks/special-file sources, enforces root ownership and byte limits,
  and materializes atomically with identical-retry/conflicting-content semantics.
  It translates its own I/O failures without reclassifying errors from a consumer
  or transfer stream.
- Explicit built-in module discovery uses the existing `SpecDiscoverer` optional-
  dependency policy. Artifact HTTP dependencies may be absent in a core install;
  missing internal platform imports fail rather than silently dropping plugins.

Evidence:

- Initial integrated transfer cases: 21 passed in 18.98 seconds,
  `/tmp/unifai-artifact-transfer-local-20261101.xml`.
- Focused milestone: **104 passed in 34.64 seconds**, zero failures/errors/skips,
  `/tmp/unifai-artifact-transfer-milestone-20261101.xml`. Includes actual API restart,
  thread/process coding -> publish -> deleted workspace -> separate code-program
  restore, scope/owner/role denial, revocation, expiry, file containment, FIFO refusal,
  cancellation, catalog discovery, affected HTTP routes and cold-import boundaries.
- Actual signed-cookie/Redis API role isolation: 1 passed in 4.42 seconds,
  `/tmp/unifai-artifact-native-auth-20261101.xml`; bearer access works for artifact
  transfer and is rejected on general API and credential-management routes.
- Subsequent download-admission/content hardening: 8 passed in 7.88 seconds,
  `/tmp/unifai-artifact-download-hardening-20261101.xml`.
- Workspace/transfer error separation: 6 passed in 0.05 seconds,
  `/tmp/unifai-workspace-io-boundary-20261101.xml`.
- After the explicit blob-reference naming change: 9 affected graph/code handoff,
  workspace and access cases passed in 12.97 seconds,
  `/tmp/unifai-blob-reference-contract-20261101.xml`. Strict mypy passes 18 affected
  domain/application/plugin/storage/HTTP modules. Focused lint/format/diff checks pass.

Next, in order:

1. Continue from the reusable verification operations/wait program below: actual
   check submission/reconciliation, report provenance and runtime push notification,
   then the reusable implementation/testing/review composition and UI. Keep exact
   candidate matching and explicit acceptance outcomes. Git remains optional;
   commit publication/retention and base-to-candidate change sets remain source-plugin
   work while other candidates keep their own contracts.
2. Close robustness/security acceptance alongside that work: automatic run credential
   binding/renewal/revocation, per-call delegation and stale-attempt fencing, hard-crash
   staging recovery/retention, remaining artifact issuer audit and tenant/profile
   admission. Protected preparation now preserves typed failure classification.
3. Rebuild matched receivers at the remote handoff milestone. Prove remote transfer
   across both hosts/backends, cleanup, recovery, replay and the intended credential-
   isolation boundary. The prior 660/40 execution gates predate this source and do
   not verify remote artifact behavior. Keep broad gates at feature milestones.
4. Continue durable Human Review and the remaining target implementation queue.

A receiver-private credential file does not establish isolation from hostile code
running as that same OS user. The [environment file-I/O capability investigation](../../../integrations/run-engine-environment-file-io-request.md)
records a possible infrastructure contract for a stronger out-of-band transfer
boundary. This is not a confirmed engine defect, an implemented capability, or a
claim that the current platform is ready for hostile multi-tenant workloads.

### Optional source capability slice (2026-11-01)

User clarification: do not make the platform about Git. The execution kernel passes
each operation's typed data and does not require a common artifact/source envelope.
Optional integrations own their behavior, schemas, configuration and adapters.

Implemented `mas_plugins.git`, enabled through existing `element_modules`, with
`providers/git_repository` and `operations/resolve_git_revision` /
`operations/checkout_git_revision`. Specifications, factories, provider references,
transitive bundles and operation invocation use the existing construction path.
No Git branch was added to the compiler, runtime, program model or Run Engine.
The small `GitRevision` value belongs to ADLC source semantics and has no managed
blob dependency. Application operations depend on the `GitRepository` port;
the CLI/config/filesystem implementation stays in the optional outer plugin.

Operator bindings admit explicit type-scoped owners and expose only logical
repository IDs to authored resources/results. The adapter resolves full branch/tag
refs or HEAD to a full SHA-1/SHA-256 commit, peels annotated tags and materializes
the exact recorded commit in a detached, new workspace. Branch movement does not
change a recorded candidate. Common pinned workspace traversal now lives in
`mas_plugins.workspaces` and is reused by file/blob transfer. Existing destinations
are conflicts; checkout never erases mutable work. Git configuration/templates,
hooks, unrelated protocols, submodule recursion and interactive credentials are
disabled. Output/deadlines are bounded, process ownership is explicit, raw private
diagnostics are discarded and ordinary cancellation/failure removes staging.

Evidence:

- Focused Git/application/graph-code/catalog/workspace/architecture milestone:
  **57 passed in 26.32 seconds**, zero failures/errors/skips,
  `/tmp/unifai-repository-plugin-milestone-20261101.xml`. Includes actual Git CLI,
  thread/process graph -> code child -> source operation, branch movement,
  annotated tags, SHA-256 source, owner denial, existing-work protection, ignored
  inherited Git configuration, output limits, cancellation/timeout and unchanged
  blob coding handoff after workspace deletion/API restart. The initial restricted
  run could not bind the two localhost API listeners; rerun with listener access
  passed all cases. No paid model calls.
- Strict mypy passes all eight affected domain/application/Git/workspace/storage
  source modules; focused Ruff/format and `git diff --check` pass.
- Follow-up Git adapter checks: **19 passed in 8.42 seconds**, zero failures/errors/
  skips, `/tmp/unifai-repository-restore-boundary-20261101.xml`. Adds complete local
  compute-directory deletion and exact-candidate rematerialization after branch
  movement, plus symlink-parent refusal without writes outside compute. These are
  local filesystem/process checks, not Kubernetes/OpenShell environment deletion.

This is local source materialization, not a full verification/acceptance system.
Uncertain checkout reconciliation, commit publication/retention, change-set base
identities, private Git credentials, repository size limits, hard-crash staging GC,
matched remote images and cross-backend source handoff remain required. A repository
must retain/serve a referenced commit; a SHA alone does not guarantee availability.
The checkout result identifies the initial candidate, not later uncommitted edits.
Future checks must bind trusted evidence to the exact candidate and cannot accept
an agent's own successful-looking result as verification. Other candidate types
must compose without adopting Git's source contracts.

### Verification plan and evidence-admission slice (2026-11-01)

Implemented opt-in `VerificationSubject` values and immutable plans with a frozen
operator policy, exact candidate, required checks/verifier IDs, owner-scoped stable
intent key and deadline. The generic runtime/compiler does not import these models
or adopt a Git/blob union. Ordinary operation inputs/results remain independent.

`VerificationService` owns admission, exact-subject matching, duplicate/conflicting
receipt handling, cancellation and derived outcomes. Acceptance requires every
frozen check to pass. Failed/broken checks remain rejected/error; they cannot be
replaced with a later successful result under the same check occurrence. A new
plan intent represents repair/reverification. Canonical JSON fingerprints preserve
the difference between booleans, integers and floats; Python model/dict equality
alone would incorrectly equate some candidates. Subject identities are bounded;
the trusted checker owns validation/interpretation of its candidate-specific schema.

`MongoVerificationRepository` reuses the application's native async database/client,
with majority-acknowledged writes and revision-checked atomic updates. Concurrent
receipts/cancellation do not overwrite one another. There is no extra database or
scheduler. Verification is explicitly enabled and requires Mongo storage. Plans
and receipts survive API restart; replaying an admitted intent uses its frozen
checks even if the operator policy is removed. New work still requires admission.

Native HTTP exposes plan creation, owner inspection/cancellation and a separate
evidence endpoint. Human sessions cannot attest. An admitted verifier uses its
own bearer credential plus authority ID, constrained to configured owners and the
plan's allowed check issuers. API configuration stores only the credential hash;
different verifier identities cannot share one hash. Evidence credentials do not
become native user sessions. Exact duplicate receipt retries are acknowledgments,
including after deadline/cancellation, without reopening evidence admission.

The wider wiring audit also corrected FastAPI callback parameter contracts and
prebuilt-service narrowing, composition-root concrete branch inference, async Redis
decorator return annotations and the Redis session codec/reader boundary. Bootstrap
uses application repository/authenticator ports; an outbound `RedisSessionReader`
adapts the borrowed client to the narrow text contract. Runtime execution semantics
are unchanged. The six audited wiring modules now pass the broader type check
(source roots supplied; untyped third-party stub diagnostics excluded).

Evidence:

- Domain/application/Mongo/API/architecture foundation: **31 passed in 2.80 seconds**,
  `/tmp/unifai-verification-mongo-foundation-20261101.xml`.
- Actual signed-cookie/Redis/Mongo and separate native API restart: **4 passed in
  13.47 seconds**, `/tmp/unifai-verification-native-api-20261101.xml`. A deterministic
  independent executable checks the exact Git checkout and attests passed/failed;
  both outcomes survive restart. Wrong commit/owner/role and receipt conflicts are
  denied. No paid calls. This check validates committed file content, not an entire
  software test suite or hostile compute isolation.
- Affected application/HTTP/native-auth regression milestone before the final
  wiring corrections: **284 passed in 37.21 seconds**, zero failures/errors/skips,
  `/tmp/unifai-verification-api-milestone-20261101.xml`.
- Focused policy/expiry/recovery/credential checks: **23 passed in 0.14 seconds**,
  `/tmp/unifai-verification-policy-recovery-20261101.xml`.
- Final affected milestone after wiring corrections: **334 passed in 57.58 seconds**,
  zero failures/errors/skips, `/tmp/unifai-verification-redis-wiring-milestone-20261101.xml`.
  Includes application/architecture, all native HTTP and Redis scenarios, actual
  Mongo evidence transitions, API restart, both Redis session codecs, coding/blob
  handoff and the new verification settings/identity/policy cases. This supersedes
  the earlier affected 284-case gate for these sources. It is not a full platform,
  Temporal or remote deployment matrix.
- Strict mypy passes the nine new/affected verification, Redis session-reader and
  async-translation modules. A separate broader check passes the six audited HTTP,
  settings, composition and Redis wiring modules. Ruff/format/diff checks pass;
  this does not establish repository-wide static-analysis completion.
- Added and validated `.cursor/skills/debug-verification-evidence/SKILL.md`, and
  linked it from the platform test workflow. It records identity/authority/recovery
  invariants and the limits of the CI fixture rather than inventing a runner.

Remaining at this 2026-11-01 milestone (superseded by the next slice): scoped workflow clients and reusable verification operations/programs,
actual CI submission/reconciliation adapters, report attachment/provenance, runtime
notifications/durable waiting, UI acceptance/review, and the broader remote/load/
isolation gates. The current API trusts its control plane, database and admitted
verifier. Authentication and a deterministic local checker do not prove isolation
from hostile code with that same OS identity or database authority. A passed
receipt set is separate from invocation completion and from delivery of a complete
ADLC task. The full target and goal remain active.

### Workflow verification integration (2026-11-02)

Implemented root/policy/action-scoped workflow capabilities, independent from CI
evidence authority. Native humans issue/list/revoke `/api/verification-access`
credentials; bearer `/self` returns metadata only. Issuance records owner and acting
human separately. Mongo persists hashes, expiry, revocation and bounded scope.
`VerificationActor` enforces owner, root, policy and create/read/cancel authority in
the application service. Invalid bearer input cannot fall back to a human cookie;
workflow capabilities cannot become user sessions, manage grants or attest evidence.

`mas_plugins.verification` supplies a provider and request/inspect/cancel operations
through existing specs, factories, dependency bundles and the operation invoker.
The provider verifies owner/root/policy/plan/candidate responses, bounds HTTP work,
and owns its client. Protected `SecretStr` configuration uses the existing resolver;
operator directory binding instead selects a private owner/root-keyed credential
file, allowing concurrent roots to reuse one published definition. Opaque nonce/hash
mechanics are shared with artifact credentials; purpose-specific policy is separate.

The registered `await_verification@1` application program takes a plan handle and
inspection bundle with placement and finite polling settings. Graph/code callers
use an ordinary child run. Inspections are short operations; `ProgramRuntime.sleep`
delegates waiting to native Run Engine timers. Recorded results determine replay.
It distinguishes resolved business outcomes from poll-budget exhaustion, never
inferring acceptance from invocation/program completion. Cancelling this borrower
does not cancel its plan. An authorized explicit cancel operation fences the plan.
No compiler/runtime integration branch or companion Run Engine change was needed.

Artifact storage errors now carry an application-owned infrastructure failure and
retryability. Protected construction preserves that classification while replacing
private messages/codes. Actual stopped-service calls and private-preparation tests
exercise this path instead of relying only on synthetic SDK exception assertions.

Evidence so far:

- Initial native graph/code operation checks: **6 passed in 9.12 seconds**,
  `/tmp/unifai-workflow-verification-initial-20261102.xml`.
- Native worker recovery/replay and scope matrix: **5 passed in 123.03 seconds**,
  `/tmp/unifai-verification-worker-recovery-20261102.xml`. Thread/process cases
  observe a real Temporal timer, stop the worker, persist evidence while it is
  absent, restart and replay root/child histories. Workflow credentials are absent
  from those histories. This precedes later fixture/validation additions.
- Private preparation/cancellation checks: **8 passed in 0.51 seconds**. Earlier
  application capability/wait checks passed 33 cases; final milestone supersedes
  these narrow checks once green.
- Follow-up service-error group: 23 passed, 1 failed during native API startup's
  Mongo selection before the affected operation ran. Dedicated containers were
  healthy; fresh Mongo/Redis pings took 0.005/0.011 seconds, so no service restart
  was performed. The exact affected process case then passed in 5.19 seconds,
  `/tmp/unifai-verification-process-error-recovered-20261102.xml`. The partial group
  is not recorded as a passing gate.
- Strict mypy passes 13 affected capability/artifact/application/plugin/HTTP/Mongo
  source modules; the broader six-module HTTP/composition/settings/Redis check also
  passes. The first full nonremote run had **792 passed, 1 failed in 343.14 seconds**,
  `/tmp/unifai-verification-workflow-platform-20261102.xml`. Its sole failure was
  the Git cancellation fixture's startup handshake: cancellation shared the timeout
  case's one-second operation deadline. The corrected fixture separates those
  budgets, surfaces premature task failure, permits timeout during startup and
  verifies every acquired process was reaped. Git production behavior is unchanged.
- Git lifecycle cases after that fixture correction: **19 passed in 9.62 seconds**,
  `/tmp/unifai-git-lifecycle-fixture-20261102.xml`.
- Final full nonremote milestone: **793 passed in 337.73 seconds**, zero failures,
  errors or skips, `/tmp/unifai-verification-workflow-platform-recovered-20261102.xml`.
  Actual dedicated Mongo/Redis/Temporal, separate API/workers, root/child replay,
  production TypeScript API clients, accepted/cancelled verification composition,
  scoped credentials and typed failure/cleanup paths are included. This supersedes
  the failed first run and older nonremote baseline for the current frozen source.
  Paid/remote deployment modules were excluded; this is not a complete browser UI,
  Kubernetes/OpenShell verification-placement or real-provider coding proof.
- Focused Ruff/format, strict typing for 13 affected modules and broader typing
  for six wiring modules pass. Updated verification/test skills validate. Companion
  Run Engine remains unchanged at `6039344`; matched remote images still need rebuild.

Remaining at this 2026-11-02 milestone (CI dispatch is advanced in the next slice): actual CI job submission/reconciliation, report provenance, push updates,
Human Review/UI integration, automatic root credential provisioning/renewal/revocation
and file collection, finer delegation/fencing, matched remote receivers and the full
target's remaining acceptance work. Directory binding is a root capability shared
by its configured calls, not per-node least privilege or hostile-process isolation.
The reusable waiter does not mint/renew its own authority or cancel external CI jobs.
The complete ADLC workflow and overall goal remain unfinished.

### Trusted CI dispatch and reconciliation (2026-11-03)

Implemented a first external-check integration through the canonical path:

- Domain `CheckRun` separates ready/uncertain/queued/running/completed/rejected
  dispatch status from evidence admission and plan acceptance. One stable intent
  identifies a plan/check; selecting another runner cannot duplicate that check.
- Application `CheckRunService` uses application-owned provider/repository ports,
  persists uncertainty before external submission, and grants the POST only to
  the winning Mongo revision claimant. Concurrent calls, retries, process death
  and lost acknowledgements never reset submission permission. A missing provider
  run remains unresolved rather than proving the POST was not sent.
- Optional `mas_plugins.ci.github` is a server-side operator adapter. Its binding
  fixes owner/policy/check/verifier, candidate repository, numeric GitHub workflow
  ID, dispatch ref and expected workflow commit. The private token stays in that
  binding; receiver capabilities cannot attest evidence. Native settings/bootstrap
  own clients and the existing Mongo connection. No GitHub engine/compiler branch
  or companion project modification was needed.
- Native `/api/verification-checks` submit/refresh routes require plan access and
  explicit workflow `run_check` authority. Internal CI verifier identities cannot
  also accept external evidence credentials. The existing plugin registers
  `start_verification_check` and `refresh_verification_check` through ordinary
  specs/factories/dependency references. `await_check_run@1` composes refresh with
  runtime timers and explicit resolved/poll-limit results.
- The adapter records acknowledged IDs and validates repository, workflow, workflow
  commit, event, attempt and intent-plus-candidate title. Bounded searches reconcile
  acknowledgement loss; duplicate/truncated matches and invalid provenance cannot
  attest. Completion records an immutable namespaced run/attempt receipt for the
  exact subject. A lost evidence acknowledgement can be repeated safely.
  Credential rotation preserves the admitted configuration digest.
- Test helpers share verification transport ownership and accept explicit
  policy/actions/settings/factory. Test process serialization preserves explicitly
  supplied nested `SecretStr` values without printing them. The durable GitHub
  wire fixture is clearly distinct from actual GitHub job execution.

Evidence before the broader milestone gate:

- Application/architecture verification group: **40 passed in 2.24 seconds**.
- Native API/Mongo reconstruction and GitHub wire contracts: **11 passed in
  1.12 seconds**, `/tmp/unifai-github-check-contract-recovered-20261103.xml`.
  The first restricted run could not open Mongo's localhost socket and was stopped
  after setup error; it is not passing evidence. The authorized dedicated-service
  rerun passed without restarting infrastructure.
- First graph/code CI workflow: **2 passed in 7.32 seconds** on thread/process
  receivers with a separate native HTTP process, signed cookies, Mongo/Redis and
  a deterministic peer; `/tmp/unifai-check-workflow-20261103.xml`.
- Actual API-process restart plus native/wire cases: **14 passed in 14.45 seconds**,
  `/tmp/unifai-ci-native-milestone-20261103.xml`. This precedes the stronger
  intent-plus-candidate title validation; the final affected gate covers that source.
- Evidence-acknowledgement and waiting checks: **19 passed in 0.24 seconds**.
  Strict typing passes ten affected modules and the four broader settings/bootstrap/
  HTTP wiring modules. Focused lint/format pass.
- Broader milestone: **582 passed in 129.76 seconds**, zero failures/errors/skips,
  `/tmp/unifai-ci-platform-milestone-20261103.xml`. It covers application/domain,
  architecture/import boundaries, adapters, native HTTP/Mongo/Redis, CI composition,
  API restart and the existing Temporal verification worker-recovery/replay cases.
  This precedes the final whole-reconciliation deadline correction.
- Final affected CI/native restart/graph-code gate: **18 passed in 13.81 seconds**,
  `/tmp/unifai-ci-bounded-reconciliation-20261103.xml`. Paginated search now shares
  one overall deadline instead of multiplying the request deadline per page. The
  test observes expiry during the second page without granting another POST.
  Final GitHub strict typing, focused lint/format and diff checks pass; the updated
  verification skill validates. No paid/model/GitHub calls were made. The companion
  Run Engine worktree remains clean and unchanged.

Limits at the initial dispatch milestone (report work follows below): deterministic wire tests do not prove live GitHub execution or a correct
arbitrary verifier. Operators must install a trusted workflow that checks the exact
input commit. Report provenance, provider cancellation, intervention for permanently
ambiguous dispatches, CI-specific Temporal recovery, current remote image parity
and the complete implementation/testing/review/UI workflow remain open. Persisting
reservation before POST trades automatic delivery for avoiding duplicate effects
if a crash occurs before sending; this is not exactly-once CI. Automatic credential
lifecycle, Human Review, richer composition, governance, retirement and the full
requirement audit remain in the active target queue.

### Durable CI reports and audited intervention (2026-11-03)

Implemented the next CI slice:

- Domain `CheckReportSource` freezes provider object ID, content identity, name and
  media type. `CheckReport` binds it to a managed `BlobArtifactRef`. Check records
  admit a source manifest before transfer, require matching completed reports
  before evidence, and retain the resulting references/configuration digest in
  immutable receipts. `CheckRequirement.requires_reports` makes this an optional
  application policy rather than a mandatory wrapper for all outputs.
- `CheckReportCollector` delegates verified publication to the existing artifact
  service/repository. Lazy, owned streams allow retries to recover already committed
  bytes after publication-acknowledgement loss without reopening an expired provider
  archive. Verification admission checks owner/reference identity and rechecks its
  deadline after artifact authorization I/O. Duplicate evidence cannot replace
  report provenance or an admitted configuration digest.
- The GitHub integration separates operator configuration, bounded HTTP transport,
  run reconciliation and artifact translation into cohesive adapter modules. It
  checks exact configured artifact names, run/workflow identities, expiry, size and
  digest. Download redirects require explicit HTTPS archive-host admission; a fresh
  request forwards no API authentication/cookies and follows no further redirects.
  Actual bytes pass through the authoritative artifact integrity checks before
  evidence can be committed. Archives are stored without extraction/execution.
- Native read-only check inspection needs plan-read authority. Native human
  `/{intent_id}/resolve` attaches an independently confirmed provider run to the
  current uncertain revision and audits human/reason/time with idempotent delivery.
  Stale/foreign/conflicting/unconfirmed proposals fail. Workflow capabilities
  cannot resolve, even alongside a human cookie. The action supplies no verdict and
  never repeats dispatch. This is CI intervention, not the Human Review program.
- Bootstrap reuses one artifact service for HTTP, evidence admission and reports.
  Settings require storage/download policy for reports and reject status-only
  runners for report-required checks. Operator validation errors hide raw input,
  including not-yet-parsed nested provider credentials.

Evidence before the full gate:

- Existing verification integration baseline after the transport split: **24 passed
  in 32.96 seconds**, `/tmp/unifai-report-refactor-baseline-20261103.xml`.
- Report provenance/actual durable byte tests: **13 passed in 0.13 seconds**,
  `/tmp/unifai-report-provenance-contract-20261103.xml`. They include corruption,
  absent/duplicate/expired/wrong/oversized manifests, rejected redirect origins,
  credential isolation and recovery of committed bytes after provider expiration.
- Native report restart and audited resolution: **5 passed in 28.08 seconds**,
  `/tmp/unifai-report-native-recovery-20261103.xml`. Separate native API processes,
  actual Mongo/Redis and durable filesystem storage retain reports after provider
  retention; signed-cookie graph/code execution checks workflow-role denial.
  This precedes the later expanded report-enabled graph matrix and deadline check.
- Application/adapter/architecture focused groups pass, including report ownership,
  immutable evidence, stale/concurrent resolution and post-I/O deadline fencing.
  Strict typing passes twelve affected source modules and the three broader wiring
  modules; focused lint passes.
- Initial full gate: **849 passed, 1 failed in 376.91 seconds**,
  `/tmp/unifai-ci-reports-platform-20261103.xml`. The failure exposed an original
  submission/reconciliation race in deployed Temporal agent sessions, not a passing
  milestone. Its correction and recovered full gate follow below.

Remaining: live GitHub validation, provider cancellation/compensation, permanent
absence handling, report retention/governance, automatic root credential lifecycle,
CI-specific Temporal recovery, current remote images and report/review UI. Report
provenance establishes byte identity and association with the trusted workflow;
its check implementation still must be correct. The complete reusable ADLC workflow,
Human Review, richer composition, production policy and final retirement/audit remain
in scope. No compiler/engine/environment-manager branch was added for this work.

### Admission ownership correction and recovered platform milestone (2026-11-03)

The full gate exposed a real control-plane race: reconciliation treated an active
`starting` submission as immediately recoverable while its original native start
was still in flight. Recovery could create the native run first, causing the
original caller to receive `RUN_ALREADY_EXISTS` and persist an incorrect refusal.

The correction belongs in UnifAI's application delivery ownership:

- A private `SubmissionClaim` token/expiry is atomically assigned in the existing
  execution repository. Live claims prevent another API/reconciler from redelivering
  the original request. Submission I/O has a configurable finite deadline (default
  30 seconds); claim expiry adds five seconds for crash recovery. Finishing an
  expired claim cannot overwrite a newer owner or release its token.
- Initial collisions still refuse ownership. Recovery preserves the exact stored
  request/private native ID; the gateway's collision rule was not relaxed. Accepted
  records cannot regress to a late admission refusal.
- Durable `cancel_requested` intent survives delayed admission and stale record
  projections, with cancellation applied through the existing engine port once
  observable. It is distinct from confirmed cancellation. Owner/location admission
  precedes mutation; unavailable original locations leave records untouched.
- Memory and Mongo implement one shared application-owned claim contract. These
  are application submission claims, not worker/environment leases or another
  scheduler. Run Engine still owns native execution, cancellation and cleanup.

Evidence:

- Deterministic Local host recovery initially passed **10 cases in 0.59 seconds**;
  the expanded claim/deadline group passed **12 in 0.61 seconds**. The barrier holds
  before native acceptance, tests another service observing it, then tests expiry
  and a late original collision. Genuine foreign-collision refusal remains covered.
- First native follow-up: **20 passed, 1 failed in 21.16 seconds**,
  `/tmp/unifai-admission-native-recovered-20261103.xml`. The location-preservation
  assertion caught cancellation intent being recorded before checking the original
  coordinator. Moving that guard before mutation fixed the regression.
- Recovered native matrix: **21 passed in 19.06 seconds**,
  `/tmp/unifai-admission-native-location-recovered-20261103.xml`: actual Mongo
  claim fencing, Local barriers/deadlines/cancellation and both thread/process
  deployed agent-session cases on Temporal, with API restart/native replay.
- Final full nonremote milestone: **856 passed in 385.40 seconds**, zero failures,
  errors or skips, `/tmp/unifai-ci-reports-admission-platform-recovered-20261103.xml`.
  Dedicated Mongo/Redis/Temporal, native API/worker processes, production TypeScript
  API clients, required-report graph/code execution, report retention/restart,
  audited intervention, admission ownership and cancellation fencing are included.
  The tested source remained frozen; only independent documentation changed during
  the gate. This supersedes the failed first full gate for current-source evidence.
- Strict typing passes twelve report/verification modules and five execution/
  repository modules; broader typing passes three wiring modules. Focused lint,
  format and diff checks pass. Three current diagnostic/test skills validate,
  including the new execution-admission skill. The companion Run Engine worktree
  remains clean and unchanged.
- The exact orphaned thread-only workflow from the failed gate was inspected via
  public Temporal APIs, verified against its unique test queue, cancellation was
  requested and the abandoned native record was terminated after its owned worker
  and fixtures had exited. No unrelated histories/resources were removed.

The gate excludes remote-program, OpenShell-policy and paid-Codex modules. It does
not prove live GitHub execution, current Kubernetes/OpenShell image parity, complete
browser/editor coverage or production scale. The next product slice is the reusable
Human Review program and interaction UI; remaining CI cancellation/absence/retention,
source publication, credentials, richer composition, governance and final audit
stay in the active target queue. The overall goal remains unfinished.

### Human Review native execution and reviewer UI (2026-11-03)

Implemented the reusable `human_review@1` application program through existing
`ProgramCallStep`, application runtime ports and registered operation bundles.
`review_service` and open/inspect/close review effects use ordinary specifications,
factories, provider references and builders. The domain/application contracts do
not import HTTP, Mongo, Run Engine or vendor clients. There is no new review
scheduler, environment manager, compiler branch or parallel element registry.

UnifAI owns the exact subject/schema/deadline, frozen reviewer assignment, scoped
workflow access, persisted decision and delivery intent. Mongo commits a human
response with its outbox state through revision CAS. Identical response keys/data
are acknowledged after delivery; conflicts and closed occurrences never overwrite
the human response. Review workflow capabilities cannot answer for a human, even
alongside a valid human cookie. Public execution message routes reject the reserved
review namespace. Engine messages only wake inspection; payloads cannot approve.

The actual App has `/reviews` and `/reviews/{id}` with assigned-human inbox,
subject/policy/execution inspection, schema-driven simple fields or complex JSON,
approve/reject, immutable response audit and saved-but-not-yet-notified state.
Request cancellation and revision comparisons prevent stale snapshots/callbacks
from replacing a newer accepted response. Uncertain submission preserves its exact
key, decision and data for retry. The UI uses the same native API as workers.

The restart scenario found an application shutdown defect: after a worker stopped,
Temporal's acknowledged message Update could keep the API-owned reconciler waiting
past the test process shutdown budget. Shutdown now cancels and drains that owned
task. Committed submission/session/review intents remain recoverable; no engine
acknowledgement semantics or native ownership checks were weakened.

Evidence before the broad milestone:

- Application policy/coordinator and architecture checks: **30 passed in 2.32
  seconds**, `/tmp/unifai-review-application-schema-20261103.xml`. Includes schema
  admission, local reference targets, immutable decisions, lost acknowledgements,
  forged wakeups, finite waits and cancellation propagation. Subsequent small
  guard/ownership refinements are included in the broad milestone, not this earlier
  source snapshot.
- Native graph/code x thread/process x approve/reject matrix: **8 passed in 26.47
  seconds**, `/tmp/unifai-review-native-recovered-20261103.xml`. Real signed-cookie
  owner/reviewer users, Mongo/Redis, API and operation receivers. Earlier failures
  were fixture expectations (native validation is 422; message content is `data`).
- Native expiry/cancellation/supersession and cross-root denial: **3 passed in
  10.68 seconds**, `/tmp/unifai-review-lifecycle-20261103.xml`.
- Temporal recovery: initial fixture failed by looking for a native identity at the
  HTTP top level; the infrastructure test now reads the persisted execution adapter.
  The next run exposed the real shutdown issue described above. Recovered result:
  **2 passed in 18.09 seconds**,
  `/tmp/unifai-review-temporal-shutdown-recovered-20261103.xml`, with API/worker
  restart, a decision accepted while the worker is stopped, immutable retry and
  root/child native history replay. The subsequent test-owned cleanup finalizer
  is covered by the broad milestone.
- Production TypeScript reviewer exports against native FastAPI: **1 passed in
  5.12 seconds**, `/tmp/unifai-review-ui-clients-20261103.xml`.
- Actual App browser: assigned reviewer submitted schema-conforming feedback,
  approval persisted after reload, and the native graph/child workflow completed
  with that exact response. Screenshot:
  `/tmp/unifai-review-browser-proof-20261103.png`. The owned runner removed its
  unique database and signed-cookie sessions; no OAuth/provider login claim.
- Strict typing passes all **12** review source modules with declared JSON Schema
  stubs; wiring typing passes **5** modules with explicit source roots. UI static
  types and production build pass. Vite still reports existing circular vendor
  chunks, a mixed static/dynamic auth import and large bundle warnings.
- The two abandoned root runs and their two children from failed native review gates were matched to their
  exact test windows, fixture metadata and unique task queues through public
  Temporal APIs, then cancelled/terminated after their owned workers had exited.
  No unrelated execution or SDK journal was modified.

Final full nonremote milestone: **891 passed in 446.77 seconds**, zero failures,
errors or skips, `/tmp/unifai-human-review-platform-20261103.xml`. This includes
dedicated Mongo/Redis/Temporal, native API/worker processes, all current Human
Review scenarios, production TypeScript API clients and earlier platform behavior.
Implementation/test/UI sources stayed frozen; only documentation/skills changed
during the gate. Remote-program, OpenShell-policy and paid-Codex modules were
explicitly excluded. This supersedes earlier nonremote evidence for this source
snapshot; it does not establish remote image parity or production scale.

Remaining: visual review-block authoring, parallel/repeated occurrence and retained
environment scenarios, automatic capability lifecycle and reviewer artifact access
policy. Remote receiver images still predate this capability. Complete reusable
ADLC composition, broader UI/API parity, dynamic governance, external-effect
lifecycle and final retirement/audit remain in the active target queue.

### Core composition and initial program composer (2026-11-03)

Added ordinary registered `map@1`, `repeat@1`, `choose@1` and `wait@1` application
programs. Graph and application remain the only program kinds. Existing graphs own
static Flow ordering/dependencies/joins. The core programs use existing runtime
child, message and timer ports; no Run Engine modification, alternative scheduler
or new graph step kind was introduced.

- Map uses a bounded coordination-task pool and declared item limit; outputs keep
  input order, stable item keys and actual child execution identities. Its join
  requires all items to succeed; failure/parent cancellation requests cancellation
  of outstanding owned child calls and drains transient tasks.
- Repeat passes recorded state through distinct pinned child iterations, requires a
  boolean completion predicate and reports `limit_reached` separately from
  `satisfied`. Choose validates the full selection before starting one declared
  branch, without exposing unknown values in diagnostics. Wait distinguishes
  native event delivery from deadline expiry and does not grant human authority.
- A narrow optional configuration capability declares required child aliases.
  The existing application registration/save/publication/compiler path validates
  those aliases before dispatch; no program-specific admission branches were added.
- The composition root installs core programs and explicit extensions in one
  registry; workers preload the same core module. Authenticated program catalog
  discovery returns public configuration/input/output metadata, not SDK settings.
- The App's new `/programs` composer creates a new registered application program,
  configures bounds/bindings, verifies pinned graph/code revisions, publishes and
  runs it through native APIs. It preserves uncertain-start identity, polls
  authoritative status and offers cancellation. This is initial creation/execution
  UI, not the completed visual graph/typed-port/library editor.
- Shared signed-session settings now live in `support/native_settings.py`; business
  review policies remain in their own review fixture rather than leaking into the
  general program browser fixture. Shared JSON UI values no longer belong to the
  review API module. Existing factories/builders, profile and environment ownership
  remain authoritative.

Focused evidence:

- Application composition, Local graph/code/operation receivers and architecture
  guards: **29 passed in 3.69 seconds**,
  `/tmp/unifai-composition-local-20261103.xml`. Covers concurrency bounds, item order,
  failure/cancellation ownership, strict loop predicates/limits, branch admission,
  waits, pinned graph revisions and actual occurrence identity.
- Real Temporal and native history replay: **3 passed in 6.71 seconds**,
  `/tmp/unifai-composition-temporal-20261103.xml`. Graph → Map → graph → operation
  runs on thread/process receivers; nested Map/Repeat uses distinct iteration
  children; Wait survives a worker stop/restart. All root/descendant histories
  replay. This is not a remote backend or Map worker-loss matrix.
- Production TypeScript program clients plus existing graph data contracts:
  **2 passed in 5.59 seconds**,
  `/tmp/unifai-composition-ui-clients-20261103.xml`. Real native HTTP/Mongo publication,
  pinned references, Map execution, idempotent start observation and Wait cancellation.
- Actual App browser with a signed session: verified the pinned operation graph,
  authored/published a bounded Map and executed three items. The terminal result
  contains ordered operation outputs and distinct child execution IDs. Proof:
  `/Users/odaiodeh/.codex/visualizations/2026/10/28/01a183fd-8230-74d3-a2f0-9abb2671a4cc/program-composition-proof-20261103.png`.
  The owned browser/API/membership fixture exited and removed its unique database
  and signed-cookie session. This is not OAuth or full editor coverage.
- Strict typing passes five new composition/registration/runtime-port modules;
  broader typing passes six wiring/compiler/catalog/service modules. Explicit
  narrowing and SDK payload annotations also resolved existing typing errors in
  the touched compiler preview path. Focused lint, UI types and production build
  pass; existing Vite vendor-chunk and mixed-import warnings remain.

Final full nonremote milestone: **915 passed in 439.56 seconds**, zero failures,
errors or skips, `/tmp/unifai-composition-platform-20261103.xml`. Dedicated
Mongo/Redis/Temporal, native API/worker processes, production TypeScript clients,
all current composition/review cases and previous platform behavior are included.
Implementation/test/UI sources stayed frozen; only independent documentation and
skills changed during the gate. The remote-program, OpenShell-policy and paid-Codex
modules were explicitly excluded. This is current-source nonremote evidence, not
remote image parity, complete visual editor or production-scale validation.

Next: align the authoring/library contracts with the unified-builder clarification
below, then implement operation/program call blocks and inline controls in the
evolved blueprint builder. Exercise parallel/repeated business reviews and the
reusable implement/check/review/repair workflow through those same contracts.
Finish typed connection validation and hierarchical runtime/source mapping.
Complete authoring concurrency/library lifecycle, automatic credential
lifecycle, retained remote environments/current receiver images, dynamic budgets
and stale-attempt fencing. Product parity, external-effect lifecycle, retirement
and final requirement audit remain open. The overall goal is not complete.

### Unified builder clarification and next plan (2026-11-03)

The user's clarified product model is saved configured elements → reusable
resources → blueprint/program composition → published reusable program revisions
→ inspectable executions. The architecture already supports graph/code program
composition; the target now explicitly requires one evolved builder and two
separate expansion modes. This updates design/implementation planning only; it does
not resume the paused goal or claim new runtime behavior.

1. Establish canonical authoring/library contracts: distinct element resources and
   program definitions, reusable published revisions, versioned drafts and optimistic
   edits, typed inputs/outputs/bindings, and explicit profiles/environment imports.
   Blueprint authoring and program publication share one executable model.
2. Evolve the existing builder with resource-backed operation blocks, pinned graph/
   code program calls and inline Flow/Map/Repeat/Choose/Wait controls. Incorporate
   the interim `/programs` screen's useful functionality. Lower controls through the
   existing runtime/registry; do not create a competing authoring language or runner.
3. Add definition expansion with read-only pinned inspection, separate child-draft
   editing/publication and explicit caller upgrades. Add runtime drill-down mapping
   blocks to actual child runs, invocations, items, iterations and attempts. Show
   observed code-program calls without fabricating an editable Python source graph.
4. Prove the unified path with parallel/repeated review and the reusable Engineering
   implement/check/review/repair program, independently and inside a larger workflow.
   Include UI save/reload/publication, stable pins, authoritative runtime status,
   profile/environment ownership and cancellation/recovery evidence.
5. Continue the full active queue: trusted outcomes/artifact handoff, external-effect
   and credential lifecycle, current remote images/matrices, dynamic governance,
   required product parity, removal of superseded paths and final requirement audit.

The separate initial composer is not the final product structure. Programs retain
graph and registered-application implementations; ordinary operation invocations
need no artificial child program. Application/adapter/engine responsibilities and
the existing specification/factory/builder pipeline remain unchanged.

### One Programs library and schema-configured implementations (2026-11-03)

The user clarified that graph composition and backend-implemented coordination
must not become separate public program categories or competing UI experiences.
A backend program supplies its implementation/version and configuration/input/
output schemas through registration. Users discover it, configure it, bind declared
dependencies, save a named draft, publish, and run or reuse its pinned revision in
the same Programs library/workspace used for visually composed programs.

Keep internal implementation-specific validation/editing where necessary, without
parallel graph/code stacks or mandatory graph wrappers. Keep program configuration,
run inputs and execution/environment policy separate. Element resources retain
their own typed construction contracts. A generic form is not an editable graph
of arbitrary Python; execution inspection uses actual observed calls and events.

Goal alignment: this clarifies existing goal points 1-3 and 6, rather than replacing
the goal or adding a new execution abstraction. Acceptance must include registering
a backend program, discovering its schemas in the UI, configuring/saving/reloading/
publishing it, running it independently, and calling the same pinned revision from
a larger program. Verify typed contracts, authorization, revision isolation and
execution-profile/environment ownership through that path.

This is a documentation/acceptance clarification while the goal is paused. No
runtime implementation or new test evidence is claimed by this entry.

### Versioned program library and schema-configured UI (2026-11-03)

Implemented one owner-scoped Programs library and canonical versioned authoring
contract. A saved `ProgramDraft` holds a normalized definition, optimistic version
and separate presentation metadata. Memory and Mongo adapters share storage-contract
tests for owner/type-scoped pages, detached reads, one-winner concurrent edits,
source-idempotent publication, revision pinning and descending pagination. Mongo
checks mirrored storage identities and returns application-owned safe errors.
Publication uses majority writes and an atomic source-version identity; competing
allocations may leave revision-number gaps, so callers follow returned references.

The native API and production TypeScript clients use explicit save/publication
versions. Schema-based configuration, save/reopen/edit, name-based pinned program
dependencies and revision selection now share one workspace. A graph view projects
canonical program calls/ordering/data bindings and saves positions outside executable
semantics. Query scope includes owner and authenticated human; invalid JSON blocks
submission, unsaved changes require discard, and publication/run retries preserve
their original identities. The create-only composer and its replaced settings
component were removed. The older blueprint builder is still pending convergence.

Browser evidence: configure a registered greeting, save/reopen/publish, run alone,
compose its revision in a visual program, publish/run the caller, then publish a
new dependency revision and run the unchanged caller. The caller retained revision
1 and its original result. A subsequent UI check verified invalid JSON prevents a
save and triggers the unsaved-changes guard. These use the actual App, signed-cookie
API and isolated Mongo/Redis with deterministic installed programs, not model calls
or external identity-provider certification. Both fixtures removed their unique
databases after shutdown.

Initial focused evidence: 11 shared application/memory/Mongo tests passed, followed
by 33 HTTP/Mongo/coding/actual-TypeScript-client tests. Strict mypy for authoring,
publication and both repositories passes after correcting a shadowed local name.
UI static types and schema/data contracts pass; browser builds retain existing
vendor circular-chunk and bundle-size warnings.

Broad gates are not yet green for this slice: the first stopped after 524 passes
on an unmigrated test helper reading the old import envelope. After caller fixes,
the next stopped after 527 passes on a native authentication Redis read timeout;
own containers were healthy and Redis PING returned PONG. Focused recovery then
passed 37 cases before exposing another test loop that reused create-version zero
for an edit. That caller now carries the observed draft version. Recovery and
current-source broad evidence must be recorded before counting this milestone as
fully verified; none of these partial runs replaces the earlier 915-test baseline.

Focused recovery subsequently passed all 89 Mongo and Temporal-operation cases
(`/tmp/unifai-program-library-storage-recovered-20261103.xml`). The deployed
thread/process recovery cases passed before the separate create-version test
failure in the earlier recovery run. A later broad attempt stopped after 528 passes
because the shared HTTP test publisher still treated every call as creation. It
now reads the observed draft version and publishes the returned source version.
The resulting scheduling/Redis/Temporal recovery gate passed all 86 cases in
180.38 seconds (`/tmp/unifai-program-library-durable-gate-20261103.xml`).

**Recovered current-source milestone:** 923 passed in 557.19 seconds, zero failures,
errors or skips (`/tmp/unifai-program-library-platform-confirmed-20261103.xml`).
The exact command selected `multi-agent/tests --ui-clients`, excluding only
`integration/deployment/test_remote_programs.py`, `test_openshell_policies.py` and
`test_codex_agents.py`, with strict markers/importlib and short tracebacks. It used
own Mongo `27018`, Redis `6380/15` and Temporal `7234`; no paid-provider flag was set.
This covers current Local/Temporal, thread/process, native workers, restart/replay
and production TypeScript clients, not current remote images or production scale.
No source edits occurred during the gate. The 1,614-file source manifest at
`/tmp/unifai-program-library-source-20261103.json` remained unchanged, SHA-256
`554378248c53e92a4106bf82a49221274d5123b404f09d199a313b44e2c8b7db`, against
Git baseline `d4573ddec20f2c5d9e3ef83106bd98baecc8b2c7` plus the recorded worktree.

The final App browser fixture also published/ran a schema-configured program,
verified invalid-JSON/save/discard behavior and readable fields through the existing
`dark-inputs` theme convention, then closed and removed its unique database. Final
screenshots live in this chat's visualization directory as
`program-library-configured-20261103.png` and `program-library-completed-20261103.png`.
The composition diagnostic skill now describes the canonical envelope/library
flow; the UI knowledge skill no longer exempts large legacy contexts/hooks from
boundary review. This is a completed library milestone, not completion of the goal.

Final static checks also pass: TypeScript `tsc --noEmit`, Ruff on the changed program
contracts/services/repositories/tests, strict mypy on authoring/publication and both
repositories, and skill validation. The production UI Vite build passes in 5.36
seconds; its existing vendor circular-chunk, mixed static/dynamic auth import and
large-bundle warnings remain. Pytest's configured filters are not evidence that
all dependencies are warning-free.

At this milestone, next work was to resolve saved resources and their authorized transitive closure
on the server; never construct execution snapshots from browser display/redacted
configuration. Add resource-backed blocks, inline controls and typed connections,
converge/retire the old builder, then definition/runtime expansion and the reusable
Engineering proof. Drafts currently require valid executable topology/configuration;
decide how unfinished visual work is saved within the canonical authoring model
before declaring full builder usability. Remote images/matrices, credential and
dynamic-governance work remain in the full goal queue.

### Saved-resource program blocks and construction depth (2026-11-03)

The Programs editor now selects saved operation/node resources through the native,
paginated library. Authoring sends owner-scoped source revision markers. The
application-owned `SavedResourceResolver` captures and rechecks the authorized
transitive closure through `ResourceSnapshotSource`; native resource authoring
retains visibility, caller overlays and private-field policy. Normal configuration
protection persists frozen resource definitions. Browser display configuration is
never used as an execution snapshot. Explicit adoption is required to replace
shared snapshots; equivalent configurations reuse protected references. Existing
step placement is separate and stays unchanged on configuration adoption.

Actual App proof added the saved operation, bound public inputs/results, saved,
reopened, published and ran it through process placement. Results included its
transitive dependency's configured value, including after reopening. The fixture
closed and removed its unique database. Screenshots in this chat's visualization
directory: `resource-backed-program-20261103.png` and
`resource-backed-program-result-20261103.png`.

Focused application/source/architecture checks passed 26 cases; native HTTP/Mongo
checks passed 14; selected production TypeScript clients passed 3. The affected
milestone passed 628 in 95.32 seconds after correcting a catalog test double that
omitted its installed implementation version. The first full gate passed 936 in
543.03 seconds (`/tmp/unifai-resource-selections-platform-20261103.xml`).

Follow-up regressions then exposed recursive traversal failure on a 1,200-resource
chain and a depth-bound bypass when all dependencies were selected as roots.
All three failed before correction. Shared bundle integrity/resolution now uses
iterative traversal with the same dependency order/digests. Admission checks the
actual longest dependency path, including reused subgraphs. Source capture remains
bounded to 1,000 resources and depth 64; this is not an execution-tree budget.
The 22 focused correction checks passed; strict mypy and affected Ruff checks pass.

**Frozen-source milestone after correction:** 939 passed in 494.95 seconds, zero
failures/errors/skips, `/tmp/unifai-resource-selections-platform-depth-20261103.xml`.
Selected `multi-agent/tests --ui-clients`, excluding only remote programs,
OpenShell policy and paid Codex deployment modules, with strict markers/importlib.
Own Mongo 27018, Redis 6380/15 and Temporal 7234 were used; no paid flag was set.
Source remained unchanged throughout the gate: 1,624 files, manifest
`/tmp/unifai-resource-selections-depth-source-20261103.json`, SHA-256
`ca41ae49442bb1861e1f4455dd0fe7f7fc53f27e91a34259f2feacba29223f1b`, against
Git baseline `d4573ddec20f2c5d9e3ef83106bd98baecc8b2c7` plus recorded worktree.
Installed Run Engine remained clean at `60393440efd3876cd6c81e0b013e8bf6d9167659`,
SDK source SHA-256 `3579a831ceb38fa8174f8084afcb8bcf0be769798637936ab1623527722ea35f`.
No companion-project modifications were made.

UI static types and production Vite build passed; existing circular-vendor,
mixed static/dynamic auth-import and large-bundle warnings remain. Composition/UI
diagnostic skills now document source capture, explicit adoption and depth checks.
This gate covers Local/Temporal, thread/process and existing restart/replay/client
contracts. It does not establish current remote image parity, production scale,
inline controls, complete visual contracts or the reusable Engineering workflow.
Subsequent routing-editor changes require their own evidence below.

### Conditional routing authoring and graph edits (2026-11-03)

The same Programs graph projection now authors conditional routes from saved
condition resources. It uses the existing source-selection/protection path and
canonical `ConditionalRoute`; no compiler, engine or public program kind was
added. Symbolic metadata supplies normalized boolean labels, while other conditions
can use explicit labels. Each route retains its own profile/environment selection,
separate from the preceding work block and ordinary unconditional edges.

Pure UI graph transformations identify conditional edges by source/label/target.
Deleting one label preserves other labels sharing its target and any ordinary
edge to that target. Block removal drops incident connections, clears removed
entry/exit choices and drops pending selections for unused roots; it does not
invent a replacement path or inspect browser configuration to prune dependencies.
Existing frozen resource snapshots remain intact. The selected-block panel owns
one UID-scoped component lifetime.

The actual App check caught a duplicate React-key defect after the initial
transport checks passed: repeated branch changes accumulated stale configuration
controls. The panel lifetime correction was rebuilt and rechecked. Repeated branch
removal/addition now retains exactly the two expected controls (work + condition).
The browser authored true/false destinations, saved/reopened with condition process
placement, published and completed score → yes → finish. Removing the start block
cleared entry and native form validation prevented save; discard restored the
saved graph. Running its unchanged revision again completed with the same result.
The temporary tab closed, API shutdown completed and fixture database
`unifai_program_browser_4abb838f6bdf433dbaaac3e5dd33f5e4` was removed. Screenshot:
`program-routing-result-20261103.png` in this chat's visualization directory.

Verification after the UI correction: **7 passed in 24.56 seconds**, zero failures,
errors or skips, `/tmp/unifai-program-routing-ui-gate-20261103.xml`. Command selected
all `multi-agent/tests/integration/ui/test_editor_client.py --ui-clients` using own
Mongo 27018 and Redis 6380/15. The program client publishes a mixed pinned-program/
saved-operation graph with a saved process-backed condition and verifies both
branches and their rejoin. Plain-data contracts separately check label-specific
deletion, entry/exit removal, source-selection filtering and unchanged input data.
An earlier focused run passed 2 with 5 deselected in 8.60 seconds; it preceded the
browser reconciliation fix and is not its evidence.

TypeScript static checks, affected Python Ruff/format checks, skill validation and
production Vite build pass (5.16 seconds; existing bundle/import warnings remain).
No production Python runtime or Run Engine source changed after the 939-case gate.
Post-gate inventory `/tmp/unifai-program-routing-source-20261103.json` records 1,628
files, SHA-256 `3b3b901c85744fd0ce0da03e3ff456c8af1361958495fbbec401932056e7f004`.
It was created after verification; no source changes occurred during the selected
UI gate. The earlier broad gate is evidence for its recorded foundation snapshot,
not a claim that all 939 tests were rerun against this subsequent editor slice.

The integrated UI order recorded above supersedes this milestone's earlier plan
to postpone builder convergence. Save unfinished visual drafts coherently and
converge the existing builder/library/session experience before extending a
separate Program product. Saved resources in
registered-program configuration, the reusable Engineering workflow, automatic
credential lifecycle/root governance and current remote-image matrices remain
required by the full goal. This slice does not complete those requirements.

### Backend draft/publication boundary (2026-11-03)

Resumed the replacement backend-led goal. `ProgramDefinition` now retains
unfinished graph topology and declared dependency bindings without introducing a
second draft language. Stable block/route identities and typed configuration stay
mandatory; existing ownership/CAS checks and configuration-secret protection apply
to every save. Registered configuration can be saved before required child aliases
are bound. Arbitrary partially filled nested configuration is not supported by this
slice; schemas still validate supplied configuration at save.

The new application validation result is version-fenced, read-only and portable:
safe issue code/message/path/severity plus derived readiness. Native
`POST /api/programs/{id}/validation` and the production TypeScript client use the
same observed-version command as publication. Publication invokes the same checks;
it does not trust an earlier report. The domain revision model independently
rejects incomplete executable structure, including copied data that bypassed draft
construction. Placement preview explicitly checks completeness. No provider client,
environment or engine run is allocated to validate a draft.

Shared memory/Mongo persistence and public HTTP contracts prove save/reopen,
invalid publication/start refusal, completion, actual operation execution and an
older published revision remaining usable after a later incomplete edit. Source-
idempotent publication retries retain the earlier revision. Application cases
cover stale/foreign validation, safe foreign-child diagnostics, missing references
and private fields protected even in an unfinished graph. No Run Engine changes
or additional execution pipeline were introduced.

Verification:

- Focused recovery: 38 passed in 4.35 seconds after correcting the new HTTP test's
  expectation that a missing memory record returns None; its port raises KeyError.
- Native Mongo/API and resource snapshot checks: 13 passed in 14.14 seconds,
  `/tmp/unifai-draft-boundary-native-20261103.xml`, actual thread/process work.
- Production program/data TypeScript clients: 2 passed, 5 deselected in 6.96 seconds,
  `/tmp/unifai-draft-boundary-clients-20261103.xml`. No visual screen expansion was
  needed for this backend contract probe.
- The first broader gate stopped with 6 passed/1 failed because a new corruption
  test created its invalid graph before the intended revision boundary; draft
  identity validation correctly rejected it earlier. Correcting the setup to copy
  an already constructed definition preserves the guard; all 11 focused boundary
  cases passed before the rerun.
- **Recovered frozen-source backend milestone: 615 passed in 64.66 seconds, zero
  failures/errors/skips**, `/tmp/unifai-draft-boundary-backend-recovered-20261103.xml`.
  Selected all domain/application/adapters/architecture/HTTP/Local run-engine tests,
  Mongo Program repository/resource snapshots, and Temporal Programs/composition/
  operations/conditions. Own Mongo 27018, Redis 6380/15 and Temporal 7234 were used.
  This is an affected backend gate, not a rerun of the entire platform or remote
  matrix. No paid calls were made.
- The source stayed frozen: 1,631 files in
  `/tmp/unifai-draft-boundary-recovered-source-20261103.json`, SHA-256
  `0885363d430a0d6f9119b1cd02eec987dd4447adb03ad1e2d3a550be649018a5`.
  Run Engine stayed clean at `60393440efd3876cd6c81e0b013e8bf6d9167659` with its
  recorded SDK source unchanged. The client gate used the same production source;
  the subsequent correction changed only the corruption test setup.
- Strict mypy passes the three authoring/domain/service source modules. TypeScript
  static checks, affected Ruff checks, diagnostic skill validation and whitespace
  checks pass. Existing warning filters are not dependency-wide warning evidence.

Readiness describes the current publication rules, not effective placement,
concrete input correctness, native plan admission or successful execution. The
interim editor still requires entry/exit choices; its full integration belongs to
the later unified UI milestone. Current-image Kubernetes/OpenShell verification
remains open. Next backend work includes remaining Program package ownership,
publication/contract validation, safe partial configuration authoring and owned
inline composition. This is progress within the canonical-foundation milestone,
not completion of that milestone or the full goal.

### Program domain/application ownership (2026-11-03)

Moved existing behavior to its actual layer and updated 116 current source callers:

- `mas.domain.programs.models`: definitions, references, bindings, revisions and
  publication invariants; `mas.domain.programs.bindings`: pure value projection.
- `mas.domain.execution_preferences`, `mas.domain.metadata` and `mas.domain.models`:
  shared SDK-free placement values, step metadata and the existing strict frozen
  boundary base. Authoring DTOs reuse that base instead of a duplicate class.
- `mas.application.programs`: authoring, repository/runtime ports, registry,
  publication service, graph-context preparation and existing blueprint import.

Removed the old Program package and core placement module without forwarding
aliases. All production/test consumers use their owners, including execution,
sessions, reviews, verification, scheduling, construction adapters and worker
entrypoints. No new runtime or plugin-specific compiler branch was added.
Definitions/revisions keep the same serialized shape; this does not promise old
worker/history compatibility. Remaining execution/session/resource/plugin package
consolidation and the larger backend requirements are still open.

The existing dependency guards now cover the moved services and values. Added
cold-domain import/round-trip checks that refuse application/SDK initialization,
and actual import-resolution checks for retired namespaces. Receiver verification
checks installed canonical imports and absent replaced paths in addition to source
hashes. Dedicated receiver/default derivative tags are now
`program-boundaries-20261103`; images must be rebuilt before remote evidence.

Initial focused checks passed 55 domain/publication/architecture cases in 2.47
seconds, then 34 domain/boundary cases in 2.37 seconds; the final standalone
architecture selection passed 11 in 2.19 seconds. Strict mypy passes nine moved/
shared modules. These checks do not certify installed receivers or the full
migration.

Current-source regression: **958 passed in 562.88 seconds**, zero failures,
errors, skips or reported warnings, including production TypeScript client suites:
`/tmp/unifai-program-boundaries-platform-20261103.xml`. The 1,637-file source
manifest remained unchanged throughout the gate; replaced source files remained
absent. SDK source stayed clean at `60393440efd3876cd6c81e0b013e8bf6d9167659`.

A subsequent wider typing check identified optional-placement narrowing and
dictionary variance in the moved blueprint importer. The importer now selects
authored versus inherited placement through one explicit `None` check and uses
the canonical `Bindings` annotation. Strict mypy passes **11 selected modules**.
The affected architecture/placement/secrets/Mongo/Local/Temporal selection passes
**72 tests in 29.06 seconds**:
`/tmp/unifai-program-boundaries-importer-20261103.xml`. Focused Ruff passes.
The 958-test gate precedes this typing correction; the focused suite verifies it.

Final build/test inputs are frozen in
`/tmp/unifai-program-boundaries-final-source-20261103.json`, 1,637 files,
SHA-256 `953a50c4be55753ed185df31b21a88d82fb9362a1665555281740d3b8f1ae3cd`.
The checked-in gateway default now uses the same receiver generation; the running
gateway is preserved and deployment tests select their image explicitly.
Matched-image verification and the remote matrix remain pending. These backend
checks do not establish full package consolidation, the Engineering workflow,
unified UI, production scalability or completion of the goal.

Receiver build/preflight status: public registry connectivity passed. The first
build waited on `docker-credential-desktop`; only that owned build/helper tree was
stopped. Retrying with a temporary anonymous Docker configuration and the observed
daemon endpoint passed metadata/source loading and reached package installation.
The build was observed live in `/tmp/unifai-program-boundaries-receiver-build-20261103.log`.
Docker Desktop reports running, but a direct daemon ping timed out and container
exec/statistics remain unresponsive. The OpenShell mTLS health preflight returned
`UNAVAILABLE` during handshake; public client/server certificate dates are valid
through 2026-11-05. No certificate replacement, TLS bypass or global Docker restart
was performed. Remote tests have not started; these are infrastructure observations,
not application test failures or receiving-image evidence. The updated infrastructure
diagnostic skill validates successfully.

The build was subsequently cancelled deliberately after the infrastructure remained
unresponsive; its exact handle returned **130** and the build log confirms context
cancellation. The owned statistics/exec diagnostics also completed. No image or
remote matrix result was obtained. Source work resumed only after that terminal
observation; the Program-only build manifest is historical after the next extraction.

### Execution domain/application ownership (2026-11-03)

Separated the old execution package and core context module by responsibility,
updating **104 Python callers** without compatibility aliases:

- `mas.domain.execution`: portable context, lifecycle/failure records, canonical
  request digest and safe placement values.
- `mas.application.execution`: submission requests, prepared adapter snapshots,
  delivery claims, execution services/ports, placement inspection port and the
  mutable receiver-local context holder.

The domain context cannot import its mutable holder or application delivery data.
It reuses the strict frozen model, requires an explicit identity, rejects unknown
fields and accepts JSON-only metadata tags. Removed the unknown-owner backfill and
silent extra-field discard. Existing team-owner/acting-human credential semantics
remain explicit; this metadata is not itself cryptographic authority.

Added domain boundary cases for missing identity, unknown fields, live objects,
secret wrappers and team credential round trips. Added cold domain/record/digest
checks and actual resolution checks for retired execution imports. Installed-image
verification now requires the canonical context/holder/service owners and absence
of both old Program and execution namespaces. Remaining session/resource/plugin
consolidation is still open.

Evidence:

- Initial domain/application/architecture selection: **66 passed in 3.02 seconds**.
- Frozen-source Local regression: **685 passed in 60.86 seconds**, zero failures,
  errors, skips or reported warnings:
  `/tmp/unifai-execution-boundaries-local-20261103.xml`. This covers domain,
  application, architecture, adapters, Local thread/process dispatch/recovery,
  catalog, deterministic coding, repository operations and memory-backed HTTP.
- Strict mypy passes all **11 new/moved execution modules**. Focused Ruff passes;
  the wider changed-caller check found one pre-existing unused session import,
  which was removed after the gate.
- The 1,642-file gate manifest remained unchanged, with all retired source paths
  absent: `/tmp/unifai-execution-boundaries-source-20261103.json`, SHA-256
  `e2a71c25aad6d9242e9c27ae6217991358669d0abfcc09190fe11324aa50d17f`.
  That manifest precedes the unused-import cleanup.

After cleanup, **19 architecture/Local session cases passed in 2.76 seconds**:
`/tmp/unifai-execution-boundaries-cleanup-20261103.xml`. Changed callers pass import/
unused-import lint, all 11 execution modules pass strict mypy, and source/SDK checks
show no unexpected edits or restored retired paths. Final inputs are frozen in
`/tmp/unifai-execution-boundaries-final-source-20261103.json`, 1,642 files,
SHA-256 `049a8ebe7276bc55c8dcfb31aa54bd3f204579c87f8d1aedc671f13131be97e4`.

Mongo/Redis/Temporal and matched Kubernetes/OpenShell receiving images remain
unverified after this extraction. The dedicated stack is preserved; restarting
Docker Desktop requires explicit permission because it interrupts other projects.
Local checks do not establish remote cleanup, full backend completion or the
unified UI. Next functional work is owned inline composition and deeper publication
contract validation, alongside the remaining architecture and reliability goals.

On rechecking after cancellation and Local work, Docker's daemon ping recovered.
Mongo, Redis, Temporal and the existing certificate-authenticated OpenShell gateway
then passed direct preflight checks. No restart or certificate change was needed;
receiver rebuilding and native verification resumed from the final source above.

Both new receiver images now match **1,292 installed Python files** against the
selected SDK, shared utilities, application, adapters, bootstrap/configuration,
plugins and receiving fixtures. Canonical Program/context/service imports match
their owners and replaced Program/execution namespaces are absent:
`/tmp/unifai-execution-boundaries-images-20261103.jsonl`.

| Image | Verified identity |
| --- | --- |
| `unifai-receiver:program-boundaries-20261103` | `sha256:99d56e5ceb354cd7defa6793d586289f3977d12bc2ae67ac00cdf9cfa066f906` |
| `unifai-sandbox:program-boundaries-20261103` | `sha256:c89f7e4c8710a915b0539f07f457b6564844a9acc42822c87d051e72b73cb12b` |

Image content verification does not establish native replay, remote placement,
environment ownership or cleanup. The selected native and deployment gates remain
pending below. No Docker Desktop restart was performed or is currently needed.

The verified Kubernetes image was loaded into dedicated `unifai-e2e`. The native
gate passes **177 tests in 200.26 seconds**, zero failures/errors/skips or reported
warnings: `/tmp/unifai-execution-boundaries-native-20261103.xml`. It covers all
selected Mongo/Redis persistence contracts, separate Temporal workers/replay and
the production TypeScript editor clients. Source stayed frozen. This supplements
the 685-case Local gate rather than claiming a new full-platform gate. Remote
placement and policy checks are separate pending evidence.

The remote matrix subsequently ended with **35 passed and one setup error** in
1,418.98 seconds: `/tmp/unifai-execution-boundaries-remote-20261103.xml`.
OpenShell/Temporal's private-settings case timed out in sandbox readiness before
application execution; four later child-owned-scope cases were not reached.
Docker ping and mTLS health passed afterward. A separate resource diagnostic did
not execute because automatic approval review timed out. No Docker restart was
performed. The failed/unrun cases remain queued for milestone follow-up; do not
repeat the 35 passing cases merely to recover that setup error. Separate egress
policy checks were deferred under the user's milestone cadence. These images and
results precede the following element/invocation changes.

### Graph-independent element contracts and operation invocation (2026-11-03)

Removed graph channel declarations from generic `BaseElementSpec`. State-based
node/condition specifications now specialize `GraphElementSpec`; graph-only state/
step protocols moved out of generic core contracts. Updated installed graph specs,
graph consumers and shared test fixtures. Operations, catalog and construction now
cold-import/initialize without graph-state modules. Construction dependency metadata
cannot accidentally create graph channel producers/consumers. Abstract spec bases
stay out of discovery/installation, concrete metadata is validated and condition
graph contracts are checked before native submission. No second registry/builder
was introduced. Existing node/condition behavior remains graph-specific.

Portable calls now separate an explicit invocation `key` from optional graph step
context. Typed operations reject graph context and skip graph `set_context`
injection, including when they have a coincidentally named application method.
Both graph and backend Program operation calls use that same context-free path.
Graph adapters retain explicit matching step context and own state mappings.
Receiver contract is `unifai-elements-v2`, prepared format `runengine/request-v3`;
there is no old-payload backfill or compatibility alias.

Focused evidence: **154 passed in 10.73 seconds** for construction/resource/agent/
catalog/Local graph paths before the invocation change; **167 passed in 12.87
seconds** after adding invocation context separation, tracing and receiver cases;
then **140 passed in 9.96 seconds** after final abstract/discovery handling:
`/tmp/unifai-graph-contract-final-20261103.xml`. This last selection covers
architecture, operation/spec contracts, registry, invocation adapters, catalog and
actual Local graph/code/thread/process/condition/session execution. Strict mypy
passes four affected contract modules. Heavy Docker/Temporal/remote gates are
deferred to the next appropriate milestone; the previously built images do not
certify this newer source. Generic partial configuration, owned inline composition,
deeper schema/binding validation and the remaining target remain open.

### Owned inline Program bodies (2026-11-03; recorded 2026-11-04)

Implemented the backend owned-body slice through the existing Program lifecycle.
`ProgramBody` owns coordination/configuration/interfaces but no independent
library identity or owner. Graph calls and backend aliases accept either an owned
body or immutable published reference. Recursive save protects nested credentials
and captures saved resources within explicit stable body paths. Publication checks
nested topology, construction and authorized dependency closure. Calling a finite
older revision with the same Program ID is allowed; actual revision cycles are
refused. Owned edits change the enclosing digest without changing old revisions.

The compiler lowers these targets through the same native child integration.
Inline defaults inherit enclosing placement unless overridden; published calls
retain their own defaults. Environment access still requires explicit imports.
Execution records and request identities include source reference, body path and
digest; published boundaries reset the source address. Private payloads contain
selected-scope contracts/configuration/compiled requests rather than entire root
definitions. Entrypoint/prepared contracts are `unifai-program-v2` and
`runengine/request-v4`, superseding the prior slice's v3 prepared format. Old
prototype payloads are not supported. Program interface failures no longer echo
rejected values in public diagnostics.

The production client types carry owned targets, scoped source selections and
execution source metadata. Existing graph edits preserve scoped selections until
their owning block is removed. The interim workspace labels/preserves inline
targets and offers explicit replacement with published references. This is not
visual inline authoring or completed product convergence.

Evidence before the requested pause:

- **136 passed in 7.84 seconds**, `/tmp/unifai-owned-bodies-focused-20261103.xml`:
  domain/application publication, configuration protection, revision/source
  identity, adapter placement/import validation, real Local graph/backend/Map/
  Repeat/Choose/Wait/thread/process execution, HTTP privacy and boundary guards.
- **1 production client journey passed in 8.42 seconds**,
  `/tmp/unifai-owned-bodies-production-client-20261103.xml`: actual TypeScript
  clients → TCP FastAPI → Mongo → Local thread/process work, including scoped saved
  resources, save/reopen/publish, immutable source identity and child inspection.
  The sandbox attempt could not connect to localhost; the authorized run outside
  that networking restriction passed. This successful-path client gate preceded
  the final generic interface-error diagnostic change, which the focused gate
  verifies. No broader browser claim.
- Strict mypy passed seven affected production modules; affected Python lint,
  full UI TypeScript check and pure graph/session client contracts passed.

No new Docker images, Temporal suites or Kubernetes/OpenShell matrices were run.
Previously built images are stale for this slice. Keep the earlier failed
OpenShell setup case, four unrun child-scope cases and policy follow-up queued for
the next meaningful remote milestone. Generic partial configuration, deeper static
binding compatibility, execution-tree governance, authoritative occurrence views,
reusable Engineering and unified UI remain unfinished. Next backend work is
schema-aware safe incomplete configuration, followed by deeper contract admission.

### Safe incomplete configuration and embedded construction (2026-11-04)

Implemented schema-aware missing configuration fields for registered Programs,
graph resources and owned bodies. `ConfigurationDraft` retains original Pydantic
field metadata without fabricating runtime models. Normal complete validation
remains the first path. Nested aliases/paths, union selections, collections,
SecretStr/secret hints and encrypted-field declarations share the normal owner-
scoped protection service. Provided invalid constraints/field validators are not
silently bypassed. Ambiguous nonempty variants and unsupported incomplete shapes
fail closed. Repeat saves verify and reuse opaque references; foreign references
cannot grant credentials. Complete model semantics remain a publication gate.

Embedded bundle/resource configurations now receive their installed-schema checks
at publication and compilation. Structural bundle validity alone is insufficient.
Incomplete resource credentials can be protected while missing fields remain draft
work. All authored graph resources, including unused entries, are validated in one
snapshot traversal; no per-resource quadratic root traversal was added. Draft edits
after publication leave old revisions executable and unchanged.

A real receiver test exposed the category factory reconstructing normalized
configuration with aliases required again. The existing factory path now validates
canonical names as well. This fixes actual aliased credential construction; there
is no new factory/registry or alternate invocation path.

Evidence:

- **153 passed in 8.79 seconds**, `/tmp/unifai-configuration-drafts-focused-20261104.xml`,
  before the final category factory correction: application protection/draft/source
  contracts, deep construction, adapter placement, Local composition/operations/
  sessions/blueprints, HTTP and architecture guards.
- Mongo/production-client gate: **5 passed, 2 failed in 11.73 seconds**,
  `/tmp/unifai-configuration-drafts-production-20261104.xml`. Existing encrypted
  credential cases and the expanded actual TypeScript→TCP FastAPI→Mongo journey
  passed. That journey saves/reopens protected incomplete configuration, refuses
  publication, completes it, then publishes and executes. The two new receiver
  cases exposed the canonical-name bug described above.
- Corrected receiver cases: **2 passed in 1.71 seconds**,
  `/tmp/unifai-configuration-drafts-receiver-fix-20261104.xml`, using actual encrypted
  Mongo storage and Local thread/process receivers; portable definitions, execution
  records and encrypted storage contain no test credential literals.
- Final affected checks after the factory correction: **41 passed in 2.33 seconds**,
  `/tmp/unifai-configuration-drafts-final-affected-20261104.xml`: draft privacy,
  canonical alias construction, built-in/tool configuration, preparation/lifetimes,
  completion then published/owned execution and old-revision immutability, native
  operation and Program paths. Strict mypy passes five production modules plus
  the shared installed scenario module; affected lint and UI TypeScript pass.

The first memory-only receiver attempt correctly refused to resolve credentials
without a receiver secret store. It was replaced with the existing production
encrypted-store/receiver fixture; no test-only credential transport was introduced.
No paid providers, image rebuilds, Temporal or remote suites were run in this slice.
They remain at the next appropriate milestone with the previously recorded remote
follow-ups. Full UI unfinished-form/inline editing, deeper static binding/schema
admission, tree governance, observation, Engineering and UI convergence remain open.

Final source manifest (Python production/tests and UI/client-test code, excluding
private state): `/tmp/unifai-configuration-drafts-source-20261104.json`, 1,642 files,
aggregate SHA-256 `c8c40b50c6f0a74b8f994e24ffd0c9af00703ff96769ffe09bdd1dbbaa126e58`.
The final two Local draft journeys also passed after using the returned draft
version instead of inferring it. Internal incomplete-tree representations omit
their values from repr. Run Engine remains clean and unchanged at
`60393440efd3876cd6c81e0b013e8bf6d9167659`. No current-image acceptance is claimed.

### Binding admission and bundled interface schemas (2026-11-04)

Added application-owned `InterfaceContract`, `BindingProjection` and `GraphContracts`
through the existing authoring/publication path. Missing required call inputs,
undeclared closed destinations, invalid literal requests and provably impossible
input/result paths remain saveable drafts but cannot publish. Diagnostics expose
`INVALID_BINDING` and authored paths without values. Owned/pinned children share
the checks; pinned revision loading is memoized per validation request. The service
now receives the installed element registry and owns its stateless validators.
All four composition roots/call sites were converted without a compatibility facade.

The compiler repeats frozen-revision application validation before native request
preparation. Operation input aliases and alias paths retain actual Pydantic behavior.
Serialized result schemas match canonical returned output. Root input errors are
safe and occur before execution record admission; malformed dynamically arriving
values still fail through the normal operation invocation path.

Schemas use Draft 2020-12 and bundled references/IDs. No schema URL retrieval occurs
at validation or execution. The schema-aware reference traversal ignores reference-
looking enum/default/example data. Unknown/different dialects reject safely.
Static recursive/shared analysis terminates; nested resource scopes and other
unknown projections defer to concrete validation rather than inventing compatibility.
No new scheduler, provider invocation or engine-project change was introduced.

Evidence:

- Initial baseline: **78 passed, 1 failed in 5.25 seconds**,
  `/tmp/unifai-binding-admission-initial-20261104.xml`. The previous runtime-error
  fixture intentionally omitted a required input, which now correctly fails at
  publication. Reworked that fixture to bind an actual malformed dynamic value;
  runtime-boundary and privacy assertions remain covered.
- **35 passed in 2.35 seconds**, `/tmp/unifai-binding-native-20261104.xml`:
  projection contracts, restored revision refusal and canonical/simple/compound
  alias execution on actual Local thread/process receivers.
- **184 passed in 10.67 seconds**,
  `/tmp/unifai-binding-admission-focused-20261104.xml`: application publication,
  configuration/secrets, composition policy, execution adapters, Local operation/
  Program/control/blueprint execution, HTTP/privacy and architecture guards.
- **1 production client journey passed in 8.99 seconds**,
  `/tmp/unifai-binding-admission-production-client-20261104.xml`: actual TypeScript
  clients → TCP FastAPI → Mongo → Local work, including invalid binding readiness,
  refused publication, correction and execution alongside prior owned/configuration
  scenarios. Full UI TypeScript and pure graph/session client contracts also pass.
- The subsequent dialect guard's first import check caught an incorrect exception
  module; corrected it to the library's public JSON Schema module. Final targeted
  checks: **19 passed in 0.05 seconds**, `/tmp/unifai-binding-dialect-final-20261104.xml`.
  Strict mypy passes five affected production modules; affected Python lint passes.

No heavy Docker/Temporal/remote gate or paid provider was run. Existing images
remain stale for installed-source changes. The earlier remote follow-up queue is
unchanged. Next foundation work: generic installed backend input/result model
enforcement, declared backend child-call projections, graph-local state/type and
branch/join data availability, and explicit authored join semantics. Then continue
the existing reliability/governance/observation/Engineering/UI milestones. This
slice does not establish full static compatibility or finish the overall goal.

Source manifest: `/tmp/unifai-binding-admission-source-20261104.json`, 1,645 code/
test/package files, aggregate SHA-256
`96dafd81b3b794a4300437a09498959bc63183555b3f391d3f9093a798eea993`.
The broad/client gates precede the final dialect guard; its focused checks cover
that final change. Run Engine remains clean at
`60393440efd3876cd6c81e0b013e8bf6d9167659`; current remote image acceptance is pending.

### Installed backend Program model enforcement (2026-11-04)

Added application-owned `ApplicationInvoker` through the existing registered Program
path. Configuration, optional installed input/result models and portable finite JSON
are enforced centrally. Input aliases/defaults normalize before implementation calls;
result serializers/computed fields normalize before published output-schema checks.
Published input schemas still check submitted intent. Safe diagnostics omit model
values. Runtime ports and native execution ownership are unchanged.

`ApplicationRegistration` validates installed declarations and supplies canonical
serialization schemas. Graph result-binding admission checks installed backend result
models as well as published schemas. Adapter `ApplicationCall` groups portable
function/model references; prepared format is `runengine/request-v5` and Program
entrypoint contract is `unifai-program-v3`. Earlier prototype formats are removed,
not retained as a second path. No Run Engine source was changed.

Shared `support/typed_programs.py` scenarios deliberately rely on the generic invoker:
aliases, defaults, custom validators, normalized output, computed fields, safe failures,
finite values, RootModel arrays and narrower published schemas. Owned and pinned
graph children and backend composition use the same implementation. Submitted inputs
remain execution intent; separately observed normalized inputs remain phase-5 work.
Whole-value scalar/array graph projections remain open. Installed validators/defaults/
serializers must be pure and deterministic; this is not arbitrary-Python replay safety.

Evidence:

- Initial native model checks: **6 passed, 2 failed**. The fixture assumed graph
  values replace prior state, whereas the existing reducer merges updates. Corrected
  its explicit root projection and asserted the actual child's normalized result;
  the rerun passed all eight cases. No production reducer change was needed.
- Final HTTP/native cases: **24 passed in 2.18 seconds**,
  `/tmp/unifai-program-models-http-native-20261104.xml`, including strict root JSON,
  installed/public schema layering and native safe contract failures.
- **238 passed in 11.13 seconds**, zero skips/failures/errors,
  `/tmp/unifai-program-models-focused-20261104.xml`: application invocation,
  execution, binding/configuration/publication/composition/review/verification,
  execution adapters, Local Programs/operations/blueprints/sessions, HTTP and
  architecture guards. This terminal JUnit report was inspected after observation
  output was lost; the gate was not restarted merely to recover that output.
- **1 production client journey passed in 9.11 seconds**,
  `/tmp/unifai-program-models-production-client-20261104.xml`: TypeScript clients
  through TCP FastAPI, Mongo and Local execution, including installed-model
  normalization and a custom-validator refusal that JSON Schema alone cannot express.
- Full UI TypeScript compilation and strict mypy for ten affected production/shared
  scenario modules pass. Affected Python lint passes.

No paid provider, Docker rebuild, Temporal/replay or Kubernetes/OpenShell matrix was
run for this slice. Installed images remain stale; current remote/recovery and prior
failed/unrun remote follow-ups remain required at the planned milestone. Next:
declared backend child-call projections, graph-local state/type/data availability
and explicit joins, then the existing reliability/control/observation/Engineering/UI
queue. The overall goal remains unfinished.

Source manifest: `/tmp/unifai-program-models-source-20261104.json`, 1,650 code/test/
package files, aggregate SHA-256
`bb0cbea618e4ac1230cbbbb72a3dd058978a780e69a96b00385370e2a3226e1a`.
Run Engine is clean at `60393440efd3876cd6c81e0b013e8bf6d9167659`.

### Declared backend child-call admission (2026-11-04)

Extended the existing validator to `ProgramContracts`, handling graph and declared
backend calls through the same `BindingProjection` checks. Removed the former
`GraphContracts` name and alias-only `ChildRequirements` interface without forwarding
aliases. Application-owned `ChildContracts.child_contracts()` now declares aliases,
request projections/local scope schemas and consumed result bindings/models.
Publication still resolves/authorizes the actual owned/pinned targets; declarations
cannot select arbitrary Programs or bypass the existing compiler/runtime path.

Map/Repeat use named scope models both for actual request construction and admission.
Repeat declares consumed state and strict boolean bindings. Choose checks every branch,
including pass-through where its input shape is known. Missing required inputs,
impossible scope/result paths and malformed literal predicates reject publication
with `INVALID_BINDING` at the child alias. Incomplete mappings remain saveable drafts.
Without a local scope schema, validation uses normalized installed parent input,
falling back to public input only when no input model is declared. Custom backend
coordinators use the same interface without validator/compiler implementation-key
branches. No scheduler, registry or saved language was added.

Pass-through checks are conservative: required source fields cannot target forbidden
destinations and required destination/model fields cannot be impossible at the source.
Unknown/open/optional structures retain runtime checks. This is not general schema
subtyping, graph-wide availability proof or static analysis of arbitrary Python.
Implementations must honor their declarations; actual values still validate through
the existing invocation boundary. Whole-value projections remain outstanding.

Evidence:

- **34 passed in 0.16 seconds**, application invocation/composition and new child
  contracts, `/tmp/unifai-child-contracts-application-20261104.xml`.
- **67 passed in 3.40 seconds**, final owned/pinned/native composition and installed
  model tests, `/tmp/unifai-child-contracts-final-native-20261104.xml`. Includes
  Map/Repeat/Choose using typed children and a custom coordinator passing normalized
  input to a child with a canonical public input schema. Earlier native intermediate
  gates passed 55 and 47 cases before the additional custom-coordinator coverage.
- **107 passed in 3.61 seconds**,
  `/tmp/unifai-child-contracts-shared-validation-20261104.xml`: shared binding,
  configuration/secrets, publication/readiness/review/verification, execution adapter
  and architecture/import guards affected by the validator and port changes.
- **1 production client journey passed in 8.97 seconds**, six unrelated cases
  deselected, `/tmp/unifai-child-contracts-production-client-20261104.xml`:
  TypeScript → TCP FastAPI → isolated Mongo → Local execution. An invalid typed
  Map saves, readiness/publication refuse, correction publishes and two actual child
  executions return normalized results. Existing composition/resource journeys pass.
- Strict mypy for six affected production modules, full UI TypeScript compilation,
  affected Python lint, skill validation and whitespace checks pass.

No paid calls or heavy Docker/Temporal/Kubernetes/OpenShell/recovery suite was run.
Images remain stale; remote/replay/cleanup obligations are unchanged and belong at
the planned frozen-source execution milestone. Next backend foundation work:
whole-value projections, graph-local state/type/data availability and explicit join
semantics; then reliability/control, observation, reusable Engineering and unified UI.
The overall goal remains active and unfinished.

Source manifest: `/tmp/unifai-child-contracts-source-20261104.json`, 1,651 code/test/
package files, aggregate SHA-256
`c1c6d14af90fbee53d2b4481cd41129fd1b6ab87a959a4cf6b7bcf00833f07f7`.

### Whole-value projections and graph input/result scopes (2026-11-04)

Domain `Projection` now selects a complete path/literal value or constructs named
fields through the same pure projection function. Operation/Program call inputs,
graph returns and Map/Repeat/Choose child inputs accept arrays, scalars and null
without artificial wrappers. Named graph initialization/output updates remain
objects. Literal authoring and projected values reject nonfinite/nonportable JSON;
selected containers are detached. Safe binding failures translate to contract errors.

Every graph starts with the original invocation JSON in `input`. Actual typed
operation/Program results are indexed by step UID in `results`, with independent
parallel-key merging. Portable mappings/resume updates cannot overwrite those
platform-owned scopes. State-based nodes do not copy full state into the result
index. Existing named channel writes still work. The index is latest current data
per UID, not occurrence/attempt history or an artifact store. Graph-local schemas,
control-flow availability, explicit authored joins and retention limits remain open.

Typed operation ports now accept/return JSON and enforce ordinary installed
Pydantic models, including RootModels, using the same construction/factory/receiver
path. New shared test operations follow those conventions; there is no array-specific
compiler branch. Prepared format is `runengine/request-v6`, Program entrypoint
`unifai-program-v4`, receiver `unifai-elements-v3`, graph state `unifai-graph-state-v2`.
Removed prototype shapes have no compatibility reader. Shared GraphState restoration
now correctly declares subtype-preserving `Self`; receiving specification references
are checked before registration. No Run Engine source changes were made.

Evidence:

- **85 passed in 2.76 seconds**, initial existing operation/invocation/binding/
  composition/mapping checks before introducing graph input/result scopes,
  `/tmp/unifai-whole-value-initial-20261104.xml`.
- **107 passed in 5.17 seconds**, `/tmp/unifai-whole-value-composition-20261104.xml`:
  domain detachment/shape/finite JSON, literal/read-only publication checks,
  adapter scope guards, actual thread/process operations, owned/pinned values,
  Map/Repeat/Choose, parallel result merging and unchanged graph revision reuse
  from graph/backend callers. Earlier intermediate checks passed 44 cases.
- Broader focused gate: **279 passed, 5 failed in 17.32 seconds**,
  `/tmp/unifai-whole-value-focused-20261104.xml`. One unit parameterization used a
  positional tuple tail, accidentally including the new valid identity Program;
  replaced positional selection with named implementation keys. Four new backend
  operation fixtures used a nonexistent bundle `resources` constructor field;
  corrected them to use the normal `ElementBundleResolver` construction path.
  These were fixture errors; no production behavior changed to satisfy them.
- Corrected affected checks: **38 passed in 2.63 seconds**,
  `/tmp/unifai-whole-value-corrections-20261104.xml`, including direct backend
  array/scalar operation invocation on both thread/process receivers. Counts
  overlap the preceding gates; they are not a new full-regression pass claim.
- **1 production client journey passed in 9.55 seconds**, six unrelated cases
  deselected, `/tmp/unifai-whole-value-production-client-20261104.xml`: actual
  TypeScript clients → TCP FastAPI → isolated Mongo → Local execution, publishing
  an array operation graph and composing the same revision into a graph caller.
  Previous resource/configuration/control journeys also pass. The subsequent full
  TypeScript check exposed an omitted `inputs` property in the existing execution
  client type; added the field already returned/asserted by the real API journey.
- Full UI TypeScript compilation, pure graph/session client contracts, strict mypy
  for twelve affected production/shared-fixture modules and affected Python lint
  pass. Current source manifest below includes the corrected tests/client type.

No paid calls, heavy image rebuild or Temporal/Kubernetes/OpenShell/replay gate was
run. Images remain stale; previous failed/unrun remote follow-ups remain required
at the planned frozen-source execution milestone. Next foundation: graph-local
source/type/data availability and explicit joins, followed by the existing
reliability/control/observation/Engineering/unified-UI queue. The full goal is active.

Source manifest: `/tmp/unifai-whole-value-source-20261104.json`, 1,655 code/test/
package files, aggregate SHA-256
`37ed5802da26ac36a25bdfe774f0f4300af32c4c23f0ab92dde3fd7daf8e5257`.
Run Engine remains clean at `60393440efd3876cd6c81e0b013e8bf6d9167659`.

### Scoped graph interfaces and explicit join preferences (2026-11-04)

Added application `GraphDataScope` for graph input/indexed-result references, keeping
each public/installed schema in its original reference document. Publication rejects
unknown/nonindexed/unreachable producers, self-result reads, missing producer-to-
consumer ordering paths and provably disjoint public JSON types. Nullable/unknown
structure and installed Pydantic coercion retain concrete runtime checks. Whole graph
state/result-index projections are objects, distinct from the invocation value in
`input`. Overlap checking is conservative, not general schema assignability or proof
that every optional value exists.

Extracted bundled schema navigation/errors into application `programs.interfaces`;
`ProgramContracts` now composes that owner with scoped graph and installed call
interfaces. Updated actual callers/tests rather than adding a forwarding facade.
These services do not import engine SDK types, construct capabilities or schedule
work. Dependency construction and invocation still use their existing owners.

Domain `JoinPolicy` and `GraphDefinition.join_policy` explicitly select `active`
(default) or `all`. Definitions/revisions retain the preference and the compiler
lowers it to the public native graph policy. The existing editor exposes the field;
no parallel authoring/execution product was added. Each nested graph may choose its
own policy. There is no claimed per-node race/first-result join support. Prepared
format remains `runengine/request-v6`; the lowered native policy was already part
of that payload. No receiving wire change or companion-project modification occurred.

The public engine source confirms that a condition replaces that source's ordinary
successors. Reachability follows that rule. The earlier guide's unconditional-edge
wording was corrected. Consistent mixed ordinary/conditional source handling across
the builder and Blueprint importer remains required; do not treat this as an engine
bug or silently assume a union of successors. Use explicit forks for always-active
parallel work. Structural ordering paths alone do not prove conditional producers
ran or establish cyclic first-iteration availability.

Evidence:

- Initial focused checks: **106 passed, 1 failed in 9.41 seconds**,
  `/tmp/unifai-graph-scope-initial-20261104.xml`. Stronger checks exposed an impossible
  default object output schema on the existing array-operation dynamic-error fixture.
  Declared its actual array output contract; kept the dynamic missing-path execution
  and privacy assertions intact.
- **100 passed in 7.52 seconds**, `/tmp/unifai-graph-scope-contracts-20261104.xml`:
  new application scope/type/order/refusal tests, existing binding/child contracts,
  actual thread/process values and controls, conditional routing, and parallel child
  execution under both join policies. Native compiled-plan inspection verifies each
  selected policy before execution.
- **135 passed in 7.88 seconds**, `/tmp/unifai-graph-scope-shared-20261104.xml`:
  publication/readiness/owned-body/configuration/review/verification, execution
  adapters, Local Programs/blueprints/sessions, HTTP and architecture/import guards.
- **1 production client journey passed in 9.73 seconds**, six unrelated cases
  deselected, `/tmp/unifai-graph-scope-production-client-20261104.xml`: TypeScript
  through TCP FastAPI, isolated Mongo and Local execution. It inspects the frozen
  all-predecessor preference, refuses an unordered result read, corrects the graph,
  and invokes the same published array Program twice with actual result propagation.
- Final targeted whole-graph/result-index object guards: **14 passed in 0.06 seconds**,
  `/tmp/unifai-graph-scope-final-20261104.xml`. Earlier broader/client gates precede
  this last guard; the focused check covers it. Strict mypy for six affected
  production modules, UI TypeScript compilation and affected Python lint pass.

No paid provider, Docker rebuild or Temporal/Kubernetes/OpenShell/replay gate was
run. Existing images remain stale. Next foundation work is route-sensitive result
availability and mixed-route authoring/import semantics, then richer mutable-state
contracts and the existing reliability/control/observation/Engineering/UI queue.
Remote/recovery/cleanup follow-ups remain required at the planned milestone. The
overall goal is active; this is not completion or full graph verification.

Source manifest: `/tmp/unifai-graph-scope-source-20261104.json`, 1,658 code/test/
package files, aggregate SHA-256
`bbebc855ef8d58d41e26a7512f7c6f246f03ac07d71fb14e515bb78ea00db7b6`.
Run Engine is clean at `60393440efd3876cd6c81e0b013e8bf6d9167659`.

### Canonical routing and conditional result availability (2026-11-04)

Canonical graph publication now rejects a source with both ordinary successors and
conditional branches; incomplete mixed authoring remains saveable. The canvas blocks
new ordinary connections from routed sources and requires explicit removal of existing
ordinary successors before routing is added. It does not silently rewrite edges.
Blueprint conversion treats redundant `after` links to declared branch targets as
branch metadata and rejects unmapped conditional dependencies. Both branch-only and
redundant-after Blueprints use the same canonical graph and normal process receiver.

Extracted pure application `GraphFlow` from schema navigation. It owns reachability
and bounded activation analysis; `GraphDataScope` owns input/result schema selection.
For acyclic active-path joins, a result consumer must have an ordering path and must
not activate on a declared route that skips its producer. A consumer inside that
producer's branch is valid. Conditions are not executed or constant-folded using
plugin-specific configuration. Routing permits empty/multiple selected destinations;
guards represent that declared contract. Scheduling, actual decisions, effects and
replay remain native. No engine source or second scheduler was introduced.

Activation expressions retain at most 256 minimal terms per node; reachability
caches retain at most 64 source sets per flow. Terms/parents are processed in stable
order. Cycles and expansions beyond the activation cap defer the unresolved guarantee
to runtime; structural/source/value contracts still apply. All-predecessor joins
require ancestors before a consumer executes but do not certify exit reachability.
The native tests explicitly cover missing cyclic data and an unexecuted static-all
exit. Neither is converted into accepted work.

Removed the obsolete condition-normalization exception for undeclared `END`.
It is an ordinary declared label, including direct routing's no-recipient outcome.
Updated direct-router descriptive metadata and closed the existing normalizer's
result-variable typing gap. Prepared/entrypoint shapes are unchanged; current
formats remain those in the guide. Earlier prototype formats are not restored.

Evidence:

- **64 passed in 8.01 seconds**, `/tmp/unifai-route-flow-initial-20261104.xml`:
  initial application/native conditional values, graph data interfaces, Blueprint
  conversion and real condition execution.
- **94 passed in 10.04 seconds**, `/tmp/unifai-route-flow-native-20261104.xml`:
  shared branch definitions, refusal/correction, actual branch-local child inputs/
  results under thread/process conditions, cyclic runtime failure, all-predecessor
  exit failure, Blueprint branch metadata normalization/refusal, value composition
  and existing routing. This gate precedes the final END-normalization cleanup.
- **41 passed in 5.64 seconds**, `/tmp/unifai-route-labels-final-20261104.xml`:
  final condition normalization and real thread/process routing, including declared
  and undeclared END behavior. The subsequent direct-router description and local
  type annotation cleanup are covered by lint/strict typing; routing code is unchanged.
- **130 passed in 5.69 seconds**, `/tmp/unifai-route-flow-shared-20261104.xml`:
  shared binding/composition/child/owned-body/draft services, execution adapters,
  Local Sessions, HTTP and architecture/import guards.
- **1 production client journey passed in 9.74 seconds**, six unrelated cases
  deselected, `/tmp/unifai-route-flow-production-client-20261104.xml`: TypeScript
  clients → TCP FastAPI → isolated Mongo → Local execution. Mixed routing saves as
  a draft, readiness/publication refuse it, explicit edge removal corrects it and
  both real branches run. Existing resource/configuration/value/Program journeys pass.
- Full UI TypeScript compilation, strict mypy for seven affected production/shared
  fixture modules and affected Python lint pass. No actual browser gesture check
  or large-graph/load proof is claimed for the small canvas guard.

No paid provider, Docker rebuild or Temporal/Kubernetes/OpenShell/replay gate was
run. Installed images remain stale, and prior failed/unrun remote follow-ups remain
required at the planned milestone. Next foundation work: schemas/ownership of
existing writable graph channels and explicit merge/conflict checks, using indexed
results for ordinary typed dataflow. Do not create another state/execution engine.
Then continue reliability/control, authoritative observation, reusable Engineering
and unified UI; richer cyclic proofs and the full completion audit remain open.

Source manifest: `/tmp/unifai-route-flow-source-20261104.json`, 1,662 code/test/
package files, aggregate SHA-256
`2bff08224ac0b0e42b1855b596f1975d60bc9b158ead9a10d38fada23c05c261`.
Run Engine remains clean at `60393440efd3876cd6c81e0b013e8bf6d9167659`.
The full goal remains active and unfinished.

## Application-owned state contracts and writer policy (2026-11-04)

Completed a focused backend foundation slice. Application `ProgramState` owns the
existing graph channel schemas, read-only invocation/result scopes, portable
updates and redacted contract failures. The Run Engine state class is now a thin
native integration. Publication validates initialization/output mappings and
installed node/condition channel declarations. Conditions cannot declare writes.
Receiving adapters validate actual returned node changes against declared write
permissions and concrete channel types.

`GraphWritePolicy.ORDERED` defaults to requiring proven acyclic ordering for
overlapping declared channel writers. Explicit `REDUCE` uses existing named
reducers; some have stable overwrite semantics. This is not a commutative merge
guarantee, a general race detector or a second state engine. The policy is graph-
wide; Blueprint conversion explicitly preserves existing reducer behavior. The
small interim canvas selector and production client exercise refusal/correction.
Generic operations remain independent of graph state. Arbitrary per-graph state
schemas, cyclic writer proofs and per-channel policy overrides are not implemented.

Evidence:

- Initial gate: **84 passed, 1 failed**,
  `/tmp/unifai-state-contracts-initial-20261104.xml`. One old test expected a missing
  graph specification to fail at dispatch; it now correctly expects publication
  refusal. No production validation was weakened.
- **90 passed in 10.02 seconds**,
  `/tmp/unifai-state-contracts-native-20261104.xml`: application admission/state,
  actual thread/process node writes, conditions, values and Blueprint conversion.
- Final focused gate: **130 passed in 6.35 seconds**,
  `/tmp/unifai-state-contracts-focused-20261104.xml`: application state, bindings,
  graph interfaces/flow, thread/process state failures, Local Sessions, execution
  adapters, HTTP and architecture guards. Dynamic initialization fails before
  invoking children; dynamic output mapping fails after the actual child result.
- **1 production TypeScript client journey passed in 7.49 seconds**,
  `/tmp/unifai-state-contracts-production-client-20261104.xml`: client → real TCP
  FastAPI → isolated Mongo → Local execution, including writer-policy refusal,
  explicit correction and both routing branches. This is not a browser gesture test.
- Strict mypy passes for nine affected modules; full UI TypeScript compilation,
  affected Python lint, diagnostic skill validation and `git diff --check` pass.
  The final unused-import-only cleanup does not change tested behavior.

Current prepared format is `runengine/request-v7`, state contract is
`unifai-graph-state-v3`; Program entrypoint and element receiver remain v4/v3.
Installed images are stale. No paid provider, image rebuild or broad Temporal/
replay/Kubernetes/OpenShell gate ran in this slice. Required remote follow-ups
remain queued for the planned execution milestone.

Source manifest: `/tmp/unifai-state-contracts-source-20261104.json`, 1,667 code/test/
package files, aggregate SHA-256
`ad967862ef29d84382ad616009c1069c4179bfa4be9cd6c014df174343c2a39f`.

Next: reliability/control (aggregate budgets, admission, credential lifecycle,
stale-attempt fencing and recovery), authoritative occurrence/attempt views, then
the reusable Engineering proving workflow and unified UI. Existing node callback
`complete` events precede receiving-adapter acceptance; they must not be treated
as authoritative committed success. Observation convergence must replace/retag
that provisional signal using accepted native execution data. Full boundary/
legacy retirement and requirement-by-requirement audit remain unfinished.

## Root-wide durable work admission (2026-11-04)

Implemented the first shared execution-tree budget path, without adding a
scheduler. Opt-in `PlatformSettings.work_limits` requires durable Mongo storage;
limits are deployment policy, not user-supplied behavioral configuration. The
compiler freezes the policy/admission reference in root and child payloads.
Prepared metadata and public execution records retain the same limits, covered
by request digests. Root submission retries preserve original admitted policy.

Domain `WorkLimits`/`WorkBudget`/`WorkReservation`/`WorkUsage` and the application
`WorkBudgetRepository` port own portable contracts. `MongoWorkBudgets` atomically
reserves against one root document, shared across independent adapters/workers.
It preserves idempotent reservations and rejects changed work/owner/policy, missing
ledgers, excessive aggregate dispatch/child counts and excessive depth. Both
counters are bounded at 10,000 to bound retained reservation storage. No active
ledger TTL/refund assumes uncertain effects did not happen.

`BudgetedOperations` gates graph and backend dispatch/child creation, then delegates
native execution. Admission runs as journaled control-plane thread invocations
using private receiver settings. It does not allocate the chosen sandbox or take
environment ownership. The published cancellation callback is exempt; storage
unavailability fails closed. Exhaustion reports `WORK_LIMIT_EXCEEDED` and safe
contract diagnostics. Application/SDK failure translation now preserves machine
codes and observes the SDK rule that only infrastructure descriptors may declare
retryability. Removed an unused experimental memory budget adapter instead of
retaining a non-durable enforcement path that production composition did not use.

Evidence:

- Initial native gate: **3 passed, 8 failed in 3.93 seconds**,
  `/tmp/unifai-work-budgets-native-20261104.xml`. Successful nested paths and Mongo
  admission worked; exhaustion was incorrectly reported as application failure
  because the new adapter set `retryable=False` on contract descriptors. Corrected
  translation without weakening refusal assertions.
- Corrected native gate: **11 passed in 3.64 seconds**,
  `/tmp/unifai-work-budgets-native-corrected-20261104.xml`: real Mongo contention,
  graph → Map → graph → thread/process operations, success, aggregate dispatch/
  child exhaustion, depth refusal, zero-budget backend refusal, frozen child
  limits and idempotent root retry. Independent Mongo adapters contend on the same
  root and preserve repeated reservations after allowance exhaustion.
- Focused final gate: **127 passed in 7.51 seconds**,
  `/tmp/unifai-work-budgets-focused-final-20261104.xml`: strict portable limits,
  frozen snapshots/request identity, adapter failure/cancellation contracts,
  existing delivery fencing/recovery, graph/code controls, channel contracts,
  HTTP and architecture guards. An earlier added snapshot test omitted required
  input data (**44 passed, 1 failed**); its fixture was corrected and passes here.
- Lifecycle/configuration gate: **22 passed in 0.15 seconds**,
  `/tmp/unifai-work-budgets-lifecycle-20261104.xml`: application submission/context/
  source tests, preserved original policy on retries and refusal of nondurable
  deployment configuration.
- **1 production client journey passed in 9.58 seconds**, six unrelated cases
  deselected, `/tmp/unifai-work-budgets-production-client-20261104.xml`: actual
  TypeScript clients → TCP FastAPI → isolated Mongo → Local execution with work
  admission enabled. Completed executions expose their frozen limits. This gate
  precedes formatting/record field-order cleanup and added tests; no behavior
  exercised by the client changed afterward.
- Strict mypy passes for 14 affected modules; full UI TypeScript compilation,
  affected Python lint, diagnostic skill validation and `git diff --check` pass.

Current prepared format is `runengine/request-v8`, Program entrypoint is
`unifai-program-v5`; state and element receiver remain v3. Source manifest:
`/tmp/unifai-work-budgets-source-20261104.json`, 1,679 code/test/package files,
aggregate SHA-256
`ce88d06c96644301d19dbd1f83c2302fce4584e0a7e2772999731609a43e7ef5`.

This is requested-dispatch/child/depth admission, not provider-cost/token limits,
physical retry accounting, physical concurrency or tenant fairness. There is no
stale-attempt fence, automatic ledger revocation or admitted dynamic-plan protocol
yet. Admission clients currently have explicit per-invocation lifetimes; pooling
and contention/load acceptance remain open. Arbitrary malicious installed Python
is outside these cooperative contracts.

No paid provider, image rebuild, Temporal/replay, worker-restart or Kubernetes/
OpenShell budget gate ran. Those remain planned milestone evidence, including
deterministic dispatch ordinals under native replay and remote failure/cleanup.
Existing images are stale. Run Engine was not modified. Next reliability work
continues tenant/profile admission, credential lifecycle, stale-attempt fencing
and recovery; authoritative observation, reusable Engineering, unified UI and the
full requirement audit remain unfinished. The goal stays active.

## Owner-scoped profile admission and frozen metadata (2026-11-04)

Added domain profile grants/rules and application `ExecutionProfileAccess`, behind
the application `ProfileAccess` port. Unconfigured policy preserves the installed
catalog. Configured policy denies unmatched owners unless an explicit default
grant exists; explicit owner denial overrides that default. User/team identities
are distinct and display names do not authorize access. Ambiguous duplicate rules
and references to uninstalled profiles fail startup before client allocation.

Discovery, placement preview and compilation share that resolver. Static workflow
defaults, element/condition/operation selections, named environments and recursive
pinned/owned Program scopes cannot select forbidden profiles. The compiler passes
backend Programs only the owner's permitted target set. Runtime selection outside
it raises application `PlacementRefused` (`placement_refused`) before invocation.
Existing specification/factory/bundle/runtime paths and native environment ownership
are preserved. Explicit injected policy ports cannot fall back to unrestricted
access merely because a provider has a false truth value.

Prepared snapshots and public records freeze safe `admitted_profiles` metadata in
their request identity. Actual child records retain the child's admitted default.
Found and fixed scheduled template-to-tick handoff dropping admission metadata:
both receiving entrypoint and scheduled business admission now preserve profile
grants and shared work limits. Pre-admission cancellation still has no admitted
catalog. These are permitted capabilities, not observed per-occurrence placement.

UI resource forms, placement editor and interim Programs surface share the scoped
profile query. Team identity is forwarded explicitly; caches include actor and
owner type/id instead of reusing a global personal catalog. This is a contract
correction, not substantial expansion of the interim Programs product.

Evidence:

- **132 passed in 6.91 seconds**, `/tmp/unifai-profile-access-final-20261104.xml`:
  application profile rules, immutable snapshots, root retries, schedule admission,
  execution adapters, graph/code composition, delivery recovery, native scheduled
  entry handoff, HTTP and architecture guards. The scheduled-entry case uses an
  actual compiled template/installed Program with an explicit coordination-port
  admission double; it does not prove a real calendar tick or Temporal restart.
- **7 passed in 2.91 seconds**, `/tmp/unifai-profile-access-mongo-final-20261104.xml`:
  actual Mongo + HTTP assembly + process execution. Restricted discovery/defaults,
  preview refusal, forbidden step/condition/environment/pinned/inline scopes before
  any execution record, filtered private target payloads, safe admitted metadata
  and dynamic backend selection refusal. Earlier corresponding gate: 7 passed in
  3.38 seconds before the explicit optional-port guard.
- **6 passed in 0.12 seconds**, `/tmp/unifai-profile-access-port-20261104.xml`:
  final adapter placement and false-valued injected-policy regression. The added
  regression case follows the 132-case gate; exercised production code is unchanged.
- **1 production client journey passed in 7.75 seconds**, six unrelated cases
  deselected, `/tmp/unifai-profile-access-production-client-20261104.xml`: actual
  TypeScript clients → TCP FastAPI → isolated Mongo → Local execution with a
  privileged installed profile excluded by policy. Discovery and completed-record
  metadata contain only permitted names. This gate precedes the optional-port
  truthiness guard; the final port/Mongo gates cover that correction. No browser
  gesture/cache-switch assertion or identity-provider membership proof is claimed.
- Strict mypy passes for 13 affected modules; full UI TypeScript compilation,
  affected Python lint, diagnostic skill validation and `git diff --check` pass.

Prepared format is now `runengine/request-v9`. Program entrypoint remains v5;
state/element receiver remain v3. No old prototype format aliases were introduced.
Source manifest: `/tmp/unifai-profile-access-source-20261104.json`, 1,685 code/test/
package files; aggregate SHA-256
`aae191a888af0d898a5eebcfe2f860cf035b5b16b26ef26ed27f1676b58bbe64`.
Run Engine remains clean at `60393440efd3876cd6c81e0b013e8bf6d9167659`.

No paid provider, image build, broad Temporal/replay or Kubernetes/OpenShell gate
ran. Installed images remain stale. Policy changes govern new preparation;
immediate revocation of running grants, tenant capacity/fairness, credential
lifecycle, stale-attempt fencing, dynamic-plan admission, authoritative occurrence
views, reusable Engineering, unified UI and the final full audit remain unfinished.
Cooperative profile grants do not sandbox malicious installed Python. Continue
reliability/control work before substantial UI presentation. The goal is active.

## Execution-bound workflow credential authority (2026-11-04)

Review/verification access now require the application `ExecutionGrantAuthority`
port. Production composition injects `ExecutionGrantAccess` over the existing
execution service, with no permissive fallback. Authentication checks actual root
ownership/native liveness without redelivery or full child projection. Missing,
foreign, child-as-root, cancelled and terminal identities cannot authorize workflow
credentials. Unavailable/unknown authority returns a safe 503; invalid authority
never falls back to a cookie. Descendants may use their bound root grant.

Pre-provisioning remains possible before root admission, but such a credential
cannot operate until the real root is live. New issuance for known closed roots
is refused, including native completion before an acknowledgement or stored
projection settles. Authentication-time lifetime checks preserve explicit grant
issuance/revocation audit; `revoked=false` and future expiry alone do not establish
effective authority. Human review/inspection and owner-bound artifact authority
remain separate. No secret data was added to portable execution contracts.

The investigation found verification E2E roots running in a separate in-memory
coordinator from the API owning their grants. Reworked those workflows to publish/
start through the actual API and Mongo execution records. Reused authenticated
public API helpers, shared operation/Program definitions and private receiver
bindings; removed the unused local execution harness from happy-path cases.
The Temporal verification scenario now uses an API configured for the actual
worker host and API-owned root/child records. It was updated, not run here.
Scope-only unit/HTTP/check-adapter tests explicitly inject a narrow authority
double; actual workflow journeys do not bypass production root authority.

Evidence:

- Initial native gate: **15 passed, 7 failed in 69.60 seconds**,
  `/tmp/unifai-workflow-authority-native-20261104.xml`. Actual graph/code review
  and verification execution worked. Failures exposed old assertions using a
  never-started root or inspecting completed work through a now-inactive workflow
  credential. Kept lifetime enforcement: cross-root review tests now start a real
  second root and explicitly cancel/drain it; completed CI inspection uses the
  human session and asserts the workflow bearer is refused.
- Corrected targeted native gate: **7 passed in 26.37 seconds**, eight unrelated
  cases deselected, `/tmp/unifai-workflow-authority-native-corrected-20261104.xml`:
  expired/cancelled/superseded review lifecycle, actual cross-root refusal, and
  thread/process CI workflows with/without durable reports. GitHub is an explicit
  durable protocol peer, not live GitHub execution. The earlier 15 passing cases
  were not rerun merely for observation; source/fixture differences are retained.
- Final application/native contract gate: **34 passed in 3.43 seconds**,
  `/tmp/unifai-workflow-authority-final-20261104.xml`: missing/foreign/child/
  cancelled/unknown roots, late acknowledgements, scope/expiry/revocation, native
  completion despite a stale stored projection, actual cancellation and architecture
  guards. This includes the final safe translation of authority lookup failure;
  that error-only correction follows the native/client gates.
- **1 production Human Review client journey passed in 5.13 seconds**, six
  unrelated cases deselected, `/tmp/unifai-workflow-authority-client-20261104.xml`:
  actual TypeScript clients, signed-cookie human/reviewer identities, TCP FastAPI,
  dedicated Mongo/Redis and native Local execution. No browser gesture claim.
- Strict mypy passes for four affected application modules; affected Python lint
  passes. No UI source changed in this slice.

Source manifest: `/tmp/unifai-workflow-authority-source-20261104.json`, 1,690
code/test/package files, aggregate SHA-256
`e019ca029880419295d348b81ce2b279da0e97d5dc03d8d1ff06ee1727cb921c`.
Prepared/Program/state/element formats are unchanged (request v9, Program v5,
state/element v3). Run Engine is unchanged.

This is an authorization-time liveness condition, not an atomic commit fence on
effects already admitted before cancellation/termination. Automatic provisioning,
rotation/renewal, managed secret delivery and file/vault retirement remain open,
along with per-attempt fencing and aggregate tenant fairness. Retained artifact
access was deliberately not bound to workflow lifetime. No paid provider, image
build, broad Temporal/replay or Kubernetes/OpenShell gate ran. Matching-image,
worker-restart/replay and failure-cleanup evidence remain at their milestones.
The overall goal remains active; authoritative observation, reusable Engineering,
unified UI and the full completion audit are still required.

## Bounded workflow credential renewal (2026-11-04)

Review/verification human issuance now accepts an optional absolute renewal
horizon, bounded to 30 days and no shorter than the initial TTL. Domain
`CredentialLease` computes due/next expiry without SDK dependencies. Purpose
services implement `CredentialMaintenance` through the existing API reconciler:
current policy and real root liveness are required; pending roots do not extend,
closed/withdrawn authority revokes due grants, and unknown authority retains the
original expiry. Expired grants cannot resurrect. Renewal retains the same
credential hash, scope, human issuer and issuance audit; no secret is transported.

A shared Mongo mechanism owns indexed bounded discovery and atomic expiry CAS,
including a database-clock fence, original document/expiry and revocation checks.
Purpose authorization stays in application services. API composition starts upkeep
only after all services exist and drains it before clients close. Added shared
purpose scenarios rather than duplicate test harnesses. Bounded cursor tests prove
an unavailable authority does not starve later grants and is revisited after wrap.

Evidence:

- **76 passed in 4.10 seconds**, final focused application/native/HTTP-lifespan/
  architecture gate, `/tmp/unifai-credential-renewal-focused-final-20261104.xml`.
  Covers both purposes, fixed expiry, capped renewal, policy recheck after service
  reconstruction, missing/unknown/closed roots, expiry after a slow authority
  query, and bounded discovery fairness. Previous focused gate: 74 passed in
  4.20 seconds, before the two paging cases and a test-support type correction.
- **3 passed in 8.60 seconds**, actual Mongo/native gate,
  `/tmp/unifai-credential-renewal-native-20261104.xml`: concurrent CAS has one
  winner, revocation is preserved, excessive renewal is refused, Mongo's clock
  fences an expired lease despite stale application time, and an actual signed-
  cookie API/Mongo/Redis Human Review workflow renews beyond initial expiry while
  waiting and denies the original bearer after root completion. Production code
  is unchanged since this gate; the final gate adds test-only paging/type changes.
- **1 production Human Review client journey passed in 3.22 seconds**, six
  unrelated cases deselected, `/tmp/unifai-credential-renewal-client-20261104.xml`.
  Real TypeScript clients, TCP FastAPI, dedicated Mongo/Redis and native execution;
  this regression does not itself exercise opt-in renewal or browser gestures.
- Strict mypy passes for nine affected production modules; affected production/
  support/test Ruff checks pass. No UI source or Run Engine code changed.

Source manifest: `/tmp/unifai-credential-renewal-source-20261104.json`, 1,697
code/test/package files; aggregate SHA-256
`e40a8d908b317c132d3af8727a8145d6f7f16fbddc309918dcee1a3ddf5a0077`.
Prepared/Program/state/element formats remain request v9, Program v5 and state/
element v3. Grant DTOs gain optional safe lease metadata; matched receivers are
still required at the remote milestone. No old-format aliases were added.

This completes bounded same-token renewal, not automatic initial provisioning,
secret rotation/delivery/retirement, per-attempt fencing, aggregate tenant fairness
or guaranteed renewal under outage/backlog. Service reconstruction is tested;
actual API/worker restart renewal acceptance is not. No paid-provider, image build,
broad Temporal/replay or Kubernetes/OpenShell gate ran. Current images remain
stale. The next backend work remains credential lifecycle and control, followed
by authoritative occurrence views and the reusable Engineering workflow. Unified
UI and the full requirement audit remain required. The overall goal is active.

## Persisted workflow grant retirement (2026-11-04)

Closed-root authority was already denied at authentication, but the renewal-only
scan left fixed-expiry and not-yet-due grants persistently unrevoked. Changed the
owned repository ports and existing upkeep to visit bounded indexed pages of all
unrevoked grants. Known closed roots/current authorization withdrawal now persist
revocation before renewal becomes due. Missing pre-provisioned roots stay pending;
unknown native authority cannot extend or revoke an otherwise-valid grant.
Verification read/cancel-only scope retains its frozen-plan authority when creation
policy disappears, without acquiring create/run-check permission; it still retires
on expiry or root closure.

Expiry retirement needs no native lookup. It compares the observed expiry and
uses both application and Mongo clocks. A stale expired snapshot cannot revoke a
concurrently renewed lease; a fast application clock cannot retire a lease that
Mongo still considers live. Purpose services own authorization, while shared
`MongoCredentialLifecycle` owns bounded discovery and atomic expiry/renewal fences.
Removed the old renewal-only helper/import path rather than adding an alias.
Retired grants leave the scan and retain immutable issuance/scope/hash audit.
No additional scheduler or environment manager was introduced.

Evidence:

- **88 passed in 4.26 seconds**, `/tmp/unifai-credential-retirement-focused-20261104.xml`:
  application, real native liveness, HTTP lifespan and architecture guards. Includes
  fixed/not-yet-due grants, policy withdrawal, unknown authority, preserved pending
  roots, expiry without native access, capped renewal and bounded cursor behavior.
- **15 passed in 39.26 seconds**, `/tmp/unifai-credential-retirement-native-20261104.xml`:
  actual Mongo retirement/renewal CAS, database-clock fences, persisted fixed-grant
  retirement, a short renewing Human Review lease, and graph/backend composition
  across thread/process runners with approve/reject outcomes. Actual signed-cookie
  API/Mongo/Redis/native workflows assert persisted retirement after completion.
  The stale-snapshot test lets the old lease actually expire before attempting
  retirement, so it proves the expiry CAS independently of the clock fence.
- **1 production Human Review client journey passed in 3.28 seconds**, six unrelated
  cases deselected, `/tmp/unifai-credential-retirement-client-20261104.xml`. Actual
  TypeScript clients/TCP API/Mongo/Redis/native execution; no browser-gesture claim.
- **32 application lifecycle cases passed in 0.08 seconds**,
  `/tmp/unifai-credential-retirement-policy-final-20261104.xml`. This final small
  gate adds the fixed/renewable read-cancel policy distinction after the preceding
  gates. Production source is unchanged; no native/client gate was repeated for
  this test-only addition. The 32 cases overlap the 88-case gate.
- Strict mypy passes for six affected production modules; affected Ruff checks,
  both diagnostic skill validators and `git diff --check` pass.

Source manifest: `/tmp/unifai-credential-retirement-source-20261104.json`, 1,698
code/test/package files; aggregate SHA-256
`c78244c10ad4a1d825c12107940307fffcecdd7485b2aa23a3453aeb075a5343`.
Prepared/Program/state/element formats are unchanged. Run Engine remains unchanged
at `60393440efd3876cd6c81e0b013e8bf6d9167659`.

Metadata retirement is eventual under bounded upkeep capacity/outages; root/expiry
authentication enforcement remains independent. This is not atomic external-effect
fencing, private-file collection or complete credential lifecycle. No paid provider,
image build, broad Temporal/replay or Kubernetes/OpenShell gate ran. Matched images,
process-restart/replay and remote cleanup acceptance remain at their milestones.
The overall goal is active.

### Next credential milestone: admission, delivery and secret retirement

Automatic provisioning must cover manual, Session and scheduled/event starts through
the same admission policy. Declare and validate safe required scopes before dispatch;
freeze their admitted identity with the run. Do not infer broad authority merely
from knowing a live root ID, an installed profile or a portable credential-user tag.
In particular, copying `credential_user_id` into `issued_by` does not prove human
approval. Unattended starts need explicit authorized delegation/current-owner policy
and retained approval provenance, not a bypass of human-issuance invariants.

Provisioning needs an idempotent owner/root/purpose intent and recoverable linkage
between the actual grant and encrypted private material. Concurrent admission or
lost acknowledgement must not mint untracked usable grants or widen scope. The
immutable configuration-secret store is not a leased secret vault: published
resources may retain those references across many runs, so root cleanup must not
delete their configured provider credentials.

Investigate/use the public Run Engine executor/environment-driver extension points
for receiver-private delivery while retaining native environment ownership. Keep
root secrets out of prepared payloads, backend/profile configuration, histories and
results. Private startup settings/Secret mount references alone do not establish
automatic per-root delivery. Retirement must revoke authority, collect only
platform-managed material/bindings for that root, and preserve issuance/decision
audit. Prove uncertain admission, API/worker recovery, isolated concurrent roots
and success/failure/cancellation cleanup; test current-image remote delivery at the
planned milestone. Do not replace this with another scheduler or environment manager.

## Existing migration queue and evidence (2026-10-30)

This section retains outstanding product migration obligations and historical
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
| 4 | Deliver the requested Human Review block | A registered, versioned application program exposed as a reusable graph/UI block, with validated expected response, authorized reviewer, stable occurrence identity and typed outcomes. Reuse ordinary specifications/factories/builders for invoked effects; durable waiting uses engine coordination through application ports. Test wait/restart, rejection, expiry, cancellation, duplicates and routing. Keep tool auto-approval rules and graph pre-node interruption separate from business review. Do not add an agent orchestration framework. |
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
See [configuration and ownership](../../program-platform-development.md#openshell-policy-configuration).

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
   [the package-boundary status and plan](../../program-platform-development.md#package-boundaries).
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
   Run Engine. See [the design and acceptance cases](../../program-platform-development.md#human-review).
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

The Run Engine handoff (`integrations/archive/run-engine-conditional-routing-request.md`,
historical file no longer present)
records exact reproductions, requested contracts, compatibility/replay constraints
and acceptance tests. The [integration README](../../../integrations/README.md) separates
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
[action diagnostic skill](../../../.cursor/skills/debug-native-actions/SKILL.md) records
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
- The new [sharing diagnostic skill](../../../.cursor/skills/debug-sharing/SKILL.md) and
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
