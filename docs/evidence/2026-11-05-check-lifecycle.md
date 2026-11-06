# Owned verifier-job retirement

Recorded 2026-11-05. Connects owned verifier jobs to plan/root lifetime through the
existing execution cancellation API. Pool cancellation is bounded draining, not
prompt invocation preemption. Isolated/live/Temporal acceptance remains open.

## State and responsibilities

- `RegisteredCheckRunner.lifecycle` explicitly selects owned jobs. Their portable
  `job_state` is active/retiring/closed; borrowed/unmanaged providers have null state.
  The last provider observation and business verification verdict remain distinct.
- `CheckJobMaintenance` uses existing application repository, verification and root
  authority ports. Bootstrap adds it to the existing reconciliation loop. There is
  no new scheduler, worker, environment manager or Run Engine dependency in the
  application/domain layer.
- Plan cancellation/expiry, recorded check evidence, or an authoritatively closed
  owning root initiates retirement. A pending root-owned plan is cancelled through
  VerificationService when that root closes. Unknown authority cannot cancel work.
- Retirement commits before provider cancellation. A ready intent can close by CAS
  before dispatch wins; in-flight/uncertain jobs retain retirement until their exact
  execution is terminal. Missing or changed bindings remain pending rather than
  inventing closure. Start/observation/report paths fence retirement against late
  acknowledgements or new attestations.
- Matching committed receipts recover a lost check acknowledgement. Matching uses
  exact check/verifier/run/candidate/configuration/report identities; it does not
  submit another attestation. Completed and partial plans retain immutable evidence.
- Mongo has indexed job-state projections validated against portable data. Memory
  and Mongo share query contracts for pagination, closed/unmanaged exclusion and
  update behavior. Current projection fields are required; no legacy reader was added.
- Maintenance pages are bounded, each pass has a five-second budget, and its cursor
  advances past unavailable items. State survives controller reconstruction; API
  process restart resets only the scan cursor, not retirement intent.
- Program checks cancel using ExecutionService under the pinned verifier owner.
  `stop` verifies owner/reference/digest/input before cancellation and observes
  terminal state afterward. A cancel acknowledgement alone is insufficient.

## Verification

Final shared gate:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture multi-agent/tests/adapters/test_verification_settings.py \
  multi-agent/tests/adapters/test_python_function_checks.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**773 passed in 7.28s**, no skips or reported warnings. New application cases cover
plan cancellation/expiry, root closure versus unknown authority, late provider
acknowledgement, ready-versus-dispatch CAS, missing/changed cleanup binding, paging,
controller reconstruction, accepted receipt retention and exact-receipt recovery
for both completed and still-partial plans. Program-control cases distinguish
cancel acknowledgement from terminal observation and reject foreign executions.

Coherent native/regression gate:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/verification/test_program_checks.py \
  multi-agent/tests/integration/mongo/test_check_jobs.py \
  multi-agent/tests/integration/verification/test_github_checks.py \
  multi-agent/tests/integration/verification/test_check_reports.py \
  multi-agent/tests/integration/verification/test_check_restart.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**44 passed in 132.10s**, no skips or reported warnings. Actual signed-session HTTP,
Mongo/Redis and thread/process workers exercise prior passing/failing verifier
behavior, completed-state API reconstruction and report survival. Four cancellation
cases observe a real checker child before cancelling either its plan or its actual
owning waiting workflow. Cleanup proceeds without verification refresh calls.
They require job closed, no new evidence, cancelled plan, terminal cancelled
execution with cancellation requested, removed workspace and nonexistent child PID.
The root cases issue a scoped test grant; they do not add automatic-issuance proof.

Mongo cases run the shared pending-query contract and reject divergent projections.
Existing GitHub/report/restart cases remain green. Native setup now reuses
`support.program_check_api.ProgramCheckAPI`, which owns identities/publication
across separate real API lifetimes instead of duplicating infrastructure setup.

The native gate preceded a final refinement that also recovers an exact committed
receipt while other plan checks remain pending. The final 773-case gate includes
both completed/partial lost-acknowledgement races after that refinement. The native
gate was not repeated for this application-only branch; its unchanged one-check,
cancellation, storage and provider paths retain the stated earlier evidence scope.

Strict mypy passes seven changed production modules with the existing MYPYPATH and
`--strict --follow-imports=silent`. Focused fourteen-file Ruff check/format, diff
checks and updated verification-skill validation pass. No UI code or remote image
changed; browser/paid-provider/broad remote gates were not repeated.

## Diagnosed limits and failures

Initial native thread cases did not close within a 15-second observation window
while the actual checker had a 30-second operation deadline. Safe diagnostics showed
job retiring, execution running and cancellation already requested. Inspection of
the committed ThreadExecutor/ProcessExecutor and `await_completion` confirmed that
pool invocations drain before cancellation propagates; no silent controller failure
was established. The final controlled checker uses a six-second operation bound;
its terminal cancellation and physical child/workspace cleanup are verified after
bounded draining. This does not establish rapid interruption of long-running work.

The [engine request](../../integrations/run-engine-invocation-cancellation-request.md)
records exact inspected semantics and cooperative-cancellation acceptance scenarios.
No companion project was edited. API-level killing of pool workers or another
environment manager was not introduced as a workaround.

The first root-case fixture incorrectly asserted 200 instead of grant creation's
201. Corrected the assertion and removed the credential response from failure
diagnostics. An application race test then deliberately reproduced closed job
metadata losing an already-committed receipt acknowledgement; exact receipt recovery
fixed it. Adding the partial-plan variant briefly lacked its pytest import; the
final shared gate follows that correction.

Owned test APIs assert complete shutdown through their maintained context manager;
unique databases/sessions and any exact controlled child PID on failure use scoped
fixture cleanup. Shared services remain running. A read-only Docker health probe
succeeded (server 29.1.3); no containers were restarted or images rebuilt.

## Remaining acceptance

Next is one current-source isolated checker image/profile and bounded live coding
through Engineering. Prompt receiver interruption, in-flight Temporal recovery,
remote physical cleanup and cross-root budgets/capacity remain required. The
controller does not claim atomic fencing of effects already in flight. Missing
uncertain jobs and removed bindings remain conservative pending states; restoring
the admitted binding or explicit reconciliation is still necessary.

No live model calls or hostile-code/complete product acceptance are represented by
this checkpoint. The full target and deferred requirements remain active.

## Source identity

[Focused manifest](2026-11-05-check-lifecycle-source.json) records changed contracts,
services, repository, composition and shared/native test fixtures, plus the inspected
companion baseline. This is not a full dependency/image manifest.
Source aggregate SHA-256: `8b9261d2f06c1ec03157b2b272527b7e71e38cd864af114e707909f3648a7f23`.
