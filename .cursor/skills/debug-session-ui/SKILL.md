---
name: debug-session-ui
description: Diagnose UnifAI session creation, chat state, turn-specific streaming, cancellation, and team scope across the existing UI and native FastAPI boundary.
---

# Diagnose native UI sessions

Start with the failing production client in `ui/client/src/api/sessions.ts` and
its HTTP route. The UI still uses dotted session routes. Native execution
`/executions/{id}/stream` is SSE; the compatibility session subscription is
NDJSON. Inspect the actual endpoint before changing a parser.

Keep the identity chain explicit: a session holds multiple execution turns, each
with its own root execution ID. A program-call child belongs to that execution;
it does not create a new chat session. `BlueprintSessionService` authorizes and
publishes a protected snapshot before creating a native session. Its unique
program draft identity prevents concurrent session creation from overwriting a
shared publication draft. Creation allocates no engine run. Existing sessions
retain their revision after blueprint/resource edits or blueprint deletion.

For personal/team failures, trace `SessionAuthenticator`, selected `teamId`,
`ProgramSessionService`, and `SessionQueryService`. The authenticated human
remains the credential user while the owner can be a verified team. Do not fix
403s by trusting request-authored `userId`, weakening ownership, or treating a
private draft as public shared-chat data. Shared-chat access requires its own
application policy; a sharing-metadata toggle does not supply that policy.

For resource placement, trace `ExecutionProfileField`, `lib/resource-editor.ts`,
`useWorkspaceData.saveElement` and the native resource service. Nodes, conditions
and operations select a reusable profile. The authenticated catalog endpoint exposes
approved names/default, never raw backend configuration. Preserve `execution`
beside `cfg_dict`, the loaded version, and selected team scope. Omission preserves
the preference; an explicit null profile clears it. An unavailable saved name
must stay visible, including while discovery fails. The generic schema form merges
only the editable resource name with element config; merging the whole resource
schema would leak execution/identity metadata into element configuration.
Workflow authoring uses `WorkflowPlacementEditor` in the save dialog. Trace
`workflowPlacement`/`applyWorkflowPlacement`, blueprint reconstruction, resolver and
program importer. Preserve workflow defaults/environments and independent node/
condition selections. Null/omitted step placement inherits the element preference;
`{}` explicitly uses workflow/platform defaults. Removing a condition must remove
its placement too. Named environments can use only profiles with a retained driver;
the outbound adapter projects that capability without exposing backend settings.
Blueprint session creation inherits the saved default into its protected revision.
The TypeScript suites and Mongo chat cases check round trips, version conflicts,
publication pins and later turns. For authoritative placement, follow
`BlueprintPlacementService`, its application-owned preview port, and
`ProgramCompiler.preview`. It shares selection/capability and construction-closure
validation without producing a portable execution bundle. Never add a flag that
allows literal secrets into execution bundles merely to inspect placement.
`ElementBundleResolver.validate` returns no bundle; `resolve` retains its secret
guard. Mongo preview tests assert unchanged records and safe response fields.
The UI hides previous results as soon as the draft changes, uses abort signals,
and keeps authored configuration out of query keys.

### Actual workspace browser check

The maintained fixture renders the production App and provider tree. It uses the
production signed-cookie authenticator against real Mongo/Redis, with an owned
synthetic membership service, unique teams and a personal workspace. External
identity, terms/settings and analytics are fixtures; MAS routes are not stubbed.
The superseded isolated blueprint-dialog harness and mode are removed.

Build from `ui/`:

```sh
NODE_ENV=production node tests/build-workspace-browser.mjs /tmp/unifai-workspace-browser
```

Start from the repository root with the existing own test services:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
PYTHONPATH=multi-agent/tests:multi-agent/lib:multi-agent/adapters:multi-agent \
.venv/bin/python -m support.placement_browser \
  --assets /tmp/unifai-workspace-browser --log /tmp/unifai-workspace-browser-api.log
