# Workflow consent and the controlled Engineering UI journey

Recorded 2026-11-05. This proves a thin actual-App Engineering journey using
controlled design/CLI/check peers. It does not complete live-agent, production
verification, full authoring, remote execution or overall platform acceptance.

## Responsibilities and implemented behavior

- The application access registry describes installed issuers without authorizing
  or provisioning anything. Each issuer owns its request constraints and policy
  filtering. Rootless permission models reuse the existing runtime scope models;
  actual invocation supplies root identity. An additional issuer needs no catalog
  conditionals. Discovery cannot replace admission authorization.
- Human-only `GET /api/catalog/workflow-access` returns owner-filtered schemas,
  excludes private root/credential material and uses `private, no-store`. Owner
  identity includes type, so a same-ID team does not inherit a user's policies.
  Bearer-plus-cookie requests cannot elevate to human discovery authority.
- Manual Program invocation uses the shared schema renderer, selects no capability
  implicitly, requires explicit approval, and resets approval when permissions
  change. Frozen request identity, inputs and permissions survive uncertain retry
  within the mounted form. The execution workbench shows the persisted approval.
- Generic artifact detection has bounded depth, traversal and result count. The
  shared review/workbench inspector checks the exact blob reference against
  owner-authorized metadata. Explicit text preview bounds content to 256 KiB,
  verifies exact size and SHA-256, then strictly decodes UTF-8 into escaped text.
  Stream cancellation/release and selection/unmount ownership remain explicit.
  Downloads use the existing attachment endpoint; metadata is also no-store.
- Reviewer assignment does not grant another owner's artifact content. This
  scenario deliberately uses an owner who is also the assigned reviewer. No
  cross-owner attachment authority or execution-owner bypass was introduced.
- `support.feature_browser` composes the existing actual App/browser routes with
  the managed Engineering API and executable Python-check fixture. Saved encrypted
  coding resources and Program revisions use normal API construction/publication.
  Workflow grants are not pre-issued. Shared browser routes and CLI creation were
  extracted for reuse rather than copied into another application composition.

The UI contains no scheduler, credential resolver, provider implementation or
environment manager. Existing application admission/operations and Run Engine
continue to own execution.

## Verification

Final shared gate:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**720 passed in 6.67s**, no skips or reported warnings. Catalog tests exercise real
issuer schemas, owner filtering, byte limits, no side effects and registry extension;
they do not merely compare presentation strings.

The coherent native gate used dedicated Mongo/Redis:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/coding/test_feature_workflow.py \
  multi-agent/tests/integration/http/test_artifacts.py \
  multi-agent/tests/integration/http/test_workflow_access_catalog.py \
  multi-agent/tests/integration/ui/test_editor_client.py::test_workflow_access_typescript_clients_use_native_admission \
  --ui-clients -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**9 passed in 38.61s**, no skips or reported warnings. This includes actual artifact
HTTP/storage/lifetime contracts, read-only catalog discovery, manual/Session
production clients and thread/process approval-gated coding repair.

After adding an optional browser review timeout, reran just
`multi-agent/tests/integration/coding/test_feature_workflow.py` with the same service
URIs/options: **2 passed in 20.82s**. Automated timeout defaults remain 60 seconds;
only the manual browser scenario requests 600. The already-green unrelated native
gates were not repeated for this fixture-only parameter change.

Strict mypy with `MYPYPATH=multi-agent/lib:multi-agent/adapters:multi-agent/plugins:multi-agent`
and `--strict --follow-imports=silent` passes all ten changed production modules:
access catalog/admission, review access, verification access/models, artifact
workflow access, HTTP dependencies/catalog/artifacts and platform composition.
Ruff check/format passes those modules plus ten changed tests/fixture modules.
`git diff --check` passes.

From `ui/`, final `npm run typecheck` and
`node tests/run-api-contracts.mjs contracts` pass. Artifact contracts exercise the
production stream reader with independent hashes, exact-size/hash rejection,
overflow cancellation/unlocking, oversize refusal and bounded reference discovery.

The final browser asset build was:

```sh
NODE_ENV=production node tests/build-placement-browser.mjs /tmp/unifai-feature-browser-assets
```

Build completed in **4.70s** with 4,563 modules; the existing circular vendor chunk
and large-chunk warnings remain. Workspace script: `workspace-browser-CdfussQQ.js`.

## Actual App journey

