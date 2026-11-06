# Coding execution with restored repair evidence and saved-resource capture

Recorded 2026-11-05. This joins the production coding adapter to the approved-design
flow with actual generated files and executable checks, using controlled protocol
peers. It is backend integration proof, not live-model or whole-product acceptance.

## Capability and boundaries

- Domain `ArtifactFile` carries an immutable blob reference and contained relative
  destination. Coding inputs bound file count and reject canonical duplicate paths.
- Application `CodingOperation` selects its normal isolated/shared workspace, checks
  the complete prompt, prepares requested files there, then calls its coding-agent
  port. Missing, denied, failed or cancelled preparation cannot proceed to the agent.
- `ArtifactWorkspacePreparation` depends on artifact-transfer/workspace-file ports.
  The `providers/artifact_workspace` specification/factory constructs it from the
  existing store dependency. Codex has an optional ordinary provider reference;
  factories and construction handle the transitive closure without compiler branches.
- `coding_file_candidate@1` attaches the previous candidate at the output path and
  durable check reports under `.unifai/reports/<artifact_id>`. Original inputs survive
  approved-design context projection. A previous candidate replaces an original input
  at the same output path; conflicting report inputs fail before coding. Limits are
  enforced rather than silently dropping reports. Filesystem materialization retains
  its byte verification, scope checks, identical retry and no-overwrite guarantees.
- Preparation uses the actual coding invocation's workspace. It does not predict a
  different invocation's key or force shared mode. Publisher placement still requires
  access to that physical workspace; remote use needs the normal named environment
  bindings. Run Engine still owns dispatch and physical environment lifetimes.
- `POST /api/resources/snapshot` captures a human-selected source using the same
  `SavedResourceResolver` as graph authoring: observed revision, authorized closure,
  reread fences, protected credentials, normal bundle construction/digest. It enables
  backend Program bundle fields without another construction pipeline. Bearer-plus-
  cookie requests are refused; selected team scope remains authenticated ownership.
  This POST may create private configuration references; it is not a polling endpoint.

The native journey authors saved store/preparation/coding/publisher resources, captures
protected bundles, publishes the normal design/Engineering/feature composition, approves
the design, produces an initially incorrect implementation, executes independent checks,
restores source and report bytes into a different isolated coding workspace, repairs,
checks again, and accepts the exact final candidate. Artifact content survives compute
workspace deletion. Automatic root grants/material retire; reusable saved credentials
remain private configuration, not disposable workflow material.

## Source identity

[The focused manifest](2026-11-05-coding-repair-source.json) records 32 files, including
29 Python files and the production TypeScript client/runner scenario. Aggregate SHA-256:
`9f0713bf3ad8e81ca695cd5cb5917a1a70a573b8a3e164ed620bb878e12b9372`.
The worktree base HEAD is recorded there. This is not a complete dependency/image
manifest. No Run Engine source or remote images were changed.

## Verification

Shared and file-adapter gate:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture multi-agent/tests/adapters/mongo/test_resource_inspection.py \
  multi-agent/tests/adapters/test_artifact_filesystem.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**732 passed in 6.56s**, no skips or reported warnings. Includes preparation ordering,
missing provider/failure/cancellation, stream closure, workspace identity, canonical
input aliases, repair candidate/report attachments, protected source capture and
source-version/owner refusal, existing file integrity/scope/symlink contracts, and
shared domain/application/architecture coverage. It is not 732 newly added tests.

Native milestone gate, with UnifAI's dedicated services:

