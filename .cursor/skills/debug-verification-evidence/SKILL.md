---
name: debug-verification-evidence
description: Diagnose Lumora verification admission, trusted CI dispatch, uncertain acknowledgements, candidate provenance, scoped authority and API/worker recovery.
---

# Diagnose verification evidence

Use [implemented contracts](../../../docs/program-platform-development.md#verification-plans-and-trusted-evidence-admission)
and [the active plan](../../../docs/plan.md). Start/resume with
[current status](../../../docs/status.md); retrieve selected
[evidence](../../../docs/evidence/README.md#historical-lookup) and guide sections as
needed rather than reading whole guides/archives. External
evidence admission and registered request/inspect/cancel operations compose with
`await_verification@1`. Trusted GitHub dispatch/reconciliation now uses
`start_verification_check`, `refresh_verification_check` and `await_check_run@1`.
Required report provenance, audited attachment of known runs and basic owner-bound
report previews are implemented; broader UI acceptance remains unfinished. Deterministic GitHub wire
fixtures do not prove live GitHub execution.

For an operator-pinned verifier Program, trace `ProgramCheckRunner` and
`LUMORA_PROGRAM_CHECKS` through normal platform composition. The configured
Program owner/reference/digest is trusted authority; an arbitrary candidate
Program returning `passed` is not. Inputs use `CheckProgramInput`; outputs use
`CheckProgramResult` with the exact subject fingerprint. Check the actual verifier
execution identity, owner, inputs and digest before diagnosing report collection.
Its ID is stable for a check intent. Reconciliation observes that execution and
never repeats a start because it is missing. Do not turn a source/definition pin
into a claim about hostile-code isolation or runtime image provenance.

For `engineering@4`, compare its selected completion's frozen `requirements` with
the actual plan, including verifier IDs and report flags. The same policy ID is
insufficient after operator configuration changes. Candidate schemas are checked
before verification effects; unknown completion names dispatch no producer. See
[the contract checkpoint](../../../docs/evidence/2026-11-08-completion-contracts.md).

Use `application/test_program_checks.py`, `adapters/test_verification_settings.py`
and `integration/verification/test_program_checks.py`. The latter uses actual
signed sessions, Mongo/Redis and thread/process operation workers with a controlled
JSON-value and controlled Python checkers, including report retrieval after
completed-state API restart. Full Engineering integration uses the same production
runner in `integration/coding/test_feature_workflow.py` and the maintained browser
fixture. These are not live-model, in-flight Temporal recovery or remote acceptance.
Verifier jobs use their configured owner's independent root and private bindings;
do not grant a candidate owner access to that full execution to fix a UI 403.
For owned-job cleanup, trace `CheckJobMaintenance`, indexed `pending_jobs` and
`CheckJobControl.stop`. `job_state` is distinct from provider/evidence status:
retirement commits before cancellation, and closure requires the exact job terminal.
Unmanaged providers are excluded. Unknown/missing jobs or changed bindings remain
pending; never mark them closed to empty a queue. Receipt recovery must match the
original check/verifier/run/candidate/configuration/reports, including partial plans.
Use `application/test_check_job_maintenance.py`, the shared memory/Mongo query
contract in `support/check_jobs.py`, Mongo `test_check_jobs.py` and native Program
checks. Cross-root capacity and full remote/recovery acceptance remain open.
For the optional Python checker and credential-free inline candidate transport,
read [the focused procedure](references/python-checks.md). The operator enable flag
and a native process test do not establish a hostile-code sandbox or live acceptance.

Recoverable human issuance is opt-in through `Idempotency-Key` and configured
`LUMORA_RECOVERABLE_CREDENTIAL_ISSUANCE`/encryption key. Retries preserve original
scope/issuer/time/material and observe current renewal, never resurrect revocation.
The actual API restart case is pre-provisioning, not a running-root restart proof.
Grant issuance/list/revoke require shared `HumanPrincipal`: even a valid human
cookie cannot turn a supplied workflow bearer into human authority. Inspect safe
reservation metadata and ciphertext absence after retirement, never private values.
Managed trusted-filesystem delivery uses `LUMORA_WORKFLOW_CREDENTIAL_DIRECTORY`
and normal `WorkflowCredentialSource` factory injection. The receiver needs no
vault key; a configured source failure must not fall back to operator files.
Source unavailability must surface as private retryable infrastructure failure.
Inspect safe destination metadata and `cleanup_pending` independently from
`retired`: the durable outbox retries file collection after ciphertext removal
and controller reconstruction. Keep token-free stale-writer fences and audit;
do not acknowledge an unknown destination or collect operator-owned bindings.
See [delivery contracts](../../../docs/program-platform-development.md#managed-private-workflow-delivery).
Manual/canonical Session starts support explicit `workflow_access` under human
authorization. Inspect the frozen root/Session approval and original request digest;
provisioning belongs to the existing submission claim. See
[admission diagnostics](../debug-execution-admission/SKILL.md). Scheduled source
consent uses the shared purpose port; native restart/replay proof currently uses
Human Review. Generic authenticated event starts now use private source consent;
see [event diagnostics](../debug-program-events/SKILL.md). Provider-specific ingress,
rotation and isolated remote delivery remain open.

- Inspect the plan's frozen subject, requirements, deadline, receipts and revision.
  Repeating an owner/type/root/key intent recovers that plan, even after policy changes.
  A changed candidate/policy requires a new intent. Never replace failed evidence
  with a successful retry under the same check occurrence.
- Match subjects by canonical fingerprints, not Python dict/model equality:
  `True`, `1` and `1.0` can compare equal while identifying different inputs.
  Kind and all identity data participate. The mechanism is optional and does not
  make Git or blob references mandatory for other operation results.
- Humans issue/list/revoke `/api/verification-access` capabilities. Workflow access
  is limited to one owner/root, explicit policy IDs and create/read/cancel/run_check actions.
  Check the acting human audit identity as well as owner. A bearer failure never
  falls back to a cookie. Managed source resolution or an explicit operator-file
  binding selects owner/root/purpose authority; it shares that admitted capability
  within a root, without claiming per-node least privilege or hostile-code isolation.
- `VerificationAccessService` requires execution-root authority in addition to
  credential scope/hash/expiry. Pre-provisioned credentials cannot operate before
  the root is live, and native termination/cancellation denies authentication even
  when a stored projection is stale. Unknown authority is unavailable, never a
  reason to relax access or fall back to a cookie. Inspect completed results as a
  human; preserve separate evidence authority. This does not implement atomic
  stale-attempt fencing. Scheduled/event admission uses separately persisted,
  bounded source consent; event tags alone never approve workflow access.
- Opt-in `renewable_for_seconds` permits same-token renewal only within the
  original bounded horizon. The existing API reconciler rechecks policy and live
  root authority before expiry CAS; unknown authority never extends a lease and
  expired grants cannot revive. Inspect safe expiry/horizon metadata, cadence and
  page capacity rather than credential files. Mongo's server clock also fences
  expiry. Shared renewal scenarios cover both purposes; renewal does not imply
  rotation, managed remote delivery, process-restart or remote acceptance.
- Fixed-expiry and not-yet-due grants also enter bounded upkeep. Closed roots or
  withdrawn policy persist revocation; missing pre-provisioned roots remain
  pending. Expired grants retire without native authority. Mongo compares the
  observed expiry and its own clock, preventing stale retirement from revoking
  a renewed grant. Retain issuance/hash audit, read the repository's revoked
  overlay, and distinguish eventual metadata retirement from authentication-time
  root enforcement. Do not delete operator-owned private files as a workaround.
- Native workflow tests must publish/start through the same API owning their root
  records. Do not run a test-local root against an unrelated API grant service or
  replace production liveness with an always-active double to make E2E pass. The
  scope-only HTTP/unit tests explicitly use a narrow authority double; actual
  workflows use shared API/Mongo/native execution. For Temporal, pass the real
  worker host to the verification API fixture and retain replay/restart/cleanup
  acceptance at the milestone. Backend/token metadata alone does not prove it.
- Human sessions and scoped workflow clients manage plans. Evidence uses a separate bearer and
  `X-Verification-Authority`; the API keeps a credential hash, not the raw secret.
  Check both the frozen verifier IDs and the current authority's owner scope.
  Knowing an owner, plan ID or desired verdict does not authorize an attestation.
  Never print credential/environment contents while diagnosing 401/403 responses.
- A deadline fences new receipts. Identical receipt retries remain acknowledgments;
  an accepted plan stays accepted after its deadline. Cancellation fences new
  receipts and preserves prior audit data. Conflicting results are 409, not overwrite.
- Mongo uses the existing native async connection and revision-checked updates.
  Preserve compare-and-set on append/cancel; process-local locks do not cover two
  API workers. Do not read a disconnected stream as an accepted result.
- `await_verification@1` uses short inspection invocations and runtime timers.
  `resolved` includes rejection/cancellation/expiry; `poll_limit` can retain pending
  state. Cancelling a waiter does not cancel the borrowed plan. Inspect business
  outcome rather than treating a completed child as accepted work. Bounded renewal
  is opt-in; persisted terminal/expiry revocation uses bounded upkeep. Private-file
  collection remains incomplete. Authentication independently denies a closed root.
- Inspect a check intent's status and admitted configuration digest. `uncertain`
  is persisted before dispatch, including when no POST was ultimately sent.
  Never reset it to ready or retry submission because a search found nothing.
  Reconcile the existing identity; conflicting, absent or truncated matches cannot
  prove safe resubmission. Provider refusal and failed verification are different.
- GitHub bindings are API-server operator configuration, never receiver credentials.
  Validate repository, numeric workflow ID, exact workflow commit, dispatch event,
  attempt one and `lumora-{intent}-{candidate_commit}` title. A changed binding
  must not reinterpret an old intent. Internal verifier IDs cannot also have an
  external evidence credential. The trusted workflow must check the exact commit;
  a successful unrelated workflow or a coding agent's report is insufficient.
- `await_check_run@1` refreshes through normal invocations and native timers.
  A resolved refusal is not success; recorded evidence for one check is not
  necessarily accepted work. The waiter does not cancel GitHub jobs. Missing
  provider artifacts cannot be assumed recoverable until local publication commits.
  Permanent absence and cancellation policy remain open.
- A report-required check cannot submit status-only evidence. Inspect the admitted
  source manifest, `reports_collected` and `evidence_recorded` separately. Do not
  replace a frozen source when the provider deletes/expires it. A committed local
  publication can recover a lost acknowledgement without another provider download.
  Corrupted/mismatched bytes must never attest; keep the original manifest/audit.
- GitHub archive redirects require explicit HTTPS host admission and an entirely
  fresh request without API auth, cookies or inherited client credentials. Never
  log signed URLs. Do not extract or execute a report archive during transfer.
- Native humans can attach a provider-confirmed run to an uncertain check using
  an idempotency key/current revision/reason. Preserve the acting-human audit.
  Workflow grants cannot resolve or supply a verdict. A known run attachment does
  not prove that an absent dispatch was never sent, and does not authorize resubmission.

Start with application/domain cases, then actual Mongo/HTTP, then signed-cookie
API restart. Reuse `tests/support/verification.py`, `verification_programs.py` and
the transport owner `verification_api.py` for local/durable scenarios;
do not import test cases or add another scheduler. From repository root:

```sh
.venv/bin/python -m pytest platform/tests/application/test_verification.py platform/tests/domain/test_verification.py platform/tests/adapters/test_verification_settings.py -q
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest platform/tests/integration/mongo/test_verifications.py platform/tests/integration/http/test_verifications.py platform/tests/integration/redis/test_verifications.py -q
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 LUMORA_TEST_TEMPORAL_ENDPOINT=127.0.0.1:7234 .venv/bin/python -m pytest platform/tests/integration/verification platform/tests/integration/http/test_verification_access.py platform/tests/integration/temporal/test_verification.py -q
```

Use only the repository's dedicated services and temporary listeners. These cases
make no paid calls. Native passing/failing content checks and receipt persistence
do not establish hostile-process isolation, complete software acceptance, remote
verification execution or a complete UI/CI delivery workflow. The Temporal cases
observe an actual timer, stop the worker before submitting evidence, restart it,
and replay root/child histories. Explicit operator endpoint/private-directory
bindings belong to worker environment, not prepared payloads or raw token inputs.

For a GitHub failure, start with `application/test_check_runs.py`, then
`integration/verification/test_github_checks.py`, `test_check_workflow.py` and
`test_check_restart.py` and `test_check_reports.py`. Reuse `support/check_runs.py` port doubles,
`support/github_checks.py` wire contracts and `support/check_api.py`'s durable test
peer. A whole reconciliation deadline must cover all pages, not reset per request.
These fixtures execute no live GitHub job and must not be presented as that proof.
Native grant tests must issue at current time: Mongo independently checks expiry
against its own clock. Keep deterministic clocks for pure tests; do not disable
server-clock fences to accommodate an old fixed-date integration fixture.