Used the maintained runner documented in
[the coding skill procedure](../../.cursor/skills/debug-coding-elements/references/feature-browser.md),
dedicated Mongo/Redis, normal signed-cookie authentication, real HTTP/worker
execution and actual React components. External identity/settings, designer, CLI
executable and checker are controlled peers. No paid model calls were made.

Final root: `a61b9290-06c4-4d8a-96f2-18220f5e4d4f`, Feature revision 1.
The task was `Implement add(a, b) in answer.py`, with a criterion covering positive
and negative inputs. Through UI fields, selected review `release@1` actions
open/read/close; verification `engineering@1` create/read/run_check; artifact
engineering/verification-reports namespaces with read/publish and 65,536-byte bound.
All three leases were 3,600 seconds. Approved and started through the UI.

Observed an exact version-1 design review before coding; the compute workspace
directory did not yet exist. Approved its plan through shared review fields.
The controlled CLI's first source failed the independent Python check. Repair
restored source/report inputs into a different workspace; two coding start markers
were observed. Final review referenced the repaired artifact, which was inspected
and previewed before approval through the UI.

Root and children then reported completed. The actual result reports `verified`,
two Engineering attempts, accepted verification and the persisted final decision.
Exact inspected outputs:

| Output | Artifact ID | SHA-256 | Bytes |
| --- | --- | --- | --- |
| `answer.py` | `7de1168c19077d277209b16883838ee969100fc6ad2c499aa314a9dbb72e9249` | `ba1a531f581d2e6094e978ed6f7aca7a8d92eeb62c6e7ad73ee692f7f18bc772` | 32 |
| `tests.json` | `7d3d607a76a11a47019d92de10cedfb0863211e2bc3e7a37fc59af8918b5daa4` | `1908edf459bbd0608fbaf437666e7262d179bc54c585dbd556f27ff562b371f1` | 17 |

After completion, deleted only this fixture's compute `workspaces`, retained its
artifact store/API, reloaded the execution URL and reopened both artifact cards.
Fresh verified previews returned `def add(a, b):\n    return a + b\n` and
`{"failures": []}\n`. [Screenshot after compute deletion](assets/2026-11-05-feature-ui.jpg).
This was fresh browser retrieval, not an already-cached preview left visible.

Mongo showed three material reservations, zero unretired/cleanup-pending records
and zero remaining encrypted credential fields. No private credential JSON files
remained. Three one-byte `R` markers intentionally remained to fence stale writers.
The API log contained neither the synthetic provider token nor artifact workflow
token prefix. This bounded check is not proof of every possible leak path.

## Diagnostics, cleanup and remaining scope

An earlier manual run (`85e6d49a-8464-4e11-90e8-7d3665c08fd1`) expired at its original
60-second design deadline and truthfully completed `design_unsatisfied`, with no
coding starts. It was not resumed or retroactively approved. The old owned fixture
was stopped and cleaned before starting the final fresh fixture with 600-second
manual reviews. A temporary tab closed across the user conversation; the final
fixture remained live and was reopened without restarting its backend.

Initial catalog-test authoring used incorrect in-memory attribute/collection
names; these were corrected against actual adapters before the native gate.
Post-run cleanup probes initially counted a retained directory and then the
one-byte lock markers as credentials. Inspecting the delivery adapter confirmed
its intentional `R` retirement fences; the corrected material/fence check passed.
No credential cleanup behavior was weakened to satisfy those mistaken probes.

The App fixture logs unavailable optional Claude/deep-agent SDKs during reflective
discovery; neither is used here. Test identity lacks an MCP endpoint and discovery
can return 404. These are not accepted optional-provider/admin integrations.

Closed the test tab and stopped the owned runner once. API and identity logs both
confirm `Application shutdown complete`. The private cookie was removed, and the
runner confirmed database removal:
`unifai_feature_browser_1591811a5d064c5eac8626bd37c5a182`. Shared services were retained.

Next is bounded live coding with appropriate production/isolated verification.
Complete authoring/configuration browser coverage, cross-owner review attachment
policy, Session browser acceptance, occurrence/attempt views, canvas convergence,
durable unconfirmed intents, remote images/recovery/load and other full-goal items
remain open. This local controlled journey is not overall product acceptance.

## Source identity

[Focused source manifest](2026-11-05-feature-ui-source.json) records the exercised
application/adapters, clients, components, tests, fixture dependencies, screenshot
and built workspace script. This is not a full dependency or image manifest.
Source aggregate SHA-256: `71c5eeaff09972d26725a8b9fdf191f11d644c3bc4d617683b5b87514a739b53`.
