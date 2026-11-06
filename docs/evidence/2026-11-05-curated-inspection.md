# Curated draft-provider inspection: reconciled checkpoint

Recorded 2026-11-05 after resuming the revised product-led goal. This completes
recording/verification of the previously paused inspection slice; it does not
complete administration, migration, or the feature-delivery journey.

## Behavior and ownership

`ResourceInspectionService` owns inspection intent and administrator authorization.
The Mongo probe owns resolution, installed provider SDK calls and client/task cleanup.
Explicit `InspectionContext` distinguishes owner overlay inspection from curated-base
inspection while retaining workspace ownership and the acting human credential ID.

Signed-human administration endpoints probe saved private curated dependencies or
inline configuration using shared base defaults. Existing resource endpoints always
use caller overlays, including when that caller is an administrator. Request payloads
cannot elevate normal inspection into curated-base inspection. Teams cannot assert
human authority; bearer-plus-cookie requests are refused. Persisted administrator
revocation takes effect for existing cookies.

Production UI clients use the native endpoints. Curated validation has its own
user/resource-version cache namespace, a bounded batch size and explicit observation
mode/time. A transport failure is unavailable, not an invalid provider result. Eligible
curated elements retain execution-profile editing. No permanent revision certification
or provider guarantee is inferred from a live observation.

## Source and verification

The `curated_inspection` group in
[the focused source manifest](2026-11-05-product-checkpoint-source.json) records 22
files, aggregate SHA-256
`a22a67756c129fa7ac7d869e58351263a62e9388cbbcc10abf03e17ae0c57070`.
This is a focused file identity, not a full dependency/image manifest. The worktree
contains extensive pre-existing changes; its base HEAD is recorded in the manifest.

Focused resumption command:

```sh
.venv/bin/python -m pytest \
  multi-agent/tests/application/test_resource_inspection.py \
  multi-agent/tests/adapters/mongo/test_resource_inspection.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**15 passed in 0.18s.** Authorization precedes probe access; base/owner behavior,
selection/time bounds, safe failures and sibling cleanup are covered.

Native/client command, with UnifAI's own services:

```sh
UNIFAI_TEST_MONGO_URI='mongodb://127.0.0.1:27018' \
UNIFAI_TEST_MONGO_TRANSACTION_URI='mongodb://127.0.0.1:27019/?directConnection=true' \
UNIFAI_TEST_REDIS_URI='redis://127.0.0.1:6380/15' \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/http/test_curated_inspection.py --ui-clients \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

The initial attempt errored during Mongo setup with sandbox `Operation not permitted`;
no endpoint behavior was exercised. The same selected gate with authorized local
service access **passed: 1 test in 3.22s**, no skips or reported warnings. It includes
real signed cookies, actual HTTP/Mongo transactions/Redis, installed provider probes,
private failure translation and the production TypeScript client. No paid model.

Strict mypy passes for the eight changed production inspection/composition modules
listed in the manifest (ports, service, Mongo probe, both inspection routers,
dependencies, library and platform). All 18 Python files across the two checkpoint
groups pass Ruff lint/format. `npm run typecheck` in `ui/` passes. The shared final
692-test gate is recorded in [candidate evidence](2026-11-05-coding-candidate.md);
counts overlap and must not be summed as independent coverage.

## Limitations

Private curated dependency selection and nested editing in the actual resource
form remain incomplete. API-client execution and static typing do not establish
browser interaction or React cache behavior. Observations do not pin an immutable
dependency snapshot. No image rebuild, remote backend, load/failover or full legacy
retirement proof was performed here. Existing test services were intentionally kept;
fixture databases, sessions and API processes are owned/cleaned by the test harness.
