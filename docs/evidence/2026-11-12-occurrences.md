# Operation and Program call observations — 2026-11-12

Step C progress; C8's full nested authoring/overlay experience and C9 remote
acceptance remain open.

## Implemented ownership

`executions/domain/observation.py` defines portable occurrence/page values.
`OccurrenceProjection` owns the bounded application view; it does not schedule,
retry, restore work or persist execution state. Run Engine still owns execution.
The adapter observes native graph node events and invocation outcomes, and marks
custom runtime calls explicitly through invocation metadata. It never guesses a
site from an engine ID or publishes work inputs, results or raw errors in this view.

Each execution has monotonically assigned call ordinals, authored call sites,
kind, last observed status, native graph step and logical graph retry attempt.
Program calls link to their actual child execution IDs. These are application
call attempts, not claims about hidden backend delivery attempts or worker readiness.
Contract failures can bypass terminal graph events; their returned invocation
outcome still closes the observed attempt. Retryable application failures produce
distinct attempts; non-retryable contract failures do not invent retries.

The outer Lumora run publishes its safe occurrence projection through native
snapshot operations. Native graph checkpoint-store behavior and durable workflow
execution are unchanged; this outer observation snapshot is not a graph-state or
checkpoint export. Durable hosts reconstruct the projection on replay.

`GET /api/executions/{id}/occurrences` authorizes the execution owner, checks source
location/identity, returns `private, no-store`, and paginates with `before`/`limit`.
The gateway translates native snapshot types into application values. Missing or
invalid snapshots are unavailable, not empty successful progress.

Retention is the latest 256 calls. `truncated` explicitly reports lost earlier
history; `next_cursor` navigates retained history. Snapshot revisions change when
observed status/identity changes. The existing execution workbench now polls this
view, shows a paginated call/attempt table and actual child links, and preserves
last observations with explicit unavailable/partial messages. No parallel execution
screen was added.

Program worker contract is `lumora-program-v12`; request format remains v10.
Matched API, worker and receiver modules are required; remote images remain pending.

## Verification

- Broad domain/application/adapter/architecture/native-composition gate:
  **1,193 passed in 25.14s**. Log `/tmp/lumora-occurrences-regression.log`.
- Final focused projection/native HTTP gate: **8 passed in 2.56s**, covering
  graph/custom calls, thread/process, privacy/authorization, pagination, retention,
  application retries and non-retryable contract failure. Counts overlap the broad
  gate except the added final contract-failure assertion.
- Actual production Programs TypeScript client with FastAPI/Mongo/Redis/native
  execution: **1 passed, 10 deselected in 11.74s**; root/child occurrence links and
  Operation states match actual child records. Log `/tmp/lumora-occurrences-client.log`.
- Temporal ADLC API/worker restart, restored snapshot/child correlation and all
  seven descendant replays: approval/thread **1 passed, 5 deselected in 15.95s**.
- Approval/process and cancellation/process with the same snapshot/replay checks:
  **2 passed, 4 deselected in 30.98s**. The selector `adlc and cancel and process`
  also matches the function's `cancels` name, so both process outcomes were selected.
  Logs `/tmp/lumora-occurrences-replay-final.log` and
  `/tmp/lumora-occurrences-cancellation.log`.
- TypeScript, UI contracts, Python import/undefined-name/syntax checks and diff
  whitespace pass. Production UI build passes with existing large-chunk warnings;
  final build log `/tmp/lumora-occurrences-build-final.log`.

Source/test delta SHA-256: `82549c5a03ec42fdda677bf2c6452e36cc8402f24a7e36b6f5dbbb7f4daa087a` (binary tracked diff plus sorted
untracked path/NUL/content under platform source/tests and UI source/tests).
No paid calls or matched remote-image rebuilds were performed. Actual browser
render/interaction acceptance, waits/timer presentation, resumable incremental
updates, graph overlays, full retained/archived history, and nested/control editing
remain. A snapshot is an observation, not acceptance evidence for produced work.
