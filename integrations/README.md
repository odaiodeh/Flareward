# Run Engine integration handoffs

UnifAI owns application behavior. Run Engine owns traversal, coordination,
invocation and environment lifecycle. This inventory tracks the integration
contracts without moving UnifAI business logic into its execution infrastructure.

## Current dependency: committed SDK

Verified on 2026-10-30: the local Run Engine checkout is clean at commit
`60393440efd3876cd6c81e0b013e8bf6d9167659`
(`fix(graph): reject unknown condition labels before scheduling successors`),
following the active-join commit `da10d1ac32e93a9752b9b5db1e0c71eced2f4b16`.
It includes the five earlier integration extensions, durable ACTIVE joins and strict
unknown-label routing.
Use this committed baseline; do not apply the historical patches to it. Package
version `0.2.0` alone does not distinguish this source from earlier checkouts.
This verification establishes a local commit, not a published release or push.

UnifAI imports `GraphBuilder`, `JoinPolicy` and `UnknownLabelPolicy` from the public
`runengine` API and explicitly selects ACTIVE joins and ERROR label handling. It no longer depends on the local join
prototype. See [development setup](../docs/program-platform-development.md).

| ID | Contract | Status on the committed baseline |
| --- | --- | --- |
| RE-01 | Portable arguments for registered program-node mappings | Included. Application binding interpretation remains in UnifAI. |
| RE-02 | Public observation of accepted direct children | Included. Native retention/history still defines observation limits. |
| RE-03 | Authenticated OpenShell TLS for invocation and managed environments | Included. Private certificate/key contents remain on the dispatcher. |
| RE-04 | Exact native execution generation identity | Included. Namespace/workflow/run identity distinguishes rapid schedule starts. |
| RE-05 | Typed OpenShell filesystem/process/Landlock/network policy | Included. Current network subset is hosts/ports/executables; URL paths/methods are unsupported. |
| RE-06 | Conditional selected paths rejoin correctly | Implemented by committed ACTIVE joins, including pending frontier and loop/checkpoint handling. |
| RE-07 | Explicit unknown-label failure | Fixed by `6039344`: validate the entire selection before scheduling, fail with `UNKNOWN_CONDITION_LABEL`, and omit returned values from diagnostics/condition events. Legacy IGNORE remains supported. |
| RE-08 | Unresolved-join completion diagnostics | ACTIVE traversal now fails when retained dependencies cannot progress. Strict labels are supplied separately by RE-07; intentional termination need not execute the declared exit. |

## Earlier verification against the join commit

Independent UnifAI-side checks on 2026-10-30:

- SDK active-join units and join integration modules: **135 passed**, no skips,
  in 30.40 seconds, including actual Temporal on UnifAI's `127.0.0.1:7234`.
  One existing `MapReduceState.items` shadow warning was reported.
  JUnit: `/tmp/unifai-engine-joins-temporal-adoption-20261030.xml`.
  An earlier run passed 95 and skipped 40 without the Temporal enable flag;
  the enabled run supersedes that limited result.
- UnifAI condition, blueprint and actual Temporal condition/replay modules:
  **45 passed** in 12.96 seconds. Temporal used UnifAI's own `127.0.0.1:7234`
  service with separate workers and thread/process condition invocation.
  JUnit: `/tmp/unifai-engine-conditions-adoption-20261030.xml`.
- Full current nonremote UnifAI gate with TypeScript API clients: **589 passed**,
  zero failures/errors/skips or reported warnings, 239.65 seconds. Remote program,
  OpenShell policy and paid coding modules were excluded for separate execution.
  JUnit: `/tmp/unifai-committed-engine-platform-20261030.xml`.
- The unchanged [SDK-only reproduction](repros/conditional_join.py) now produces:

```json
{"condition_outcome":"yes","phase":"completed","visits":["choose","yes","finish"],"declared_exit_executed":true}
{"condition_outcome":"typo","phase":"completed","visits":["choose"],"declared_exit_executed":false}
```

The SDK owner's `tests/VERIFICATION.md`, section “Conditional active-path joins:
2026-10-30”, records broader SDK regression, checkpoint, native replay, lint and
type checks. Those are owner-reported results, not a full SDK gate rerun by UnifAI.
For that earlier join commit, UnifAI rebuilt Kubernetes/OpenShell receiver images
and verified **1,173 Python files per image** against the then-current sources. Its deterministic remote matrix
passed **28 cases** across Local/Temporal and Kubernetes/OpenShell, including
composition, dependencies, environment lifetime/borrowing, private settings, replay
and physical cleanup. The OpenShell allow/deny policy matrix passed **8 cases**
across both hosts and environment lifetimes. No paid model tests ran. These results
do not cover remote worker loss, concurrent Codex, or Celery. Exact image identities
and reports are in the [migration ledger](../docs/execution-platform-migration.md).

