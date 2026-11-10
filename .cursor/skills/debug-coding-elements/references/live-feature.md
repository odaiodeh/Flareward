# Bounded live feature acceptance

Use this for integrated real Codex/production-verifier journeys. The current fixture
uses `coding_designer@1` for real planning and a separate saved coding resource for
implementation; identity and automated HTTP review responses remain controlled.
For the actual-App variant below, enter review decisions through the UI. Full authoring/canvas acceptance, live Git/CI
delivery, Temporal/recovery and automatic remote private provisioning remain distinct
requirements. Follow existing user authorization and keep paid calls
explicit; availability of a credential does not authorize its use.

`support.live_feature` composes the normal Engineering API, saved resources and
published Programs. Coding uses the backend fixture's private provider binding;
artifact loading/publication stays on the trusted thread profile. Input and output
files cross the coding boundary as bounded verified content. The separately owned
Python verifier dispatches an evaluation operation with API-host evaluation disabled.
OpenShell evaluation is offline; Kubernetes pod isolation does not imply network
denial. Source/arguments are evaluator inputs; comparison and verification authority
remain outside that receiver.

Build matched receiver/Codex images at the coherent milestone and verify them with
`tests/infra/verify_images.py`. The source snapshot includes host test helpers as
well as runtime code. After a host-only helper correction, distinguish that older
full snapshot from a fresh `--platform` comparison of production/runtime sources;
never claim changed execution source matches an old image. Test profile helpers
must retain concrete SDK lumora.bootstrap.settings classes; a base `ExecutorConfig` can serialize with
warnings when placed in the operator settings union.

With current dedicated services, valid mTLS files, an explicitly selected image,
and an authorized private key binding:

```sh
LUMORA_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
LUMORA_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
LUMORA_TEST_OPENSHELL_ENDPOINT=127.0.0.1:8090 \
LUMORA_TEST_OPENSHELL_PKI=/absolute/current-state/pki \
LUMORA_TEST_OPENSHELL_IMAGE=lumora-codex:your-current-source-tag \
.venv/bin/python -m pytest \
  platform/tests/integration/deployment/test_live_feature.py \
  --live-coding --platform-backends=openshell --platform-hosts=local -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

The shared fixture selects `gpt-5.4-nano`, 60 seconds and four command events per
design/coding invocation; Feature Design permits one revision and Engineering one repair. These are finite execution bounds,
not a strict spending guarantee. Do not force extra paid repair attempts to duplicate
already-covered controlled failure scenarios. Record whether a live repair occurred.
The maintained HTTP test now runs Engineering revision 1 independently, then calls
that same unchanged revision through Feature. It permits two implementation tasks
(each with at most one repair) plus Feature's bounded planning, retires six
capabilities and retains both source/report pairs.
Keep the two roots' checks/reviews separate; successful reuse is not a reliability
rate. See [the reuse checkpoint](../../../../docs/evidence/2026-11-06-engineering-reuse.md).

Before design approval, only the design child should be observed. Inspect exact
source and the canonical `details` report before final acceptance. A candidate owner
must receive 403 on the private verifier execution. Three managed capabilities
must retire. `release_compute()` closes fixture-owned compute while the API remains
available: retrieve source and report again afterward. Teardown must retain no owned
receiver containers/workspaces, API processes, cookies or test database.

Real key assertions must use constant diagnostics; audit decoded source as well as
portable data and logs. Base64 is not redaction. Do not print the private binding,
stored cookies or provider command output during diagnosis. Preserve live handles
and frozen execution source until gates are terminal. The first scoped result is
in [the content-handoff evidence](../../../../docs/evidence/2026-11-06-content-handoff.md).

## Actual-App live journey

Build App assets with `ui/tests/build-workspace-browser.mjs`, then use the same
service/image variables above and the repository's test import paths:

```sh
PYTHONPATH=platform/src:platform/tests \
.venv/bin/python -m support.live_feature_browser \
  --assets /absolute/built-browser-assets --directory /tmp/unique-live-feature-run \
  --backend openshell --live-coding
```

This runner shares `feature_browser_session` with the controlled App fixture and
`live_feature` with the HTTP test. Use a fresh directory; its cookie file is private
and exclusive. Follow the printed login URL, choose Feature revision 1, fill inputs
and explicitly approve the required permissions. Reviews have 600-second manual
deadlines. Inspect the exact source before final approval, then its admitted report.

For authored-path acceptance, use the normal Resources and Programs editors to
create coding/designer/candidate resources and adopt their published revisions in
Design/Engineering. Use the provided `coding` profile for Codex and workspace
reading, `thread` for artifact operations, and the receiver's private key binding;
leave the resource API key empty. The live fixture supplies saved workspace input
preparation, artifact dependencies and trusted verifier policy. Keep the model,
timeout and command bounds no larger than the provided live resources.

Once terminal, write the owned root ID to the printed `release-compute` marker.
The runner checks the authenticated root/terminal identity and its pinned published
`coding_feature@1` implementation, including UI-authored roots, before collecting owned
compute. Wait for its removal message; reload the browser and freshly retrieve
both previews. A local marker is fixture control, not a product endpoint. Keep the
API live until this survival check finishes, then stop the same runner once and
verify database/cookie/API/receiver cleanup. Never delete shared Docker services.

Record UI steps, source/image identity, scopes and a saved screenshot as in
[the live browser checkpoint](../../../../docs/evidence/2026-11-06-live-feature-ui.md).
Prepublished Programs and controlled identity do not establish complete resource
authoring or Git/CI delivery. The [configured designer checkpoint](../../../../docs/evidence/2026-11-07-configurable-designer.md)
proves live planning. The [review-evidence checkpoint](../../../../docs/evidence/2026-11-07-review-evidence.md)
closed its earlier report-visibility gap: inspect both source and admitted report
in the pending review UI before approval. The
[controlled authoring checkpoint](../../../../docs/evidence/2026-11-08-feature-authoring.md)
records the authored path with a protocol executable; real-agent acceptance must
exercise that path with matched bundle-v2 receiver images.
