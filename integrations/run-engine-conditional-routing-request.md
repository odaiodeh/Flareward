# Run Engine request: conditional rejoining and explicit routing failures

Status updated 2026-10-30: RE-06 and ACTIVE stalled-frontier errors are implemented
in `da10d1ac`; **RE-07 is fixed in `60393440efd3876cd6c81e0b013e8bf6d9167659`**.
The unchanged reproduction reaches `finish` for `yes` and raises the portable
`UNKNOWN_CONDITION_LABEL` contract failure for `typo`. New plans default to ERROR;
old recorded inputs retain IGNORE. See [current integration status](README.md)
for policy, privacy, checkpoint compatibility and independently rerun evidence.

The original observations, requests and prototype evidence below are historical.
They document the original defect and acceptance criteria, not current patch
installation instructions. New builders now default to ACTIVE; old recorded plans
without policy retain ALL. Unreleased prototype requests/checkpoints require their
original implementation or rebuilding before submission.

## Task for the Run Engine owner

Investigate and implement the generic engine contracts below using small, cohesive
changes. Keep graph traversal inside Run Engine. Preserve SOLID boundaries,
typed configuration, closed-policy enums, portable checkpoints and deterministic
replay. Do not import UnifAI, agent/LLM concepts, application authorization,
application condition schemas or another scheduler into the engine.

Do not blindly adopt the attached prototype. Validate its semantics, lifecycle,
checkpoint and compatibility behavior; replace it with a better minimal design
if the evidence warrants it. Report exact tests and unverified cases.

## Confirmed observation 1: a selected branch cannot naturally rejoin

```text
+---------------------------------------------------------------------------+
| SDK-ONLY GRAPH                                                            |
|                                                                           |
|                         +--------------+                                  |
|                         | choose       |                                  |
|                         +------+-------+                                  |
|                                | condition returns "yes"                  |
|                     +----------+----------+                               |
|                     v                     v                               |
|              +--------------+      +--------------+                       |
|              | yes          |      | no           |                       |
|              | selected     |      | not selected |                       |
|              +------+-------+      +------+-------+                       |
|                     |                     |                               |
|                     +----------+----------+                               |
|                                v                                          |
|                         +--------------+                                  |
|                         | finish       |                                  |
|                         | declared exit|                                  |
|                         +--------------+                                  |
+---------------------------------------------------------------------------+
```

Actual result using the default public SDK API:

```json
{"condition_outcome":"yes","phase":"completed","visits":["choose","yes"],"declared_exit_executed":false}
```

`finish` has both `yes` and `no` as static predecessors. Only `yes` executes, so
static all-predecessor gating never activates `finish`. Traversal then exhausts
its active set and completes. UnifAI's real condition graphs reproduced this on
both thread and process invocation backends.

**Classification:** the current all-predecessor behavior is documented, so the
missing active-path join mode is a capability gap, not a request to silently
redefine the existing default. The resulting completion/diagnostic ambiguity is
addressed separately below.

### Requested contract

Provide an explicit typed way to request a join over active upstream paths:

1. An unselected conditional branch does not block a downstream join.
2. When several selected branches are active, wait for all applicable active
   paths, including unequal-length branches. This is not a first-result/ANY join.
3. A pending join is retained and reconsidered after upstream paths advance or
   are eliminated by later decisions; do not drop blocked candidates.
4. Execute the rejoin once for the resolved frontier, while preserving intended
   repeated execution in loops.
5. Checkpoints retain enough strategy position to restore pending joins exactly.
6. Preserve explicit Goto and FinishTraversal semantics and lifecycle ownership.
7. Keep the existing static ALL policy available with compatible default behavior.

Names such as `JoinPolicy.ALL` and `JoinPolicy.ACTIVE` are illustrative. The owner
should choose the clearest API and verify whether global or per-node policy is
needed; do not build unused policy machinery.

## Confirmed observation 2: unknown branch labels silently end the graph

With the same topology, make the condition return `"typo"`, which is absent from
the declared branch map. Actual SDK output:

```json
{"condition_outcome":"typo","phase":"completed","visits":["choose"],"declared_exit_executed":false}
```

Condition invocation validates string/list result types, but successor resolution
uses a branch lookup that discards unknown labels. This makes a routing mistake
look like successful completion.

### Requested contract

- Define and enforce an explicit unknown-label policy. A strict mode should
  produce a portable permanent contract failure before scheduling any next nodes.
- Validate a list/tuple as a whole: one unknown label must not silently disappear
  while valid labels run.
- Keep errors safe: identify the contract violation without echoing arbitrary
  potentially private condition output.
- Specify empty-result and intentional termination semantics. Do not confuse
  explicit terminal controls with accidental unknown labels.
- Plan compatibility for earlier graphs that intentionally used an unmapped
  label to stop. Do not introduce replay-breaking global strictness silently.

UnifAI now validates its own declared labels at its adapter boundary, but generic
SDK callers still need an engine-level contract. The engine need not adopt
UnifAI's boolean normalization or legacy `END` spelling.

## Related request: completion diagnostics

The observations above return `completed` without executing the declared exit.
Please make it possible to distinguish intentional completion from traversal
that ran out of runnable nodes with unresolved dependencies.

Choose an explicit completion/validation policy or useful typed diagnostics.
Do not simply require the exit in all cases: supported intentional early
termination/finalization must retain its documented semantics. Specify which
states are successful, invalid, stalled or intentionally terminated, and how
those appear in results/status/events.

## SDK-only executable reproduction

The companion file [conditional_join.py](repros/conditional_join.py) contains no
UnifAI imports. It uses `GraphBuilder`, a simple typed state, LocalHost and public
graph handles. No databases, containers or paid APIs are required.