## Strict-label adoption (2026-10-30)

The unchanged SDK-only reproduction now raises a permanent contract failure for
`typo`, with code `UNKNOWN_CONDITION_LABEL` and only `{node_uid: choose}` in its
details. A valid `yes` still reaches `finish`. Independent SDK strict/legacy/checkpoint/replay and join checks passed **232 cases**
in 49.37 seconds on UnifAI Temporal 7234 with thread/process receivers, no skips
and one existing fixture warning. JUnit:
`/tmp/unifai-engine-label-policy-adoption-20261030.xml`. The current nonremote UnifAI gate passed **589 cases** in 301.45 seconds, with
zero failures/errors/skips or reported warnings:
`/tmp/unifai-strict-label-platform-20261030.xml`. Matched Kubernetes/OpenShell images each match **1,175 Python files**. The
Local/Temporal × Kubernetes/OpenShell program matrix passed **28 cases** in
358.81 seconds, no failures/errors/skips or reported warnings. JUnit:
`/tmp/unifai-strict-label-remote-20261030.xml`. Exact image identities are in the
migration ledger. The policy matrix above belongs to the preceding join commit;
it was not rerun for this label-only SDK change. The earlier
results above belong to `da10d1ac`, not automatically to this newer SDK.

UnifAI retains its application condition normalization and declared-label checks.
They define boolean and legacy `END` semantics before generic engine routing.
The engine remains independent of those product meanings.

New plans default to `UnknownLabelPolicy.ERROR`; missing policy in old recorded
plans/checkpoints retains IGNORE. Whole scalar/list/tuple selections are validated
before scheduling any successors. Empty lists/tuples select no route; empty strings
and `END` are ordinary exact declared labels. Mismatched checkpoint policy is
rejected. Old strict parsers reject new ERROR plans, so deploy matched coordinators
and receivers. Graphs constructed inside durable application programs need their
own upgrade/replay review. Safe errors/events do not remove ordinary return values
from native invocation histories: data/secret policies still apply.

## Upgrade and recovery boundary

The subsequent native-action module migration was also verified against this SDK
with fresh source-matched receiver images: **28 remote cases passed** across
Local/Temporal and Kubernetes/OpenShell. This confirms existing remote composition
and environment contracts after UnifAI's module moves, not remote condition-label
invocation specifically. Current image identities, scope and the separate broad/
focused action gates are in the [migration ledger](../docs/execution-platform-migration.md#native-async-action-migration-2026-10-30).

New `GraphBuilder` plans default to ACTIVE. Explicit ALL and recorded plans without
a policy retain ALL behavior. The policy belongs to the strict `GraphPlan` /
`GraphProgramInput` boundary, not topology. Older strict parsers reject ACTIVE
plans instead of silently interpreting them as ALL. See Run Engine's
`src/runengine/COMPATIBILITY.md` before deploying coordinators and receivers.

The unreleased UnifAI-side prototype placed policy in a different payload layout.
Its requests/checkpoints are incompatible with the committed ACTIVE layout.
Rebuild unsubmitted prototype graphs; finish already submitted prototype executions
on their original compatible implementation. Keep old workers/recovery material
until actual drain is verified. This document does not assert those runs are drained.

Historical patches are preserved in [archive](archive/README.md) for investigation
and recovery, not installation into the current SDK.

## Remaining handoff

[Conditional-routing request](run-engine-conditional-routing-request.md) retains
original reproductions and acceptance requirements. RE-06/RE-07 and the ACTIVE stalled-frontier part of RE-08 are now implemented.
Retain the original acceptance criteria as regression requirements and complete
matched deployment/upgrade validation. Do not reimplement traversal in UnifAI.

Separate investigations remain richer supported OpenShell egress controls and
private-secret provisioning into engine-owned environments. Establish actual
backend capabilities before adding interfaces. Current live evidence for external
secret mounts/files does not prove automatic managed-environment secret setup.
UnifAI continues to own authorization, approved profiles, provider credential
resolution, review schemas, agent behavior and application condition semantics.
