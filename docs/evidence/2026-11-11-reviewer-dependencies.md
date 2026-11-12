# ADLC reviewer Program dependencies

Date: 2026-11-11. Step B implementation checkpoint, not complete coordinator or
platform acceptance. Builds on [persisted confirmation](2026-11-11-review-confirmation.md).

## Working behavior and ownership

`feature_design@2` and `engineering@4` declare reviewer Program dependencies. They
invoke the configured alias through `ChildCalls`, then confirm the returned review
ID against the caller's exact subject, expected policy and actual child execution
subtree. A pinned graph reviewer may delegate to an owned Human Review Program;
its descendant's persisted decision can satisfy the caller without changing ADLC
coordination code. A returned approval cannot replace a persisted rejection.

- `plugins/adlc/programs/reviewer.py`: `ReviewDependency` owns the alias, expected
  policy, registered confirmation bundle and confirmation placement. `Reviewer`
  owns invocation and authoritative consumption through existing runtime ports.
- `lumora/services/reviews/domain/results.py`: portable result and wait-reason
  contracts, independent of the concrete Human Review coordinator.
- `plugins/adlc/programs/design.py` and `program.py`: domain-specific subject and
  outcome logic; declared reviewer inputs/results and producer/reviewer alias checks.
- `plugins/adlc/programs/contracts.py`: existing shared effect/authority validation,
  moved out of the Engineering coordinator. Current coding/feature callers migrated.
- `support/review_children.py`: shared application test peer using the real Human
  Review coordinator and review service, with distinct child identities and retained
  ancestry after completion. Existing authoring helpers now bind reviewer bodies
  explicitly; they do not inject fallback production bindings.

ADLC no longer imports `HumanReviewConfig` or `human_review`, and `AttemptRuntime`
is removed. Reviewer template, assignment, deadline and wait bounds belong to the
configured target. No old config/version aliases are installed. Ordinary plugin
registration, publication, resource closure, child admission and Run Engine runtime
paths are reused; Run Engine was not edited.

When a reviewer returns at its check limit, lifecycle inspection can cancel its
still-pending review because the reviewer execution has ended. Confirmation returns
that current persisted state; ADLC reports `review_closed`. The advisory
`check_limit` reason remains the reason the reviewer returned. It never establishes
approval or triggers automatic repair. This intentionally changes the old direct
helper's pending-result behavior. Already-decided records retain their decisions.

## Verification

Checkout HEAD: `54d0a42a8141b878b85248deec6c7742c4bb4274`, with preserved milestone
changes. Run Engine HEAD: `60393440efd3876cd6c81e0b013e8bf6d9167659`.
Final source/test delta SHA-256:
`ed0360c6c911f9afbddb0a49f418244e3db63b2aa74a4f3fa35bcb9e577c27b2`.
Hash uses the tracked binary diff and sorted untracked paths/content for
`platform/src`, `platform/tests`, `ui/client`, and `ui/tests`.

- Application + architecture gate: **848 passed**, 12.52s.
  `.venv/bin/python -m pytest platform/tests/application platform/tests/architecture -q --tb=short --maxfail=5`
  Log: `/tmp/lumora-reviewer-application.log`.
- Final focused alias/configuration/plugin gate: **26 passed**, 2.12s.
  `test_review_dependency.py`, `test_engineering_completion.py`,
  `test_coordinator_catalog.py`, and `integration/catalog/test_plugin_installation.py`.
  Log: `/tmp/lumora-reviewer-final-focused.log`. Overlaps the application gate;
  includes the subsequently added producer/reviewer alias-collision case.
- Native Design + Engineering: **10 passed**, 73.09s.
  `integration/verification/test_feature_design.py` and `test_engineering_workflow.py`.
  Log: `/tmp/lumora-reviewer-native.log`. Actual TCP FastAPI, dedicated Mongo/Redis,
  signed owner/reviewer sessions, managed root authority, native Local execution,
  thread/process invocation. Direct owned and pinned graph reviewers, revision
  rejection/approval, exact evidence, repair, standalone/nested Engineering and
  credential retirement are covered. Formatting and a validator-method rename
  followed this gate; no subsequent production behavior change.
- Enclosing Feature and file/Git completion gate: **8 passed**, 142.52s.
  `integration/verification/test_coding_feature.py`,
  `integration/coding/test_feature_workflow.py`, and
  `integration/coding/test_completion_choices.py`.
  Log: `/tmp/lumora-reviewer-feature.log`. Actual HTTP/services and native
  thread/process execution cover approved/rejected Design gating, controlled coding
  and repair, persisted exact review evidence, retained artifacts, and selecting
  file/Git completion contracts through the migrated nested Programs. Coding uses
  deterministic protocol peers; these are not new live-model acceptance results.
- UI contract script passes: `pnpm --config.verify-deps-before-run=false run test:contracts`
  from `ui`; log `/tmp/lumora-reviewer-ui-contracts.log`.
- Changed-Python import/syntax checks and `git diff --check` pass. Review diagnostic
  skill validation passes. Status/plan/evidence index remain 100/117/80 lines.

Native commands use:
`LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018`
and `LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15`.
No paid model calls, Docker rebuilds, remote environment changes, or commits.

## Remaining scope

C6 remains unchecked: focused cancellation and native decisions do not prove the
migrated caller's Temporal restart/replay matrix. C5/C7 still require generic
result routing and the mixed delivery graph -> Repeat -> attempt journey. Nested
UI/authoring, authoritative occurrence history, full browser acceptance, matched
Kubernetes/OpenShell images and remaining platform obligations are still open.
