# Versioned feature design and approval-gated Engineering

Recorded 2026-11-05. This checkpoint advances the first feature journey. It does
not establish live coding, full UI acceptance, remote operation or overall completion.

## Implemented ownership and behavior

`mas_plugins.engineering.design` registers `feature_design@1` through the existing
Program registry. A configured designer child returns plan text and optional generic
references. The coordinator freezes the original task, nonempty acceptance criteria,
proposal and execution-local revision number into each Human Review subject.
Rejected designs feed the previous revision and actual recorded reviewer response
into a bounded retry. Approval, exhausted revisions, pending observation and closed
review are distinct outcomes. Result validation binds outcome to the exact reviewed
subject and authoritative decision returned by the scoped service operations.

`mas_plugins.engineering.feature` registers `coding_feature@1`. It composes normal
design and Engineering children. It checks that the reviewed request matches the
submitted prompt/context/criteria; an unsatisfied design returns without invoking
Engineering. Approval passes the exact proposal, criteria, revision and approval ID
alongside the original coding prompt. Combined input must satisfy existing context
bounds; it is never silently truncated. Child result contracts declare the complete
consumed models' required fields and use normal publication/runtime validation.
Optional defaults are not forced into required paths; a strict graph result can
omit its optional review on an unsatisfied outcome and still compose correctly.

Engineering now returns a result that identifies the same candidate as its checks
and review. `verified` requires accepted checks and human approval. Repairs receive
check evidence/report references and the recorded reviewer response, rather than
only verdict/decision labels. These serialized invariants do not turn arbitrary
self-reported records into authority; the execution path still uses scoped services.

All three Programs remain independently reusable. They use application runtime ports,
normal immutable publication, child calls, review effects and native waiting. No new
scheduler, element category, engine integration, provider-specific compiler branch
or graph-state dependency was introduced. Git remains optional.

Tests share application-only service runtimes and scenario constructors. Native
Engineering API/session/storage ownership is shared rather than copied into another
harness. The production coding adapter and the fixture candidate producer remain
separate; the fixture's optional workspace setting is only test scenario configuration.

## Source identity

[The focused manifest](2026-11-05-feature-design-source.json) records 18 Python files,
aggregate SHA-256
`8cfef7c628fb815460dde4de5413ea19782131b574cda0787410cd2992f6197e`.
This is not a complete dependency or installed-image manifest. The dirty checkout
base HEAD is recorded there. Run Engine source was not modified. Previous evidence
retains its older source identity and must not be described as current-image proof.

## Verification

Final shared gate:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture multi-agent/tests/adapters/mongo/test_resource_inspection.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**712 passed in 6.61s**, no skips or reported warnings. It covers the new design and
feature application scenarios, publication, exact-subject and outcome checks,
rejection/pending/expiry gates, cancellation, repair evidence and shared boundaries.
It also covers strict graph child output that omits the optional review. Earlier
focused selections overlap; do not sum their counts as independent coverage.

Final native milestone gate:

```sh
UNIFAI_TEST_MONGO_URI='mongodb://127.0.0.1:27018' \
UNIFAI_TEST_REDIS_URI='redis://127.0.0.1:6380/15' \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/verification/test_coding_feature.py \
  multi-agent/tests/integration/verification/test_feature_design.py \
  multi-agent/tests/integration/verification/test_engineering_workflow.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**10 passed in 62.64s**, no skips or reported warnings, using authorized local-service
access. The selected cases are:

- Four design journeys: thread/process review operations; reject revision one, then
  approve/reject revision two; distinct subjects/occurrences; unauthorized owner and
  stale conflicting decisions refused; pinned designer; automatic root credentials
  retired and managed material collected. The designer child completes before wait.
- Four composed feature journeys: thread/process effects; Engineering absent while
  either design is pending; unsatisfied design causes no Engineering child, checks
  or stored artifact metadata. Approval allows the pinned Engineering child, failed
  then passing independent content checks, bounded repair, exact-candidate final
  human review and artifact retrieval after compute-workspace removal. All three
  root capabilities are automatically provisioned and retired, including unused ones
  when design is rejected.
- Two existing Engineering regression cases: standalone and unchanged published
  child inside the delivery graph, exact fixture-byte verification/artifact survival
  and managed grant cleanup. The shared fixture refactor preserves those scenarios.

An earlier composition gate ended **4 failed, 6 passed in 49.00s**. Publication
correctly rejected incomplete child-result projections: the coordinator declared
only `outcome` while consuming complete Design/Engineering models. The fix projects
the required model fields, with a graph/backend publication regression. No validation
was bypassed. The affected four native cases then passed in 24.06s; the final
10-case gate above covers the complete corrected source and richer repair feedback.

Strict mypy passes for the four production Engineering modules. All 18 manifested
Python files pass Ruff lint/format. The updated composition diagnostic skill passes
its validator and records the result-projection pitfall; its stale request-format
reference was corrected from v9 to the actual v10. The target diagram was checked
for ASCII-only content and aligned 76-column rows. No UI source changed this turn.

## Limits and next acceptance

Designer and candidate production here are deterministic peers. Candidate files
are seeded fixtures, and the independent check peer verifies actual stored bytes;
it does not execute software tests on real agent-generated code. The separate
[coding handoff checkpoint](2026-11-05-coding-candidate.md) proves the production CLI
adapter with a protocol executable, not its complete integration with this root.

No paid model, actual browser, production Jira/CI/CD, Temporal recovery/replay,
remote execution, load/fairness or rebuilt image was exercised. Local waits are
in-memory; existing Temporal review evidence cannot certify these new compositions.
Generic references in design proposals are recorded, not dereferenced/certified.
Check report bytes and previous candidate content are not yet materialized into
repair workspaces. Full work acceptance still requires meaningful trusted checks,
real coding-agent execution and a thin existing-UI journey.

Next: combine the actual coding candidate with managed Engineering/checks, implement
required repair materialization, connect the stable design/feature contracts to the
existing UI, and run bounded live-agent acceptance before unchanged larger reuse.
All deferred controls, migration/retirement and final backend/recovery matrices
remain required. Test-owned databases, sessions and API/receiver processes are
cleaned by their fixture lifetimes; dedicated shared infrastructure stays running.