```

Keep the live handle and open the printed login URL. It opens `/inventory`;
use `/programs` for canonical composition, placement and saved revision inspection.
The isolated profile has a preview-only placeholder image; do not execute it.
Observe real server responses instead of injecting application state. This does
not certify OAuth, remote isolation or complete product acceptance.

Close the test tab, stop the owned runner with Ctrl-C once and poll that handle.
Confirm API/identity shutdown, unique database and cookie/lease retirement. Leave
shared services and unrelated databases intact. Never deploy the fixture ASGI app.

Check personal and team node/condition profile save/reload, transitive reference
selection, resource versions, closing a pending lease and switching teams. A team
change must clear the previous inventory/editor and scoped notification/sharing
state. `WorkspaceContent` owns that provider lifetime; `AgenticLayout` still gates
mounting its resource provider until team selection is ready.

The fixture delays actual mock-agent schema/list and edit-acquire requests by two
seconds. Expand Conditions and Agents first, then select Mock Agent Node followed
immediately by Router Boolean. Verify the condition card/form remains selected
after the delayed response could arrive. `useLatestRequest` owns one AbortController
per selection channel, cancels replacements/unmounts, and guards catch/finally state
updates. Resource pagination forwards the same signal to every page. Schema JSON
may omit `required`; treat it as an empty list instead of failing the whole editor.

Native resource badges retain the dotted `resource.validate` POST contract and
delegate to the existing inspection service. Body `userId` cannot select credentials.
Native action discovery/execution now uses application-owned async dispatch. In
the OpenAI LLM form, invoke model discovery, select `fixture-model-mini`, invoke
reasoning discovery and select `minimal`. The fixture seeds synthetic capabilities
in its unique Mongo database; these two requests must succeed without a model call.
Use [action diagnostics](../debug-native-actions/SKILL.md) for registration,
identity, provider ownership and test coverage. Native notification list/details/
decline/cancel now use actual invitations; see
[sharing diagnostics](../debug-sharing/SKILL.md). The full App fixture seeds separate
personal/Alpha/Beta invitations and delays Alpha notification responses. Verify
decline persists after reload and a rapid team switch retains only the new team's
state. Create/accept/team-copy routes remain under migration; do not hide their
missing behavior with empty fixture responses. The fixture also does not run the
separate administrative configuration service.

The browser identity lasts 30 minutes, then normal authentication expires. Close
the tab before stopping the owned runner. Both API and membership processes must
shut down; verify the unique browser database, synthetic identity and exact team
lease keys are gone. Do not flush either shared store. The runner cleans only its
unique data; test services remain running. Save proof of the persisted profile.

### Session streaming and decisions

`useSessionStream.executionReference` records the session and exact observed root
from accepted submission/reconnection. Cancellation/view replacement clears it;
late status/submission responses remain generation-guarded. The session view links
that reference to the shared `/executions/:id` workbench only when it matches the
selected session. Do not derive the link from a stale previous-turn status object
or expose owner-only inspection as part of a public shared-chat promise. This link
is implemented; full Session browser/lifetime acceptance remains required.

For wrong-turn or missing stream data, compare the submission's `executionId`,
the pinned subscription ID, event cursors, and the current session record.
Interactions are stored by execution root, not by session ID. Reject an explicit
stale subscription instead of following the next turn. Finish an already-open
stream using its pinned execution, even if the session has since moved on.
Unknown stream count/timing fields stay null; do not invent monitoring data.

Approval cards capture both the root execution ID and request ID. Native decision
and rule-patch routes require `executionId` and reject a stale turn; never recover
a missing ID by reading whichever execution is current now. Child events retain
their source `execution_id` and also carry `root_execution_id` for UI actions.
Handle node-less `approval_resolved` events before requiring a node; status updates
must match both IDs. The pure UI helper and actual client suites exercise repeated
request IDs across turns.

Session rule changes persist in session metadata through an optimistic command,
then publish a revision-fenced live copy. Publication failure can mean the session
default was saved while live synchronization is pending; preserve that distinction
in errors. The existing session reconciler retries publication, including after
service restart. Redis stores its fence inside the same cached JSON value; keep
its adapter-only marker out of public policy responses and preserve empty arrays.
An execution-only full replacement preserves the fence, so same-version session
reconciliation does not overwrite it. A newer session rule command takes effect.
Current pending tickets require their own human decision; a rule affects later
matching requests. Keep rule-save and current-decision failures separate in UI
notifications. Whole metadata edits can clear defaults between executions.

Do not assume a terminal execution has already been projected into the session:
turn admission refreshes an apparently busy record before rejecting it. Reuse
optimistic session versions so that this observation cannot admit two turns.
Concurrent retries with the same identity and input recover the winning admission
without staging messages again. Different inputs/scopes with that identity remain
conflicts; this is not a retry of agent/tool effects.

`readSessionEvents` owns UTF-8 decoding, NDJSON framing, final unterminated lines,
and reader cancellation/release. The React hook owns subscription lifetime:
pass the actual abort signal to fetch and prevent an old subscription from
changing a replacement's state. Client disconnection only closes observation;
backend cancellation is a separate application operation. Keep observing an
accepted cancellation until a terminal result arrives. During browser testing,
also check pending submission/completion callbacks across session and workspace
switches; transport tests alone do not prove those UI lifetimes.

Use [the platform test workflow](../run-platform-tests/SKILL.md). Relevant evidence:

- `integration/mongo/test_chat_sessions.py`: snapshot isolation, multiple turns,
  user/team ownership, deleted authoring data, filtering and pagination.
- `integration/mongo/test_agent_sessions.py`: shared two-agent/tool/dependency
  scenario through both canonical and UI routes on thread/process workers.
- `integration/redis/test_interactions.py`: pinned stream replay, human decisions,
  stale subscriptions/decisions, child root identity, persistent rules, cache
  recovery, version fences and cancellation with actual workers.
- `application/test_session_approval_rules.py`: port-only concurrent edits,
  persisted-but-unsynchronized recovery after restart, denied/stale writes and
  observation/version stability.
- `integration/deployment/test_session_approvals.py`: real signed-cookie HTTP,
  Mongo/Redis and a separately running Temporal worker on thread/process targets.
  The API restarts during a pending approval and reconstructs a deliberately lost
  live-rule cache before the decision and next turn. Native histories replay.
- `integration/ui/test_editor_client.py --ui-clients`: production TypeScript
  exports against real HTTP. The sessions case needs isolated Mongo and Redis;
  other API cases need Mongo, and the pure NDJSON/data contracts need no services.
- `support/session_store_contracts.py`: identical query/deletion contracts for
  memory and Mongo adapters. Deletion checks the observed version and refuses
  active sessions; do not orphan work by deleting its session record first.

The Node runner's fetch shim changes only the browser-relative base URL and
still performs real HTTP. Fixtures own unique databases, API processes and Redis
execution keys; clean those keys after server shutdown rather than flushing a
shared Redis database. No paid model calls are needed for these scenarios.
Report API/client, worker, browser and deployment evidence separately. Native rule
and turn-binding regressions do not establish full shared-chat authorization,
authenticated browser flows or React callback ownership across workspace changes.

If the bundled pnpm wrapper attempts a noninteractive reinstall of an already
installed UI dependency tree, do not purge it just to run verification. The actual
checks can use `node tests/run-api-contracts.mjs contracts`,
`node node_modules/typescript/bin/tsc --noEmit`, and
`NODE_ENV=production node node_modules/vite/bin/vite.js build` in `ui/`.
