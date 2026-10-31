---
name: debug-program-schedules
description: Diagnose UnifAI native program schedules, reused Temporal workflow IDs, stale calendar edits, tick admission, and schedule-history replay.
---

# Diagnose native UnifAI schedules

Read [the native schedule contract](../../../docs/program-platform-development.md#native-program-schedules)
and [the test infrastructure guide](../../../multi-agent/tests/infra/README.md).
Use this workflow for `/api/program-schedules`; retained `/schedule.*` routes and
their legacy workers have a separate drain/migration obligation.

Trace one tick through the actual boundaries: Temporal calendar action, generic
Run Engine worker, installed scheduled entrypoint, invoked business admission,
and program execution in the same owning run. The admission effect runs on the
trusted worker. It does not create another execution host or graph child.

Check the boundary indicated by the evidence:

- Duplicate sessions, wrong result, or wrong cancellation: compare native workflow
  **and run** IDs. Calendar actions can reuse a workflow ID within one second.
  New empty-ID native ingress uses a versioned `TemporalRunIdentity`; the adapter
  resolves an explicitly pinned handle. Keep decoding and SDK types outside the
  application layer. Child operation identities must include the generation too.
  When auditing pinned handles, also exercise ordinary submitted roots: their
  recorded child-parent IDs remain ordinary IDs. Child status must retain the
  recorded parent representation and validate its generation against native
  metadata, rather than reducing every parent to a workflow-ID alias.
- Conflicting or apparently ignored edits: distinguish queue acknowledgment from
  application. The installed SDK's high-level update omits the native conflict
  token, and even the fenced RPC can acknowledge before the scheduler rejects a
  conflict. Confirm the applied version and complete registration, including the
  prepared digest, before reporting success. Use the controlled real-service
  concurrent-writer test; an in-process lock does not prove cross-process fencing.
- Missing tick records after delivery trouble: inspect accepted execution and
  session identities. Admission writes the accepted execution first, then creates
  its session idempotently. Reconciliation must observe that run, not submit a new
  root. Preserve the original human credential binding and immutable snapshot.
- Replay failure: preload the same installed worker modules, use the original
  namespace, and select the exact native generation. Replay old unmarked histories
  with their original identity behavior. Do not weaken replay restrictions or
  replace a generation pin with a latest-workflow lookup.
- Timer budget changes: manual actions bypass the automatic budget. Metadata/input
  edits preserve its live remainder; rearming a completed series resets its counted
  offset while retaining durable session history. Compute interval phase with
  timedeltas, preserving UTC normalization and microsecond precision.

Run from the repository root with the documented service URIs configured:

```sh
.venv/bin/python -m pytest multi-agent/tests/application/test_program_schedules.py multi-agent/tests/adapters/test_program_calendar.py multi-agent/tests/architecture -q
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_schedules.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

After engine identity changes also run its native-identity, Temporal handle/message,
and fixed-history replay regressions. Rebuild receiver images before remote tests.
Use recorded IDs for targeted calendar/workflow cleanup. Never delete unrelated
schedules, print credential-bearing payloads, or count a queued action as a completed
program. Report verified behavior separately from legacy migration and retention gaps.
