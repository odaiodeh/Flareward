# Operator-pinned verifier Programs

Recorded 2026-11-05. Adds the production execution-to-verification connection needed
for checker Programs using normal placement/composition. Current native evidence
uses a controlled JSON-value checker, not actual software tests or live coding.

## Implementation and trust boundary

`ProgramCheckRunner` implements existing check/report ports using narrow application
execution/revision ports. Normal ProgramService and ExecutionService supply those
ports. No Run Engine SDK dependency, scheduler, environment manager, new Program
kind or separate execution lifecycle was added.

Private `UNIFAI_PROGRAM_CHECKS` bindings pin a published Program's owner, reference
and exact definition digest alongside existing verifier policy. The invocation
cannot supply that authority. A graph or backend implementation can provide the
same typed check interface. Installation/publication alone grants no attestation.
Settings reject conflicting runner names, missing artifact storage, incompatible
policies, disabled verification and overlap with external evidence credentials.

Inputs identify the check intent, plan, check and exact subject. Outputs identify
its fingerprint, verdict and optional JSON details. Before observation or report
admission the runner rechecks actual execution owner/reference/digest, root/input
identity and candidate fingerprint. Unknown, foreign, malformed, oversized or
mismatched output cannot attest. Failed/cancelled jobs produce safe error reports.
Provider diagnostics and credentials are not copied into those generated reports.

A stable execution ID identifies each check. Lost start acknowledgements reconcile
through existing persisted execution records; missing work never authorizes another
start. Report bytes/manifests reconstruct from stored results across controller
reconstruction and use the existing exact-content artifact collection pipeline.

Jobs are independent verifier-owned roots, like external CI jobs. They do not
pretend to be Engineering children or inherit its workflow credentials. Candidate
owners can inspect admitted check evidence/reports but cannot inspect another
owner's entire execution. Raw provenance does not supply artifact-read authority.

## Verification

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture multi-agent/tests/adapters/test_verification_settings.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**743 passed in 6.94s**, no skips or reported warnings. This scope includes adapter
settings tests and must not be described as the earlier shared-only 720-test gate.
New application cases cover lost acknowledgement, missing execution without
resubmission, changed trust binding, foreign/malformed results, terminal error
reports, report reconstruction/manifest mismatch and cancellation propagation.

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/verification/test_program_checks.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

Final **4 passed in 30.37s**, no skips or reported warnings. Actual production
composition, signed-cookie sessions, HTTP, Mongo/Redis and thread/process operations
exercise both passing and failing candidates. The checker belongs to a distinct
operator owner. The test verifies denied cross-owner execution inspection, exact
pinned revision and subject/report identities, then reconstructs the API and
retrieves unchanged completed evidence and durable report content.

The first four-case run failed after check evidence was recorded because its test
expected 404 for foreign execution inspection. The established execution adapter
returns 403. Corrected that assertion, preserving production authorization behavior.

Existing regression gate:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/verification/test_github_checks.py \
  multi-agent/tests/integration/verification/test_check_reports.py \
  multi-agent/tests/integration/verification/test_check_restart.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

Initially **29 passed, 2 failed in 22.15s**. The two native GitHub tests issued grants
at their fixed November 1 clock, now expired against Mongo's independent server
clock. Changed only those native scenarios to initialize their test clock at current
UTC. Pure deterministic clocks and production expiry fencing remain unchanged.
Targeted rerun of `test_github_checks.py -k native_api_reconstructs` with the same
services/options: **2 passed, 13 deselected in 0.89s**. This is targeted recovery of
the failures, not a claim that the entire 31-case gate was rerun afterward.

Strict mypy (`--strict --follow-imports=silent`, existing four-root MYPYPATH) passes
the three changed production modules. Ruff check/format and diff checks cover the
focused changed source/tests. No UI code changed; green browser/client suites were
not repeated. No Docker images, Kubernetes/OpenShell/Temporal matrices or paid model
calls were run. Owned test API/workers/stores follow existing fixture teardown;
dedicated shared infrastructure remains running.

## Remaining product work

This bridge does not certify checker logic, provide untrusted-code isolation or
transfer candidate content automatically. An actual software checker still needs
trusted tests, suitable isolated placement, separately scoped input access and
private bindings. Automatic plan-to-job cancellation, cross-root resource accounting,
in-flight Temporal recovery and current-image remote cleanup proof remain required.
Existing root bounds do not aggregate these independently owned verifier jobs.

The active milestone remains real Engineering acceptance: connect actual isolated
software verification and bounded live coding, then complete integrated authoring
and unchanged nested reuse. The JSON fixture does not satisfy those requirements.
No companion Run Engine modifications were made.

## Source identity

[Focused manifest](2026-11-05-program-checks-source.json) identifies the changed
source/tests and relevant execution/check contracts. This is not a full dependency
or image manifest. Source aggregate SHA-256: `1444a8ed3b9cd76e5ca3b10d928e8a98d7f3bb22cc101c2e496ec5020abcac82`.
