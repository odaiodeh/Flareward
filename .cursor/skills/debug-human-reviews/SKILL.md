---
name: debug-human-reviews
description: Diagnose Lumora business Human Review authorization, immutable decisions, engine wakeups, restart recovery and reviewer UI behavior. Tool approval tickets are a separate mechanism.
---

# Diagnose Human Review

Read the [current contracts](../../../docs/program-platform-development.md#human-review)
and selected [implementation evidence](../../../docs/evidence/README.md#historical-lookup).
Start/resume with [current status](../../../docs/status.md) and [the active plan](../../../docs/plan.md);
read the relevant sections, not whole reference guides or archives.
Use the existing `human_review@1` program and ordinary registered review operations;
do not add a dedicated review scheduler, worker or graph step kind.

Trace `ReviewService` through its application-owned repository/execution ports.
Mongo atomically accepts the human response and notification intent. `ExecutionReviews`
binds the actual accepted root/child and delegates native status/messages to the
execution service. The coordinator invokes open/inspect effects and waits through
`ProgramRuntime.receive`; message data is never an approval.

For lost issuance responses, use the existing human endpoint with `Idempotency-Key`
and configured `LUMORA_RECOVERABLE_CREDENTIAL_ISSUANCE`/encryption key. The same
owner/purpose/key/request/human recovers one original token; changed intent conflicts,
and revoked/expired identities cannot revive. Inspect safe metadata/tombstones,
never ciphertext/token values. The API upkeep retires encrypted material separately
from grant audit. Shared `HumanPrincipal` rejects bearer-plus-cookie grant management.

For managed trusted-filesystem delivery, inspect the absolute private
`LUMORA_WORKFLOW_CREDENTIAL_DIRECTORY` binding and safe reservation `delivery_key`.
The API needs recoverable issuance and its vault key; the receiver needs only the
directory/source binding. Normal factories resolve through `WorkflowCredentialSource`;
a configured source failure must not fall back to an operator file. Inspect
the receiver failure category: source unavailability must be private, retryable
infrastructure, not a generic application error. Inspect
`cleanup_pending` independently from `retired`: the durable outbox survives
ciphertext removal, and acknowledgement follows file collection. Preserve
token-free fences against delayed writers. Unknown destinations remain pending;
restore the correct adapter rather than deleting another directory. See
[delivery contracts](../../../docs/program-platform-development.md#managed-private-workflow-delivery).
Manual/canonical Session requests can provision this material automatically using
explicit `workflow_access` and authenticated human approval. Inspect the frozen
root/Session `workflow_access_approval` and original request digest; portable user
tags cannot supply approval. Use
[admission diagnostics](../debug-execution-admission/SKILL.md) for pending provisioning.
Scheduled consent has focused native worker-restart/replay coverage through the
same review operations; see [schedule diagnostics](../debug-program-schedules/SKILL.md).
Generic authenticated event starts now use private source consent and canonical
root admission; see [event diagnostics](../debug-program-events/SKILL.md). Provider
adapters, rotation, broader recovery and isolated remote delivery remain open.

- A human's ownership or selected team does not imply reviewer assignment. The
  inbox is the authenticated user's assigned occurrences across owners. Assignment,
  policy, exact subject, schema and deadline are frozen when a review opens.
- The shared execution view reads `GET /api/executions/{root}/reviews` using the
  human owner's scope. Trace `ReviewService.for_execution` and the repository port,
  not a browser-side scan of inbox pages. Mongo owner type/id/root projections must
  agree with the stored record; its cursor belongs to that exact owner/root query.
  Shared query contracts run against both memory and Mongo. The endpoint rejects
  bearer-plus-cookie requests and does not add reviewer authority.
- Inbox and execution views share `components/reviews/ReviewDetail` and the generic
  schema fields. There is no separate scalar-only review renderer. Backend response
  schemas and assignment remain authoritative; pending owners see no decision form
  unless assigned. Reviewers inspecting another owner's root still need owner access
  to the full execution; assignment alone permits the exact review detail.
- Workflow access is purpose-separated and scoped to root/policy/actions. It can
  open/read/close admitted occurrences, never answer as a reviewer. A bearer header
  must not fall back to a cookie, even if that cookie belongs to the reviewer.
- `ReviewAccessService` requires `ExecutionGrantAuthority`. Production uses the
  read-only application record/native-status ports to check actual owned root
  liveness without recovery or child projection. Pre-provisioning is permitted, but a missing/foreign/child/
  cancelled/terminal root cannot authenticate. Unknown authority is a safe 503.
  After completion inspect with the human session; an unexpired/unrevoked grant
  is not proof of current authority. This is not an atomic external-effect fence
  or automatic rotation/unattended delegation. Keep those milestones open.
- Optional `renewable_for_seconds` enables bounded same-token renewal through the
  existing API upkeep loop. Check `renewal.renewable_until`, current policy, real
  root liveness and upkeep/page capacity. Unknown authority cannot extend expiry;
  expired grants cannot resurrect. Mongo fences renewal with its own clock and
  atomic expiry/revocation checks. Renewal does not rotate credentials; managed
  delivery/collection has its own lifecycle. Reuse `support/credential_renewals.py` and the application,
  Mongo and native review renewal cases; do not add a second maintenance scheduler.
- Upkeep visits all unrevoked workflow grants, including fixed-expiry grants and
  leases not yet due for renewal. Closed roots/current policy withdrawal persist
  revocation; a missing pre-provisioned root stays pending. Expiry retirement
  needs no native lookup, but must compare the observed expiry and Mongo's clock
  so a stale snapshot cannot revoke a renewed lease. Use the real Mongo repository
  when checking retirement; `data` retains issuance audit while the stored revoked
  flag is overlaid on read. Bounded metadata retirement is eventual, whereas
  authentication independently denies terminal roots. Explicit operator files
  remain operator-owned; only managed slots enter the cleanup outbox.
- Compare occurrence ID, exact execution/root, revision and stable response key.
  Identical retries return the original response after notification acknowledgement.
  A conflict, expired/cancelled/superseded review or wrong scope cannot become an
  approval. Do not edit persisted decisions to recover delivery.
- Inspect `delivery_pending` independently from `status=decided`. Lost delivery or
  acknowledgement leaves the accepted decision intact. The next reconciler or
  bounded receive timeout invokes authoritative inspection. A check limit is a
  pending result, not approval; the review deadline is never reset by wakeups.
- Native Temporal sends use acknowledged Updates. With the workflow worker stopped,
  acknowledgement may wait until its bounded RPC timeout. API shutdown cancels and
  drains its own reconciler; committed intents survive. Do not hide a shutdown hang
  by enlarging process timeouts or bypassing engine message admission.
- Local waiting is in-memory; Temporal restart/replay evidence is separate. Review
  waiting holds no element invocation, but retained parent environments still follow
  Run Engine ownership. Verify actual remote cleanup before claiming that matrix.
- Worker endpoint and private credential-directory bindings are operator inputs.
  Preserve mode-0600 files, purpose/root scope and HTTPS requirements. Do not put raw
  credentials into authored definitions, results, screenshots or diagnostic output.

Run focused application/architecture cases first, then actual adapters:

```sh
.venv/bin/python -m pytest platform/tests/application/test_reviews.py platform/tests/application/test_review_program.py platform/tests/architecture -q
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 LUMORA_TEST_TEMPORAL_ENDPOINT=127.0.0.1:7234 .venv/bin/python -m pytest platform/tests/integration/reviews/test_workflow.py platform/tests/integration/temporal/test_reviews.py -q
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest platform/tests/integration/ui/test_editor_client.py -k human_review --ui-clients -q
```

The native fixtures use real signed-cookie owner/reviewer users, separate API and
worker processes and dedicated Mongo/Redis/Temporal. Shared program data and port
doubles live in `support/review_programs.py` and `support/reviews.py`; transport
ownership lives in `support/review_api.py`. The Temporal case stops a worker during
an observed native timer, accepts a decision, restarts the API/worker, and replays
both histories. The unique-database finalizer cleans accepted test-owned native
identities after worker contexts exit. Do not terminate unrelated workflows.

For an actual App check, build `ui/tests/build-workspace-browser.mjs` as described
in [session UI diagnostics](../debug-session-ui/SKILL.md), then use a fresh directory:

```sh
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 PYTHONPATH=platform/src:platform/tests .venv/bin/python -m support.review_browser --assets /tmp/lumora-review-browser-assets --directory /tmp/lumora-review-browser-run
```

Open the printed test login URL, select the pending occurrence, inspect its subject,
enter schema-conforming feedback and approve/reject. Check the actual decision,
reload and reselect it, and require the runner's completed workflow result. A UI
click or saved response alone does not prove continuation. The fixture sets a
signed assigned-reviewer cookie, not production OAuth; MAS routes are unstubbed.
The second printed login opens the owner execution workbench. Inspect the pending
root and actual child, confirm the unassigned owner has no decision buttons, then
use the reviewer login to decide. Return through the owner login and verify both
execution completion and the persisted exact decision. Cookies share the loopback
host across ports: reenter each fixture's own login before resuming another fixture.
Close the tab before Ctrl-C and confirm the unique database/sessions are removed.

For uncertain UI delivery, preserve the exact submission key/data/decision on retry.
Background snapshots cannot regress a newer revision; selection and workspace
changes abort old requests. Response fields use the shared schema renderer with
JSON fallback for unsupported shapes; server validation remains authoritative.
The inbox and execution workbench share the detail/decision component. Full visual
nested-program authoring and broader occurrence inspection remain unfinished.
