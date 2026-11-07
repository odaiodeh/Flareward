# Unchanged live Engineering revision: independent and nested execution

Recorded 2026-11-06. Extends the [live browser journey](2026-11-06-live-feature-ui.md)
with an explicit same-publication reuse gate. This is Local/OpenShell HTTP proof,
not a second browser run, broad remote/recovery acceptance or full product completion.

## Behavior and boundaries

The live fixture publishes Engineering revision 1 once, retaining its captured
coding resources, verification/review configuration and owned candidate bodies.
The same API/database then runs that revision independently and invokes it as
Feature revision 1's pinned Engineering child. No Program is republished or edited
between the executions. The test compares the complete published revision before
and after each run and observes the nested child's exact Program reference/root.

Both runs use real Codex in the `coding` OpenShell profile, independent production
checks in offline OpenShell, and trusted local artifact loading/publication. Normal
operation construction, Program invocation, capabilities, review and Run Engine
integration remain unchanged. Identity/design generation and HTTP review responses
are controlled test peers. Each root independently consents to three capabilities.
The nested case still proves that only Design runs before exact design approval,
without producing a new candidate artifact before that decision.

The test verifies exact source/report hashes and sizes, three passing cases,
root-specific plans and review records, and owner HTTP 403 on private verifier
executions. Six capability reservations retire with no remaining credential fields
or JSON files. Both source/report pairs are fetched again after owned compute is
removed. Decoded source, reports, results, public revisions and the API log are
audited for the actual private coding key with constant failure diagnostics.

## Failure found and corrected

The initial expanded gate on `content-handoff-20261106` images failed in **44.89s**:
the independent run passed, but nested root `07a2acc4b4764b32b7ead82f59a302a7`
failed with `Coding agent could not execute its CLI protocol`. That message could
not distinguish a known bound/failed turn from malformed protocol or process failure.
No raw provider output was retained, so its underlying cause remains unknown.

Inspection found that `asyncio.TaskGroup` wraps adapter-owned `CodingAgentError`
exceptions. The outer adapter's generic group handler discarded even their already
sanitized reasons. It now preserves a single known coding error, while unknown or
mixed groups retain the generic safe message. There is no raw stderr/event logging,
new automatic retry, relaxed limit or new scheduling abstraction.

Native subprocess tests now check meaningful failed-turn, output-limit,
incomplete-answer and command-limit messages, plus malformed output containing a
synthetic secret. They retain redaction, process reaping, private-home cleanup,
timeout/cancellation, containment and explicit sandbox composition coverage.

The later live pass does not prove this diagnostic correction fixed the original
transient cause. Both runs used the same model and execution bounds; it establishes
the successful reuse case with the corrected adapter, not a live reliability rate.

## Verification and images

```sh
.venv/bin/python -m pytest multi-agent/tests/integration/coding/test_codex_cli.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**15 passed in 8.26s.** Strict mypy (`--strict --follow-imports=silent`, normal MAS
source paths) passes the changed Codex adapter. Ruff check/format passes that adapter,
the CLI fixture, CLI tests and live reuse test. Collection and `git diff --check` pass.
Unrelated shared/browser/Temporal suites were not repeated for this focused change.

Built a fresh receiver and derivative because installed execution code changed:

```sh
docker build \
  --build-arg RECEIVER_BASE=ghcr.io/nvidia/openshell-community/sandboxes/base@sha256:aeef1c63f00e2913ea002ccb3aaf925f338b5c5d70e63576f0d95c16a138044e \
  --build-arg RECEIVER_USER=sandbox \
  --build-context unifai="$PWD" --build-context run_engine="$PWD/../run-engine" \
  --file multi-agent/tests/infra/Dockerfile.receiver \
  --tag unifai-sandbox:engineering-reuse-20261106 multi-agent/tests/infra
