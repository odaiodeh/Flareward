# Persisted review evidence for replaceable reviewer Programs

Scope: a Step B prerequisite for [reusable Human Review](../architecture/coordinator-programs/README.md).
The new capability is implemented and locally verified. Existing ADLC Design and
Engineering still import/call the concrete review coordinator; their migration,
shared result contracts, version updates and recovery acceptance remain next work.
C6 and the coordinator milestone are not complete.

## Boundary and behavior

Replacing a guarded concrete reviewer with an arbitrary compatible Program must
not turn a schema-valid claimed approval into trusted evidence. The caller needs
to confirm the record it consumes, independently of the reviewer's implementation.

`ConfirmReview` carries the review ID, expected policy, exact subject and invoked
reviewer execution ID. `ReviewService.confirm` uses existing READ authorization,
re-reads the persisted record, compares canonical subject identity and policy, then
checks provenance through the application-owned `ReviewExecutions.contains` port.
`ExecutionReviews` follows persisted, owned parent records and checks root identity.
It allows completed descendants, refuses sibling/foreign/cyclic ancestry and reports
unavailable lineage without fabricating an answer. It does not use native liveness
to reject a successfully completed reviewer child.

The generic review feature owns these checks. It knows nothing about ADLC candidate
schemas, Git, graph traversal, or how the reviewer coordinates its work. A graph
reviewer can call another reviewer and return its record; the occurrence must still
belong to the selected subtree. The caller supplies the child ID returned by the
runtime rather than trusting an execution ID from the returned evidence.

`confirm_human_review` follows ordinary Element conventions: `ConfirmReviewSpec`,
`ConfirmReviewFactory`, typed `ConfirmReviewOperation`, and the existing review
provider/gateway. Its HTTP adapter uses `POST /api/reviews/confirmations` with the
same root/policy/action-scoped authority. Confirmation does not issue credentials,
submit human decisions or change pending/rejected/closed records into approval.
It returns the authorized current persisted record.

## Source

Lumora HEAD `54d0a42a8141b878b85248deec6c7742c4bb4274`, plus uncommitted work.
Source/test delta SHA-256: `89dea3fc4df0ea49fbfec70e9ea858c2e4d86a4b953e5d03513af8d5ff603af0`.
Digest uses `git diff --binary -- platform/src platform/tests ui/client ui/tests`
then sorted untracked path, NUL and file bytes. Run Engine remains at
`60393440efd3876cd6c81e0b013e8bf6d9167659`, without edits. Program payload remains v9.

## Verification

```sh
.venv/bin/python -m pytest platform/tests/application/test_reviews.py platform/tests/application/test_review_program.py platform/tests/application/test_engineering_program.py platform/tests/application/test_feature_design.py platform/tests/adapters/test_review_ancestry.py platform/tests/integration/catalog/test_plugin_installation.py platform/tests/architecture -q --tb=short --maxfail=3
```

**86 passed.** Covers pending/decided authoritative reads, wrong subject/policy,
sibling/unknown occurrence, foreign owner, exact integer-versus-float identity,
completed nested ancestry, missing/foreign/cyclic records and existing ADLC behavior.
The earlier 44-test focused run overlaps this regression gate.

```sh
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest platform/tests/integration/reviews/test_confirmation.py -q --tb=short --maxfail=1
```

**4 passed.** A normal registered coordinator invokes a reviewer Program, awaits
its result and invokes the ordinary confirmation Operation using the returned child
ID. The reviewer is either direct Human Review or an owned graph wrapping it.
Both paths run on real Local thread/process invocation runners with dedicated
Mongo/Redis, TCP FastAPI, separate workflow/human authority and actual persisted
decisions. The graph-wrapped record belongs to a descendant rather than the direct
reviewer ID. API requests for a sibling, changed subject or different policy reject.
These are deterministic review workflows, not paid agents or remote sandboxes.

Changed Python passes Ruff `I,F821,F822,F823,E9`; `git diff --check` and the updated
Human Review diagnostics skill validator pass. An omitted API import was caught and
fixed by static checking before tests. No scoped failure remains.

## Remaining work

Migrate ADLC review fields to explicit Program dependencies plus caller-owned
confirmation requirements. Share the public review result contract without importing
its concrete coordinator. Preserve candidate/evidence identity, remove the old
AttemptRuntime wrapper when no caller remains, update registered implementation
versions and migrate current authoring fixtures/clients. Then verify replacement,
cancellation and durable restart/continuation before claiming C6.
No Temporal recovery, full browser, Kubernetes/OpenShell, current-image rebuild or
capacity gate ran in this slice; they remain in the agreed milestone sequence.
