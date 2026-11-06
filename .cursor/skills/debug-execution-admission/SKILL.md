---
name: debug-execution-admission
description: Diagnose UnifAI root submission races, uncertain acknowledgements, delivery fencing, cancellation, coordinator recovery and shared execution-tree work budgets.
---

# Diagnose root execution admission

Start with [current status](../../../docs/status.md) and [the active plan](../../../docs/plan.md).
Consult relevant [execution contracts](../../../docs/program-platform-development.md#current-architecture)
and selected [evidence](../../../docs/evidence/README.md#historical-lookup).
Do not read entire guides or archives for routine diagnosis.
This is application delivery ownership, not another scheduler or environment lease.

For automatic review/verification provisioning, inspect the secret-free
`workflow_access_approval` on the root and pending Session turn. Manual/canonical
Session requests must carry explicit scopes and authenticated human approval;
portable credential-user tags are not authority. The existing submission claim
owns provisioning before native dispatch. Recover its original approval and
stable issuance intent after uncertainty; do not mint from a new human identity
or widen scopes on retry. See
[admitted capability contracts](../../../docs/program-platform-development.md#admitted-workflow-capabilities).
`support/managed_access.py` starts with no grants/token files; native HTTP and
TypeScript-client cases exercise both entry paths. Bounded scheduled consent now
uses the same provisioning port; see [schedule diagnostics](../debug-program-schedules/SKILL.md).
Generic authenticated event starts now share this path; see
[event diagnostics](../debug-program-events/SKILL.md). Provider adapters, remaining
recovery combinations and isolated remote delivery remain separate acceptance.
For partial multi-purpose issuance, use
`integration/mongo/test_workflow_admission.py`: it injects failures only at the
purpose port while preserving actual encrypted reservations and purpose stores.
An unconfirmed root must retain its original approval/material and may not dispatch
until every requested purpose is confirmed. Cancellation precedes reprovisioning;
an access refusal caused by concurrent root cancellation remains cancelled.
Use canonical JSON identity for retries: Python equality equates `True`, `1` and
`1.0`, allowing changed requests to adopt the wrong invocation.
`deployment/test_managed_workflow_recovery.py` exercises both purposes in native
thread/process operations, duplicate concurrent submissions and a running-root
API restart. Its borrowed listening socket preserves the endpoint while the
separate worker stays live; rebinding receivers to a new URL would test a different
recovery scenario. Each root's cleanup must leave the other's live material intact.

- Start from the public execution record and original pinned location/prepared
  snapshot. Clients choose a public idempotency key; the service chooses a separate
  private native ID. Never accept arbitrary `RUN_ALREADY_EXISTS` as ownership.
- `prepared -> starting` atomically obtains a private submission token and expiry.
  A live starting owner must not be redelivered by another API/reconciler. The
  original I/O is bounded by `UNIFAI_SUBMISSION_TIMEOUT_SECONDS` (default 30 seconds);
  a crashed owner's claim matures five seconds later. Claim metadata stays outside
  public records, program payloads and worker configuration.
- A finishing attempt must match its token. An expired owner can receive a late
  collision/refusal after a recovery owner already started the same stored request.
  That old result must not overwrite the newer accepted record or release its claim.
  Preserve frozen input/profile/location and private native ID during recovery.
- Keep uncertain delivery distinct from rejected contracts. Genuine first-start
  collisions remain refused; accepted work that becomes unobservable is unknown
  and must not be resubmitted merely because observation vanished.
- Persist `cancel_requested` before trying native cancellation, after owner/location
  admission. A cancellation arriving before native acceptance must survive API
  restart and stale record updates. The submission owner/reconciler applies it once
  the native run becomes observable. Requested cancellation is not confirmed cleanup.
- Check both storage implementations with the shared application-port contract in
  `tests/support/execution_claims.py`. Mongo claims/finishes must be atomic and
  token-fenced across API workers; process-local locks alone are insufficient.

Use `integration/run_engine/test_recovery.py` to force interleavings with a real
Local host: delay before native acceptance, observe from another service, expire
the owner before its late response, cancel before acceptance, and enforce the
submission deadline. The existing foreign-collision assertion must remain intact.
Then run real Mongo and the deployed agent-session Temporal scenario:

```sh
.venv/bin/python -m pytest multi-agent/tests/adapters/test_execution_claims.py multi-agent/tests/integration/run_engine/test_recovery.py -q
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 UNIFAI_TEST_TEMPORAL_ENDPOINT=127.0.0.1:7234 .venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_repositories.py multi-agent/tests/integration/deployment/test_agent_sessions.py -q
```

Use only dedicated test services. Do not mask a race with arbitrary sleeps,
larger timeouts, broad exception suppression or relaxed collision ownership.
After a failed native gate, inspect its exact owned workflow through public APIs;
do not delete unrelated histories, read private SDK journals or claim a partial
gate passed. Current-source full regression and required remote recovery evidence
are separate acceptance gates.

## Shared work budgets

Read [root-wide work admission](../../../docs/program-platform-development.md#root-wide-work-admission)
when a Program fails with `WORK_LIMIT_EXCEEDED`. `UNIFAI_WORK_LIMITS` is opt-in
deployment policy, requires Mongo and freezes into prepared requests/records.
Check the original admitted limits rather than current deployment defaults.

`BudgetedOperations` reserves before native dispatch/child creation for both graph
and backend Programs. Control-plane admission uses journaled thread invocations
and receiver-private Mongo settings; it must not launch the selected sandbox.
`MongoWorkBudgets` conditionally updates counters/reservation hashes in one root
document. Repeated identical claims spend once; changed fingerprints, owners or
policies conflict. Missing storage/ledgers must fail closed, never reset counters.
Do not refund uncertain downstream work or expire/delete active reservations.

The allowance counts requested dispatches (including graph framework calls) and
all tree children, not physical retries, provider tokens/cost or capacity. Published
cancellation callbacks are exempt so exhaustion cannot prevent that cleanup path.
Do not describe budgeting as stale-attempt fencing or tenant fairness. Connection
pooling/load behavior, native replay/restart and current-image remote validation
remain separate acceptance work.

Use shared `support/work_budgets.py`, Mongo `test_work_budgets.py`, native
`run_engine/test_work_budgets.py` and adapter refusal/cancellation tests. The native
scenario spans graph → Map → graph → thread/process operation under one ledger.
The production Programs client verifies admitted limits. For error translation,
native `FailureDescriptor.retryable` is allowed only on infrastructure failures;
setting even `False` on contract failures replaces the intended refusal with a
validation error. Preserve classification and machine codes across application
ports without including submitted values in diagnostics.
