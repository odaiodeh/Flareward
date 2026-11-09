# Cooperative cancellation of running pool invocations

Inspected 2026-11-05 at Run Engine commit
`60393440efd3876cd6c81e0b013e8bf6d9167659`. No companion-project changes were made.

## Current behavior and observed limit

`ThreadExecutor.invoke` and `ProcessExecutor.invoke` submit `FunctionInvocation.run_sync`
to their respective executor pools and await `core.completion.await_completion`.
That helper shields the future and drains it before propagating cancellation.
`LocalTaskHandle.cancel` requests cancellation of the owning coordination task;
it does not interrupt the invocation's separate thread/process event loop.

This preserves ownership and avoids pretending that a cancelled await stopped a
running function. Its limitation is cancellation latency: even a natively async
application operation with reliable `finally` cleanup cannot observe coordinator
cancellation promptly while running inside that pool event loop.

Flareward's actual thread check test observed `cancel_requested=true`, coordination
phase `running` and check job `retiring` beyond a 15-second observation window when
the independently bounded operation had a 30-second timeout. The thread/process
cases pass when using a six-second operation bound and waiting for actual terminal
cancellation, child reaping and directory collection. They establish bounded
draining, not immediate preemption or a remote cancellation guarantee.

## Requested capability

Provide a public invocation cancellation contract for running async receivers,
with explicit acknowledgement/cleanup semantics. Keep it owned by Run Engine:

- Deliver cancellation to the particular invocation's receiver event loop so an
  async operation can unwind, kill/reap owned subprocesses and close resources.
- Distinguish requested cancellation, receiver cleanup/draining, and confirmed
  terminal state. A control acknowledgement alone must not mean work stopped.
- Fence attempts and scope delivery to the exact invocation. Cancelling one pool
  invocation must not terminate other invocations sharing that pool or borrowed
  environments owned elsewhere.
- Preserve bounded draining or an explicit unsupported capability for arbitrary
  synchronous code. Hard preemption requires appropriate process/container
  isolation; a Python thread cannot be safely killed.
- Preserve durable host/recovery semantics, especially cancellation after an
  uncertain dispatch or controller/worker restart. Do not silently redeliver work.
- Keep portable request data separate from private cancellation-channel bindings.

The particular transport is an engine implementation decision. Flareward should not
add an ad hoc Redis polling cancellation channel, reach into executor internals,
kill pool workers globally, or implement another environment owner as a workaround.

## Acceptance scenarios

1. An async thread invocation has acquired a subprocess and is awaiting its output.
   Cancel the owning run; observe cancellation in that invocation, run `finally`,
   reap its subprocess, and report terminal only after cleanup completes.
2. Repeat for a process worker with another unrelated invocation in the same pool.
   The unrelated invocation must continue normally.
3. Cancel during acquisition, while an invocation is queued, after uncertain
   dispatch, and repeatedly during cleanup; no acquired resource may be orphaned.
4. A synchronous noncooperative function follows its declared drain/preemption
   policy without claiming early termination.
5. Repeat relevant cases on Local/Temporal coordination, including API/worker
   restart and native replay. Verify actual retained/borrowed environment ownership.
6. Expose enough public capability/status information for application admission
   and truthful observation without requiring SDK-private handles.

Until then, Flareward retains retirement intent and observes exact execution state,
uses finite operation bounds, and reports the pool limitation explicitly. This
does not close the broader isolated/remote cancellation acceptance checklist.
