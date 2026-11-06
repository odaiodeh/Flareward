# Native reporting and reconciled artifact checkpoint

The resumed worktree already contained the integrated managed artifact capability
and verified canonical startup. The unfinished slice was native reporting. This
record supersedes unfinished reporting notes, not the remaining platform goal.
The worktree contains extensive earlier migration changes; none were reset.

## Behavior and ownership

`ReportingService` owns human administrator authorization, UTC time scope, pinned
revision labels and operational completion. `ReportingReader` is its async query
port. Mongo aggregation, signed-session HTTP and UI presentation remain adapters.
Application/domain cold-import and dependency-direction checks cover the slice.
Parallel queries/label lookups use owned task groups: failures cancel and drain
siblings before returning a safe error, and caller cancellation remains cancellation.

Owner overview counts exact user/team draft, resource and last-observed session
scopes. Admin analytics count root execution records, excluding nested children.
An administrator can inspect aggregate reports without gaining another owner's
execution access. Client-supplied identity and bearer credentials confer no human
reporting authority. An empty persisted admin list revokes bootstrap access;
missing policy permits explicit bootstrap users, while policy failure returns
unavailable authority. The directory is reread, without stale authorization cache.

Owner pages are bounded to 100, top owners to eight, pinned Program revisions to
ten and activity to the latest 366 UTC days, with explicit truncation and full-period
totals. No unbounded owner list is embedded in a Program result. Mongo queries have
per-operation time limits. Names use executed immutable revisions, not modified
drafts. Completion is completed / (completed + failed + cancelled), or null when
there are no terminal executions. It is not verified or human-accepted work.

Reporting is explicitly a stored, eventually consistent projection. Queries do not
refresh engine state and are not an atomic snapshot across queries/collections.
Payloads/configuration/credentials are excluded from public reporting data. A
memory-only deployment reports unavailable storage rather than invented zeros.
These bounds and tests are not tenant-load or production-scale acceptance.

Production dashboard/analytics clients now call `/api/reporting/overview` and
`/api/reporting/system`. Owner pagination is server-side; Program rows show pinned
revisions, unavailable completion stays unavailable, and the UI explains stored
observations. The old statistics service and Flask routes, duplicate activity table
and old blueprint-named analytics components are removed, without aliases.
The installed-image verifier now rejects `mas.statistics`; no new image was built.

## Final checks

From the repository root, using Python 3.14 `.venv`:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain multi-agent/tests/architecture -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_reporting.py multi-agent/tests/integration/http/test_reporting.py multi-agent/tests/integration/ui/test_editor_client.py::test_graph_references_and_session_output_contracts --ui-clients -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 .venv/bin/python -m pytest multi-agent/tests/integration/mongo/test_artifact_workflow_access.py multi-agent/tests/integration/verification/test_engineering_workflow.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

- Shared domain/application/architecture: **647 passed**, 6.28s.
- Real Mongo/native HTTP/TypeScript reporting and pure UI contracts: **6 passed**,
  5.93s. Includes empty data, long/truncated history, root/child filtering, exact
  user/team identity, pagination, persisted revocation/malformed policy, private
  payload exclusion, actual native invocation and production API clients. The
  final shared-layer gate includes failure/cancellation sibling-cleanup tests.
- Managed artifact regression: **4 passed**, 24.27s. Actual Mongo lifecycle/clock
  fencing and standalone/embedded Local Engineering with thread/process receivers,
  automatic artifact authority, exact fixture bytes and retirement remain green.
  Candidate files and service peers remain deterministic, not paid coding agents.
- Strict mypy: seven production reporting/access/Mongo/HTTP/bootstrap/settings
  modules passed. Run from `multi-agent` with `MYPYPATH=lib:adapters:plugins:.`,
  `../.venv/bin/mypy --strict --follow-imports=silent` and those explicit paths.
- `cd ui && npm run typecheck` passed. Ruff lint/format passed on 18 changed
  production/test files, and `git diff --check` passed after whitespace cleanup.

On resume, API/Mongo checks passed but the new client fixture built an invalid
API URL. It now uses `rstrip('/') + '/api'`; both its focused rerun and the final
six-case gate passed. Final review identified unowned sibling work after a parallel
query failure; structured task ownership replaced gather, and affected shared,
native/client and typing gates were rerun successfully. Earlier gate output was unavailable across the handoff,
so final checks were rerun rather than inferred from an unobserved completion.

The [focused source manifest](2026-11-05-native-reporting-source.json) records 37
files and seven removed paths. Its path/hash-map aggregate SHA-256 is
`0ef5c36717a626db08ad8d32c6005c0d90b9a061cc875609a5de28efddfe169c`.
Python and API clients were frozen during final gates. Subsequent UI presentation
fixes clarify pinned revisions/owner labels and avoid comparing revision rows with
distinct Program totals; UI typecheck was rerun. Actual browser rendering remains
unverified. This is a focused identity, not a full-source or remote-image proof.

## Remaining acceptance

Remaining administration/built-ins, sharing creation/acceptance/cloning and templates
must migrate before AppContainer and residual Flask/old execution bodies can be
removed. The previous startup image predates reporting; rebuild and verify retired
installed modules at the coherent runtime-retirement milestone. No new Docker,
Temporal, Kubernetes/OpenShell or browser matrix ran for this reporting slice.
Private isolated delivery, remaining credential recovery/rotation, tenant admission,
authoritative occurrence observation, production Engineering, unified UI and full
current-source acceptance remain open. Run Engine was not changed.