docker build --build-arg SANDBOX_IMAGE=unifai-sandbox:engineering-reuse-20261106 \
  --file multi-agent/tests/infra/Dockerfile.codex \
  --tag unifai-codex:engineering-reuse-20261106 multi-agent/tests/infra
.venv/bin/python multi-agent/tests/infra/verify_images.py \
  --image unifai-sandbox:engineering-reuse-20261106 \
  --image unifai-codex:engineering-reuse-20261106
```

Both builds exit 0. Each image matches **1,398 production/runtime and fixture Python
files**, with replaced paths absent. CLI remains 0.166.0; no Run Engine edits were made.

| Image | Identity |
| --- | --- |
| `unifai-sandbox:engineering-reuse-20261106` | `sha256:8bac75472f77a1577f4529e4426a60d69cc91b27d85d185d913023f91bac3556` |
| `unifai-codex:engineering-reuse-20261106` | `sha256:8910693cf8e01eb2b1f8abbe7fce93fc2b519c5f0a02ace015f9367663361d6f` |

The corrected coherent gate used the existing private opt-in binding:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
UNIFAI_TEST_OPENSHELL_ENDPOINT=127.0.0.1:8090 \
UNIFAI_TEST_OPENSHELL_PKI="$PWD/multi-agent/tests/infra/.state/openshell-20261105/pki" \
UNIFAI_TEST_OPENSHELL_IMAGE=unifai-codex:engineering-reuse-20261106 \
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_live_feature.py \
  --live-coding --platform-backends=openshell --platform-hosts=local -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' \
  --junitxml=multi-agent/tests/infra/.state/reports/20261106-engineering-reuse-openshell-corrected.xml \
  -p no:cacheprovider
```

**1 passed in 43.81s**, proving both invocations. Execution source was frozen during
builds, image comparison and the gate. Kept the same live process handle until exit 0.

## Exact outcomes and cleanup

| Entry point | Root | Outcome | Coding attempts |
| --- | --- | --- | --- |
| Engineering revision 1 | `3aa6fb7d12e142c38fee5ea388686760` | verified | 1 |
| Feature revision 1 -> Engineering revision 1 | `70e11be0865f43ab84c2f7d0a1c58310` | verified | 1 |

Both source files have SHA-256
`4ba6c8881970c15c36e02f5784c3ea2713b519d51b02afdaf39c13e3e95189da`, 33 bytes.
Their root-scoped identities and reports remain distinct:

| Entry point | Candidate artifact | Report artifact |
| --- | --- | --- |
| Independent | `7f7730dd778519438c5149422a0f3cb5841ab0807587e41871d2ab72219b6784` | `72b4542bd26c3a61506510300d406b9f6a8bbde3b018a4e3406566b1d4f97c1a` |
| Nested | `89e77e5dfbf91c8af7f62ba972eecf75bb2388edbc67675d95f5a483f80288db` | `03c08b88bd1ea5a853075b2a845408e8dea60a278f093c2f055142d00d8b33ca` |

The [focused manifest](2026-11-06-engineering-reuse-source.json) retains result
identities, report hashes and selected exercised source. Public accepted results
were saved in the owned pytest directory as `accepted-results.json`; temporary
files are diagnostic conveniences, not the durable acceptance record.

Native fixture teardown completed, API log reports application shutdown, no API
source workspace or managed credential JSON remains, and Docker's new-image
container query returns no running or stopped receivers. The isolated Mongo fixture
owns database teardown. Shared services and images remain available.

## Remaining acceptance

This proves unchanged reuse with the small file candidate, one owner, two sequential
Local roots and normal OpenShell isolation. It does not establish live repair,
concurrent agents, hostile same-user secret isolation, Temporal recovery, Kubernetes,
full Git/CI/Jira delivery, completion alternatives or performance at scale. Existing
native/controlled repair evidence remains separately scoped. Full authoring starting
from UI-created resources/Programs, live design generation and canvas convergence
remain open; passing reuse must not erase those first-product gaps.
