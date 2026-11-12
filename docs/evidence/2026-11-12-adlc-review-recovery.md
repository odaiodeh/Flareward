# Migrated ADLC reviewer recovery — 2026-11-12

C6 is accepted within the Local/Temporal and thread/process scope below. This
completes Step B's scoped composition/review/routing acceptance; C8-C10 and the
larger platform's remote, credential, capacity and delivery obligations remain.

## Current-source behavior

`integration/temporal/test_reviews.py` adds four ADLC cases to the existing
review infrastructure. Design 2 binds a pinned graph reviewer whose owned body
uses Human Review 1. The production ADLC caller confirms persisted evidence using
the shared `Reviewer` helper and ordinary scoped confirmation Operation.

The worker stops after an actual native review timer is observed. A signed human
reviewer rejects design revision one while the execution worker is absent. The API
then restarts on the same borrowed listener; an identical decision retry recovers
the immutable response. A new worker resumes the caller, confirms the persisted
rejection, and generates revision two with that feedback. The new subject and
review occurrence have different identities; a conflicting approval of revision
one fails with 409.

The final action is approval or root cancellation. Approval yields the confirmed
exact revision-two subject and approved business outcome. Cancellation closes the
pending review and refuses a late approval. Both runners require all seven native
root/descendant executions to become terminal and replay every history through
the installed worker modules. Two graph reviewer executions plus their owned
review bodies share the pinned revision; `body_path` distinguishes them.

Shared ownership comes from `managed_access_api`, signed-session clients,
`api_process`, `worker_process`, existing authored review/design fixtures, and
native `replay`. No replacement scheduler, replay mechanism, review implementation
or bypass of the application confirmation boundary was introduced.

## Verification

- Temporal migrated ADLC gate: **4 passed, 2 deselected in 55.21s**.
  Selected `-k adlc` from `platform/tests/integration/temporal/test_reviews.py`.
- Current Local reviewer replacement gate: **8 passed in 51.06s** from
  `platform/tests/integration/verification/test_feature_design.py`: direct and
  pinned graph reviewers, thread/process, exact revision/feedback, duplicate and
  stale decisions, approved and revisions-exhausted outcomes.
- Changed Python imports/undefined-name/syntax checks and diff whitespace pass.
- An initial recovery case reached its final assertions but counted owned review
  bodies as independently published graph reviewers. The corrected assertion
  checks both revision and empty `body_path`; the final gate above is authoritative.

Services: dedicated Mongo `127.0.0.1:27018`, Redis `127.0.0.1:6380/15`, and
Temporal `127.0.0.1:7234`, isolated databases and task queues. The pre-existing
`flareward-e2e-temporal-1` was restored; unrelated services were not changed.
Fixture ownership drains API/worker processes and cleans only this test's native
identities if interrupted. No confirmed-live handles remain from these gates.

Base HEAD: `54d0a42a8141b878b85248deec6c7742c4bb4274`.
Source/test delta SHA-256: `6c0bc1a51a63a2285f87725a04746fa4dab187d5b1d756dd2b9f67640d93d96e` (binary tracked diff plus sorted
untracked path/NUL/content under platform source/tests and UI source/tests).
Logs: `/tmp/lumora-adlc-review-recovery-final.log` and
`/tmp/lumora-adlc-review-local.log`.

The designer is a deterministic registered coordinator peer. No paid reasoning,
full browser, Kubernetes/OpenShell image rebuild or broad remote/credential/crash
matrix was run. Engineering's current Local composition evidence is in the mixed
delivery checkpoint; this gate adds migrated Design confirmation after Temporal
recovery, rather than claiming every ADLC workflow on every backend.