```sh
UNIFAI_TEST_MONGO_URI='mongodb://127.0.0.1:27018' \
UNIFAI_TEST_REDIS_URI='redis://127.0.0.1:6380/15' \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/coding/test_feature_workflow.py \
  multi-agent/tests/integration/coding/test_artifact_handoff.py \
  multi-agent/tests/integration/coding/test_codex_cli.py \
  multi-agent/tests/integration/coding/test_codex_registration.py \
  multi-agent/tests/integration/verification/test_coding_feature.py \
  multi-agent/tests/integration/verification/test_engineering_workflow.py \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**28 passed in 95.49s**, no skips or reported warnings, with local-service permission.
The two new thread/process cases prove saved encrypted coding credentials resolve
through protected snapshots, design approval precedes coding, independent executable
checks fail then pass, immutable report/source bytes reach a fresh repair workspace,
private CLI homes are collected, final human approval identifies the candidate, stored
source survives workspace deletion, and all three root capabilities/material retire.
They also refuse foreign snapshot capture and bearer-plus-cookie authoring.
Existing cases cover coding protocol/failure/timeout/cancellation, explicit plugin
registration, independent handoff/API restart and the earlier composed fixture paths.

Production UI client gate:

```sh
UNIFAI_TEST_MONGO_URI='mongodb://127.0.0.1:27018' \
UNIFAI_TEST_REDIS_URI='redis://127.0.0.1:6380/15' \
.venv/bin/python -m pytest \
  'multi-agent/tests/integration/ui/test_editor_client.py::test_existing_typescript_editor_clients_use_native_services[api]' \
  --ui-clients -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**1 passed in 5.20s**, no skips or reported warnings. The actual production snapshot
client captures the selected resource, refuses a stale source after editing, accepts
the new source and never receives the plaintext saved credential. This is API-client
execution, not a rendered UI or browser workflow. `npm run typecheck` in `ui/` passes.

Strict mypy passes for the 13 production Python files in the manifest (domain files,
coding contracts/operation, artifact preparation, construction snapshots, Engineering
coding/feature, Codex configuration/specification, artifact specs, HTTP dependencies/
resources and platform composition), using `--strict --follow-imports=silent` and
`MYPYPATH=multi-agent/lib:multi-agent/adapters:multi-agent/plugins:multi-agent`.
All 29 manifested Python files pass Ruff lint/format; `git diff --check` passes.
Counts overlap; do not add the gates to claim broader independent acceptance.

## Encountered failures and limits

The initial native attempt failed both cases during startup: explicit module loading
expected `ELEMENT_SPECIFICATIONS`, while built-in reflective discovery had hidden its
absence from Codex. The plugin now exports the normal tuple, and a real registry
composition test covers explicit installation alongside artifact dependencies. The
corrected targeted thread case passed, followed by the final 28-case gate above.
Intermediate application checks also exposed an old non-blob repair fixture and a
comparison between separately minted context identities; fixtures were corrected to
exercise the intended contract rather than weakening validation or ownership.

The CLI executable is a deterministic Codex protocol peer, not the OpenAI binary or
a paid model. It creates actual Python source; a separate check peer runs fixed
addition tests and publishes reports through the production check/artifact services.
That verifier executes controlled fixture source on an owned local process and keeps
provider observations in the API process. It is not a production isolated verifier,
proof of arbitrary untrusted-code safety, or provider recovery across API restart.
A real coding/production-verification journey still requires suitable verification.

No actual browser, live provider, Temporal restart/replay, Kubernetes/OpenShell,
load/fairness, new image or full cleanup/recovery matrix was exercised. Logical
workspace separation is not hostile same-user OS isolation. Shared destinations with
different bytes remain conflicts; uncertain invocation/worker recovery needs separate
acceptance. Generic repository/multi-file candidates remain possible through other
Programs; this single-file integration does not narrow the platform.

The visible UI still needs shared resource/bundle selection and schema-driven
configuration/invocation plus execution/review/artifact views. Source inspection
confirmed `ProgramConfiguration` uses JSON fallback for objects and `ProgramRun`
uses raw JSON inputs. Evolve those capabilities into the existing builder and shared
workbench rather than growing another standalone execution product.

Test-owned databases, sessions, APIs, CLI/verifier processes and private temporary
homes are cleaned by their fixture lifetimes. Dedicated services remain running.
Reusable configuration references are not collected as workflow credentials. Full
migration, production checks, remote/recovery/control and final acceptance remain
required by the active goal and target checklist.