From the UnifAI repository root with the editable SDK installed:

```sh
.venv/bin/python -c 'import asyncio, json; from integrations.repros.conditional_join import reproduce; print(json.dumps(asyncio.run(reproduce("yes"))))'
.venv/bin/python -c 'import asyncio, json; from integrations.repros.conditional_join import reproduce; print(json.dumps(asyncio.run(reproduce("typo"))))'
```

For a standalone Run Engine task, copy that small module into an importable test
fixture module and update the import in those commands. Keep the fixture importable
by receiving workers; do not bypass portable-function validation with closures or
`__main__` references.

The essential public graph construction is:

```python
builder = GraphBuilder(VisitState)
for uid in ("choose", "yes", "no", "finish"):
    builder.add_node(uid, visit, kwargs={"uid": uid})
builder.add_conditional_edge(
    "choose", choose, {"yes": "yes", "no": "no"}, kwargs={"outcome": outcome}
)
builder.add_edge("yes", "finish").add_edge("no", "finish")
graph = builder.set_entry("choose").set_exit("finish").compile()
```

## Relevant source ownership

All paths below are relative to Run Engine:

| Source | Relevant responsibility |
| --- | --- |
| `src/runengine/programs/graph/models/graph.py` | Serializable topology and static predecessor calculation |
| `src/runengine/programs/graph/traversal/strategy.py` | Conditional label -> target mapping |
| `src/runengine/programs/graph/traversal/bsp.py` | Readiness gating, pending frontier and algorithm position |
| `src/runengine/programs/graph/lifecycle.py` | Traversal completion, interrupts and finalization |
| `src/runengine/programs/graph/node_invocation.py` | Received condition result contract |
| `src/runengine/programs/graph/builder.py` | Public declarative policy selection |

Keep backend clients and application-specific decisions out of the traversal
algorithm. Conditional routing should behave identically across coordination
hosts and invocation backends.

## Acceptance matrix

### Semantics

- XOR choice -> shared join: only the chosen branch runs, followed by the join.
- Selected fan-out -> join: all selected branches complete before one join.
- Unequal-length selected branches: a short path must not trigger the join early.
- Nested condition eliminates a possible upstream path after a join was deferred.
- A condition routes directly to the rejoin, bypassing the alternative branches.
- Repeated loop rounds: prior-round completion must not satisfy fresh active work.
- Multiple incoming labels mapping to the same target do not duplicate execution.
- Unknown scalar/list label gives the defined contract failure; no partial routing.
- Empty outcomes, explicit termination, Goto and FinishTraversal follow their
  stated contracts.

### Durability and compatibility

- Pause/checkpoint while a join is deferred, restore and complete exactly once.
- API/worker replacement during that position; native Temporal histories replay.
- Cancellation during active upstream work drains owned work as before.
- Old graph/checkpoint payloads retain their default interpretation and wire shape.
- New policy/configuration requires compatible coordinator/receiver builds; reject
  incompatible capabilities explicitly rather than silently degrading semantics.
- Preserve legacy histories or state the required version/worker drain boundary.

### Execution levels

1. Isolated strategy/model units, including legacy serialization assertions.
2. Actual Local host with thread and process invocation.
3. Actual Temporal host/worker with thread and process, restart and replay.
4. Relevant existing graph contracts, commands, interrupts, loops and program-node
   composition regressions.
5. Selected actual remote backend validation after rebuilding matched images.

Use Run Engine's test skill and test guide. Report passes, failures, skips, warnings,
selected matrix and image identities separately. No real LLM calls are needed.

## Historical local prototype status

[archived run-engine-active-joins.patch](archive/run-engine-active-joins.patch) illustrates an opt-in
ACTIVE policy using the live frontier and forward predecessor relationships.
It retains deferred candidates in strategy position and omits default/empty new
fields from legacy serialization.

At the time of the original investigation, the prototype was applied locally and
uncommitted after the five earlier integration patches. It has since been
superseded by the committed SDK; see [README](README.md). Its five isolated units
passed. With UnifAI selecting the experimental mode, 69 focused UnifAI condition,
factory, graph and architecture cases passed in 6.15 seconds
(`/tmp/unifai-conditions-active-joins-20261030.xml`). Before enabling it, the same
focused set had 16 failures demonstrating missing rejoins, with 53 cases passing.

Six further UnifAI cases passed in 7.19 seconds using separate Temporal worker
processes, then replaying their histories after the workers closed. They cover both
exclusive outcomes and selected fan-out, with thread/process condition invocation
and thread invocation for the work nodes
(`/tmp/unifai-conditions-durable-20261030.xml`). These prove the selected completed
histories replay; they do not prove restart from a deferred join or old-history
upgrade compatibility.

This does not prove the prototype ready for upstream adoption. The full SDK suite,
deferred-checkpoint recovery, upgrade behavior, remote images and final lint/type
review remain unverified; the last lint read found import/format issues. The prototype does not
implement generic strict unknown-label handling or completion diagnostics.

## What is not an engine request

- Threshold numeric selection, enum/config validation and condition registration
  are UnifAI responsibilities; those defects are being fixed in UnifAI.
- LLM structured generation, review permissions, ADLC budgets, artifact business
  schemas and agent orchestration remain application responsibilities.
- Run Engine already provides children, waits, timers, cancellation and environment
  ownership. Do not duplicate them in UnifAI.
- Richer OpenShell URL/method policy support and automatic private-secret binding
  for managed environments are separate integration requests, not established
  causes of this routing failure. Track them independently if implemented.
