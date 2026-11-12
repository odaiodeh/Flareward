# Mixed delivery composition — 2026-11-12

C5 is accepted for the controlled Local host/thread/process scope below. C6
Temporal recovery, C8 authoring/observation and C9 remote lifecycle remain open.

## Working flow

The ordinary delivery graph calls an owned Repeat. Its owned graph body invokes a
pinned Engineering 4 revision. Engineering calls a pinned coding candidate Program,
independent trusted Python checks, and an owned Human Review Program. ResultRoute
maps Engineering outcomes to boolean iteration completion. Native joins/reducers,
child identity and configured bounds use existing contracts; no compiler special
case or new scheduler was introduced.

Shared authoring data: `platform/tests/support/delivery_composition.py`.
Native acceptance: `platform/tests/integration/coding/test_delivery_composition.py`.
Both reuse existing coding resources, protocol executable, verifier publication,
managed access, review clients and API/process ownership.

Each case starts the production FastAPI composition with signed human/reviewer
sessions, real dedicated Mongo/Redis, automatic workflow credentials, saved coding
resources, published Programs, actual Codex adapter subprocesses and independently
executed Python checks. The controlled CLI writes a broken addition implementation;
checks fail; Engineering restores the exact candidate and failed reports for repair;
the CLI writes the corrected source; checks pass before review.

The outer Repeat covers approval, rejection followed by approval in a new iteration,
and repeated rejection reaching the iteration limit. Assertions distinguish engine
completion from verified business outcome, validate review/candidate identity,
check distinct iteration executions and failed/passed independent checks, and
retrieve exact artifact bytes after deleting the coding workspaces.

## Verification and limits

Final native gate: **6 passed in 119.74s (0:01:59)** across all three outcomes and both runners.
Command uses `LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018` and
`LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15` with:

```sh
.venv/bin/python -m pytest platform/tests/integration/coding/test_delivery_composition.py -q --tb=short
```

Initial infrastructure preflight failed because the dedicated Mongo/Redis
containers were stopped. Only `flareward-e2e-mongo-1` and
`flareward-e2e-redis-1` were restarted. Publication then correctly rejected the
fixture's unordered branch writes; the graph now explicitly selects its declared
reducer policy. Preliminary thread cases passed before the final artifact-survival
assertion and full two-runner gate. These are overlapping checks, not extra totals.

Base HEAD: `54d0a42a8141b878b85248deec6c7742c4bb4274`.
Source/test delta SHA-256: `46b130422fb6db1283f736929bc21a1a41491de83ac50686b5fffb6e4f1d558c` (binary tracked diff plus sorted
untracked path/NUL/content for platform source/tests and UI source/tests).
Native gate log: `/tmp/lumora-delivery-composition-final.log`.

The Codex CLI is a deterministic protocol peer: no paid LLM/provider acceptance is
claimed. This is composition/check/review/artifact evidence, not live Jira/CI/CD,
browser, Temporal replay, Kubernetes/OpenShell or physical remote cleanup proof.
