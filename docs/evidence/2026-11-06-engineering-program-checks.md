# Engineering uses the production verifier

Recorded 2026-11-06. The controlled Engineering journey now uses the normal
production API and Program checker, including in the actual App. Design and CLI
responses remain controlled fixtures. This is not full live Engineering acceptance.

## Integration and ownership

- `CheckProgramSetup` publishes through the owner-authorized Program API and pins
  the actual immutable revision digest. Standalone check and Engineering fixtures
  share this setup instead of duplicating publication or replacing runtime services.
- The Python verifier is published by `trusted-verifier`, separately from the
  candidate owner. Engineering uses `program@1`; its policy requires reports from
  `program-ci`. The normal `ProgramCheckRunner` dispatches the pinned Program.
- The evaluator receives bounded, exact source bytes and arguments. Expected
  answers and comparison stay in the trusted verifier coordinator. Local thread/
  process evaluation is explicitly enabled only for this controlled source.
- Native tests prove the candidate owner receives 403 for private verifier
  execution inspection, while the verifier owner sees the pinned completed run.
  Admitted reports remain inspectable by the candidate owner.
- The failed candidate and its canonical `details.failures` report are restored
  into a fresh coding workspace before repair. Final review names the exact
  repaired artifact. Design approval, trusted checks and final acceptance remain
  distinct. No new scheduler, environment manager or application bypass was added.
- The obsolete transient `support.python_check_api` and `PythonArtifactCheck`
  were removed after migrating both callers and passing the replacement gate.
  The generic deterministic peer remains for separate text-only policy tests.

## Automated verification

Dedicated Mongo/Redis integration gate:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/coding/test_feature_workflow.py \
  multi-agent/tests/integration/verification/test_program_checks.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**14 passed in 135.55s.** This includes the complete feature flow on thread/process
and standalone verifier pass/fail, API reconstruction and cancellation/retirement
contracts. Tested source was frozen while this gate ran. Subsequent fixture edits
only update module descriptions and remove the unused peer.

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture multi-agent/tests/adapters/test_execution_policies.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**776 passed in 7.33s**, including operator policy loading/validation. Both migrated
browser/publication fixtures cold-import successfully. Ruff check/format passes
the eight affected Python files. No UI implementation changed in this checkpoint.

## Actual browser journey

Built the actual App using the maintained browser procedure:

```sh
cd ui
NODE_ENV=production node tests/build-placement-browser.mjs /tmp/unifai-feature-production-check-assets
```

Build: **4.89s**, 4,563 modules, workspace script `workspace-browser-CdfussQQ.js`.
Existing circular-vendor and large-chunk warnings remain. Started
`support.feature_browser` against dedicated services with a unique database and
owned directory. Identity/design/CLI are controlled; execution, storage, API,
check runner and Python verifier use production implementations.

Root: `b2da919b-bdf6-4d49-a3f4-db2327a58300`, Feature revision 1. Through actual
UI fields supplied `Implement add(a, b) in answer.py`, an addition criterion and
explicit review/verification/artifact permissions with 3,600-second leases.
No workspace or coding-start marker existed before version-1 design approval.

Observed a failed and a passing production check, each with one admitted report;
both recorded evidence. Repair restored the failed report in a different workspace.
Inspected repaired source before final approval. Root/children completed with
`verified`, two attempts, accepted verification and persisted human decisions.

Deleted only the two temporary coding workspaces, reloaded the execution URL and
reopened source/report previews. Fresh retrieval returned the repaired function
and `{"verdict":"passed","details":{"cases":3,"failures":[]},...}`.

| Output | Artifact ID | SHA-256 | Bytes |
| --- | --- | --- | --- |
| `answer.py` | `8e724e8e5ba630ff0ca8855aff7432660a54d8c2f4e2f7a8544c4e5125bc53ee` | `ba1a531f581d2e6094e978ed6f7aca7a8d92eeb62c6e7ad73ee692f7f18bc772` | 32 |
| `check.json` | `09c56c0e160aaf9208f5dbb62985a46db0eccf28a47f2d85aa0ebdcf4b893340` | `e420e3739eb4635236ab2631d5ad52db87b94b655ac2835d0555410c1de8b592` | 145 |

[Browser evidence after compute deletion](assets/2026-11-06-engineering-program-checks.png).
All three managed reservations retired: zero unretired/cleanup-pending rows,
zero retained credential fields, and no credential JSON files. The API log
contained neither the synthetic provider token nor the artifact-token prefix.
Closed the tab and stopped the same runner once; it confirmed deletion of
`unifai_feature_browser_11f23dbe5b8a43f0a368b1d05c3d749f`. Both owned API/identity
processes shut down cleanly. Shared services were retained.

## Limits and next acceptance

The [live two-Codex smoke](2026-11-06-normal-openshell.md) and this controlled full
journey are separate proofs. Full live Engineering still needs safe remote
artifact/credential handoff, isolated evaluation and the approved UI journey in
one run. Unchanged nested reuse, complete authoring, Temporal/recovery, broader
remote matrices and remaining target requirements stay open. No Docker rebuild
or paid call was repeated for this fixture integration.

The [source manifest](2026-11-06-engineering-program-checks-source.json) identifies
selected runtime/test/UI files and the screenshot/build artifact. It is a focused
snapshot, not a complete dependency or image manifest.
Selected-source aggregate: `2c0640b488c004bb6385ed78e6995390f34061202fa785a32a098d7486354848`.
