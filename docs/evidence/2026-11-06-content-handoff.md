# Bounded content handoff for Engineering

Recorded 2026-11-06. Native and bounded live Local/OpenShell HTTP verification
passed. Actual live browser acceptance remains open. This record extends the
earlier production-checker integration rather than treating its old source
snapshot as evidence for these changes.

## Ownership and behavior

- `InlineContent` identifies bounded verified bytes without claiming publication.
  `InlineFile` adds a contained destination path. Published `InlineArtifact`
  preserves its distinct storage reference and shares exact-byte verification.
- Normal registered operations load artifact content, read contained workspace
  content and publish file content. Their specs/factories use the existing builder
  and invocation pipeline; no new scheduler or environment manager is introduced.
- `InlineWorkspacePreparation` needs only the workspace-file port. It refuses
  unresolved artifact references before writing anything and receives no store
  credential. The existing streaming preparation path remains available.
- Workspace materialization now requires only `ContentIdentity`; a storage ID was
  unnecessary for its integrity/path/atomicity responsibility.
- The optional file-candidate Program loads repair/source/report inputs and
  publishes output on its explicit artifact placement. Coding and workspace reads
  use the separately configured coding placement. It validates loaded identities,
  exported paths and publication hashes/sizes before returning a blob candidate.
- Individual content values and aggregate coding inline inputs are bounded to
  1 MiB. Registered transfers default to 65,536 bytes; the workflow capability
  supplies its separate storage-access bound. Inline source is portable data and
  can appear in execution history; encoding is not encryption or secret redaction.
- This is one file deliverable implementation. Generic Engineering still accepts
  configured verification subjects. Git or other candidate producers do not need
  to implement this transport or change the core runtime.

## Native verification

Focused application/domain gate: **46 passed in 0.18s**. It covers changed/oversize
content, scoped publication identity, stream closure/cancellation, credential-free
preparation, exact candidate binding and typed operation behavior.

Shared application/domain/architecture gate: **778 passed in 7.11s**.
Strict mypy (`--strict --follow-imports=silent`) passes ten affected production
modules: domain artifacts/files, coding contracts, artifact content/stream/
preparation/publication operations, filesystem and registration adapters, and the
Engineering file coordinator.

Dedicated native gate:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/coding/test_artifact_handoff.py \
  multi-agent/tests/integration/coding/test_feature_workflow.py \
  multi-agent/tests/integration/coding/test_workspace_files.py \
  multi-agent/tests/integration/coding/test_codex_registration.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' \
  --junitxml=/tmp/unifai-bounded-handoff-native.xml -p no:cacheprovider
```

**14 passed in 49.72s.** Production coding/transfer, actual POSIX path and atomic
materialization guarantees, publication/registration and the approval/check/repair
journey run on actual native services. CLI/model output is controlled.

After migrating the shared resource authoring helper to `CodexConfig` and extracting
workflow permissions, reran only `test_feature_workflow.py` with the same service
URIs/options: **2 passed in 30.45s**. Both thread/process flows preserve saved
encrypted resources, production verification, repaired source/report restoration,
output retention and three-purpose credential retirement.

## Bounded live HTTP acceptance

The explicitly opt-in `deployment/test_live_feature.py` uses real Codex in the
backend fixture's owned environment, trusted local artifact operations and an
independently dispatched Python evaluator. API-host evaluation is disabled.
OpenShell evaluation uses an offline policy; Kubernetes uses its existing isolated
pod configuration without claiming network denial. The provider credential uses
the established private receiver binding and is not a resource configuration.

The test retains separate design/final decisions, exact reports and private
verifier-owner boundaries. It explicitly releases fixture-owned compute before
retrieving source/reports again through the still-live authenticated API.
Design generation and human responses are controlled in this HTTP scenario.
Actual browser acceptance and automatic private receiver delivery remain separate.

Matched builds used the maintained receiver and pinned Codex Dockerfiles:

- `unifai-sandbox:content-handoff-20261106`:
  `sha256:cd0a96ee7401c3813069381ccbbefe6e583e535fcb556f278da4b295ef994fdf`.
- `unifai-codex:content-handoff-20261106`:
  `sha256:94fbdffd48efff2e39a1098fcf5b150d80296d377a5a8e72bddf7cb4bb10ccaa`.

`verify_images.py` matched **1,395 installed Python files per image**, including
then-current test fixtures, and confirmed retired paths absent. Run Engine stayed
at `60393440efd3876cd6c81e0b013e8bf6d9167659`; no companion changes were made.

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
UNIFAI_TEST_OPENSHELL_ENDPOINT=127.0.0.1:8090 \
UNIFAI_TEST_OPENSHELL_PKI="$PWD/multi-agent/tests/infra/.state/openshell-20261105/pki" \
UNIFAI_TEST_OPENSHELL_IMAGE=unifai-codex:content-handoff-20261106 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/deployment/test_live_feature.py \
  --live-coding --platform-backends=openshell --platform-hosts=local -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' \
  --junitxml=multi-agent/tests/infra/.state/reports/20261106-live-feature-openshell.xml \
  -p no:cacheprovider
```

**1 passed in 34.59s**, with one fixture serialization warning described below.
Model: `gpt-5.4-nano`, pinned CLI 0.166.0, four command events and 60 seconds per
attempt, with at most one repair. These are not strict dollar/token limits.

Root `de8cee36144440debe7876d8692085f8` completed `verified` after **one attempt**.
The candidate-owner private-verifier inspection was denied; the verifier owner
observed the pinned completed Program. The independently produced report records
three passing cases. Source and report were freshly retrieved through authenticated
HTTP after fixture compute release. All three root capabilities retired and private
credential files disappeared. No API-host source workspace existed. The test's
decoded-source/public-data/log audit found no provider key. A subsequent Docker
query found no live or stopped containers derived from the milestone Codex image.

| Output | Artifact ID | SHA-256 | Bytes |
| --- | --- | --- | --- |
| Candidate | `d2be1a525887243d0a5757c1d0288517eb69e2d6b71f3bde8cd354ad21beef58` | `4ba6c8881970c15c36e02f5784c3ea2713b519d51b02afdaf39c13e3e95189da` | 33 |
| Report | `dc8c8591a3e115c3164e37f791c4d2de7a9b878543e6207fcaed0aec263e4567` | `9d3a88f9e65d538f8b9b482e3ac5eb207539d50d1ca9e618c3992b0596888d26` | 145 |

The warning came from the host-only test helper constructing a base `ExecutorConfig`
instead of retaining its concrete OpenShell class. The helper now validates the
concrete class and rejects host evaluation profiles. **3 focused tests passed in
0.72s**, including warning-free operator-settings serialization for OpenShell/K8s.
A separate diagnostic confirmed identical serialized profile data before/after this
correction. The paid gate was not repeated solely for this fixture warning.
Production/runtime sources did not change after the live gate; the full installed
fixture snapshot above precedes this helper correction.
Fresh `verify_images.py --platform` checks match **1,283 current production/runtime
Python files per image**, with retired paths absent, after the fixture correction.

The [focused manifest](2026-11-06-content-handoff-source.json) records 25 selected
files as exercised, images and result identity. Aggregate:
`5e2faffc4167cfb44789c340dc36aae220258d6d98528ea80b7847de9f800c6b`.
The manifest distinguishes later fixture corrections from that tested snapshot.

Next is actual browser-to-API-to-worker proof of the live journey. Controlled
native repair remains the repair proof; this live run needed no repair. Full Git/
CI delivery, unchanged nested reuse, configurable completion alternatives,
Temporal/recovery, the broader remote matrix and remaining target requirements
are not completed by this single scoped journey.
