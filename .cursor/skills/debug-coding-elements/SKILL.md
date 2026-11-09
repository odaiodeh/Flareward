---
name: debug-coding-elements
description: Implement or debug Flareward coding-agent CLI elements, remote images and policies, protected credentials, and explicit Kubernetes/OpenShell live workflow tests.
---

Read the [coding contract and ownership](../../../docs/program-platform-development.md#coding-agents-and-codex-cli)
and [test setup](../../../platform/tests/infra/README.md#optional-live-codex-coding-workflow)
for this workflow.
For actual App capability consent, approval-gated coding/repair, final review and
artifact retrieval, use the [controlled browser procedure](references/feature-browser.md).
It exercises the production CLI adapter with a controlled executable, not a live model.
For bounded real-agent HTTP or actual-App journeys with independent remote
evaluation, use [the live feature procedure](references/live-feature.md). Keep
live browser execution proof distinct from full authoring/canvas acceptance.
For typed Git output, admitted revision inspection and file/Git completion choices,
use [the Git candidate procedure](references/git-candidates.md). Its native gate
uses controlled coding with actual Git publication and source checks.
For production planning, install `plugins.adlc.programs.designer` and configure
`coding_designer@1` through saved operation/loader bundles and explicit placement.
It validates JSON proposals; the existing Design coordinator owns review/revision.
The [designer checkpoint](../../../docs/evidence/2026-11-07-configurable-designer.md)
records native and actual-App designer proof. The
[review-evidence checkpoint](../../../docs/evidence/2026-11-07-review-evidence.md)
adds source/report inspection before approval. `engineering@3` now publishes named
completion choices with candidate schemas and frozen check/verifier/report requirements.
`EngineeringReviewSubject` (`engineering-review@2`) binds that name to exact evidence;
preserve fingerprint validation and substitution tests. See
[completion contracts](../../../docs/evidence/2026-11-08-completion-contracts.md).
Keep generic review/inspection independent of Engineering; reviewer assignment is
not another owner's artifact authority.

Keep coding work behind `flareward.elements.coding.contracts.CodingAgent`; `CodingOperation` owns typed input/result translation, and the outer
`plugins.codex` adapter owns subprocess details. Register `CodexSpec`
through the existing catalog/factory/builder path as `operations/codex_coding`;
do not restore the removed Codex node. Graphs use `OperationStep` bindings and
custom programs use `ProgramRuntime.invoke_element`. The application coding
contract must not import graph state or plugin modules.
Placement and environment sharing remain program/runtime responsibilities. Do not
start another sandbox or engine from a coding element.

The [normal OpenShell checkpoint](../../../docs/evidence/2026-11-06-normal-openshell.md)
has current-image policy proof and a live smoke with two sequential saved Codex
resources sharing one externally owned sandbox. It is not concurrent-agent,
Temporal or complete live Engineering/review acceptance. Preserve approved injected
proxy/TLS settings through the shared outer `network_environment` helper; exclude
unrelated application/provider material. Live secret assertions must fail with a
constant message without pytest introspection printing credential or leaked data.

For Engineering file candidates, install `plugins.adlc.programs.coding` and
exercise `integration/coding/test_artifact_handoff.py`. It covers production coding
and publication with a protocol executable, not live-agent or trusted-check acceptance.
Registered input/result models need installed importable identities: a generated
Pydantic specialization such as `EngineeringWork[CodingInput]` has a schema but no
resolvable distributed function path. Declare a named concrete subclass (as in
`CodingFileWork`) and verify actual thread/process invocation rather than replacing
the typed schema with unstructured JSON. Shared profile selection alone does not
share files on isolated receivers; use an explicit named environment binding.

For restored repair inputs, use `integration/coding/test_feature_workflow.py`.
Its file-candidate Program configures loader, reader and publisher bundles with
separate artifact/coding placement. Configure `providers/inline_workspace` as the
coding resource's `workspace_preparation`; the candidate receives bounded content
without an artifact-store credential. Storage authority stays on trusted artifact
placement. The streaming `artifact_workspace` provider remains available for
appropriately trusted receivers. `CodingOperation`
stages `CodingInput.files` in its actual owned workspace before calling the agent.
Do not work around isolated invocation keys by silently enabling shared workspaces.
File materialization preserves identical retries and refuses different existing
bytes. Repairs need read access to `verification-reports` as well as candidate
artifacts. The native case captures saved encrypted resources through
`POST /api/resources/snapshot`, exercises the CLI protocol and actual executable
fixture checks, and verifies restoration in a fresh workspace. The native feature
and browser fixtures now use the normal production API and `program@1` checker,
pinned to a separately owned published Python verifier. `CheckProgramSetup`
shares publication/pinning with the standalone checker fixture. The candidate
owner can inspect admitted evidence but cannot inspect the private verifier run.
Local execution is explicitly enabled only for controlled source; this is not
hostile-code isolation or live-model acceptance. The transient Python checker
peer was removed; do not restore it to bypass production verification.
Explicit `element_modules` installation requires `ELEMENT_SPECIFICATIONS`; a
spec discovered reflectively may otherwise hide a missing module export.

Verify flags against the pinned image's CLI, not only the desktop's version.
The npm launcher executes a native binary: OpenShell policy matches the actual
executable path. The Codex image installs it at `/usr/local/bin/codex` for an
architecture-independent policy path. Install its packaged `bwrap` and `rg`
helpers too; copying only the CLI binary can let model calls succeed while all
editing commands fail. Smoke-test namespace support in the actual sandbox before
paid calls. On the tested host, nested namespaces are denied, so the externally
isolated OpenShell fixture explicitly sets receiver-only
`FLAREWARD_CODEX_SANDBOX_MODE=danger-full-access`. Keep workspace-write as the default
and never silently downgrade it or expose this choice in resource flareward.bootstrap.settings. A supplied OpenShell policy replaces image
policy, including filesystem and process fields. Give Python receiver services
and Codex API calls separate endpoint/binary rules. Existing sandbox IDs retain
the policy of their external owner.

Use existing configuration-secret storage when the receiving environment can
reach it, or the operator-only `FLAREWARD_CODEX_API_KEY_FILE` binding. The pinned
0.0.103 test runtime did not reach Mongo through native sockets; an HTTP endpoint
allow-list is not proof of database transport. Do not put a plaintext key in a
runner profile to work around that. Keep credential resolution at the
receiver, a private invocation-owned Codex home, and no credential argument or raw
CLI diagnostic in results. Generated shell environments must exclude the API key.
That exclusion does not isolate arbitrary hostile same-user processes; do not
claim it does. An interrupted subprocess acquisition must finish assigning the
owned handle before cleanup; terminate the process group and reap it before
propagating cancellation. TaskGroup errors need deliberate adapter translation:
preserve a single adapter-owned safe coding error; unknown/mixed failures must not
expose raw events or stderr. Native CLI tests check the reason as well as redaction.

The CLI can repair unsuccessful commands; a completed coding turn should not fail
merely because an intermediate command returned nonzero. Reject failed turns,
nonzero CLI exit, invalid events and incomplete results. Time, command-event and
output-byte bounds are not a strict dollar/token budget.

Run cheap subprocess and application tests before rebuilding images. Custom
program dispatch must send only the invoked bundle's transitive specification
closure; shipping the whole catalog forces unrelated optional SDK imports on
minimal receivers. The remote operation matrix exercises this boundary. After source
changes, refresh the receiver and derivative and run `verify_images.py` before
remote tests. Paid calls require user authorization and `--live-coding`; never
turn them on merely because a key exists. Verify files with the deterministic
workspace evidence step, rather than accepting a model's success claim. Separate
actual live proof, deterministic protocol coverage, external sandbox ownership,
and future automatic secret-mount provisioning in verification reports.
Pre-existing `sandbox_id` profiles can be reused directly by steps; they cannot
be adopted as owned named environments.

Select Kubernetes and OpenShell independently with `--platform-backends`; both
use the same saved-operation-resource/publication/coding scenario. Load the Codex
derivative into the dedicated kind cluster and select it through
`FLAREWARD_TEST_K8S_IMAGE`. Kubernetes uses the shared backend fixture's private
Secret mount, with `FLAREWARD_CODEX_API_KEY_FILE` derived from the receiver settings
directory. Bind both coding steps and the physical file reader to an engine-owned
named environment so they share one pod; repeated profile selection alone creates
separate invocation pods. Temporal retained environments need the worker's durable
environment journal. Check physical Job/pod removal before fixture Secret and
namespace teardown. OpenShell retains its distinct externally owned sandbox mode.
The live cases use sequential coding resources with explicit
`workspace_mode=shared`; do not describe them as proof of concurrent editing,
automatic cross-environment file transfer, or CLI conversation resumption.
Deterministic local graph/code cases exercise the real CLI adapter with a protocol
stub, including overlapping calls with default isolated workspaces and separate
private homes. They make no model calls and do not establish paid remote behavior. Report the selected sandbox mode separately from outer placement.

Kubernetes rejects `runAsNonRoot` pods when the image declares a nonnumeric user,
even if that account is non-root. Verify the base's actual account with `id`; the
tested OpenShell base uses `998:998`, not `1000:1000`. The Codex derivative declares
that numeric identity through `CODEX_USER`. Preserve non-root enforcement instead
of weakening the pod security context. Rebuild with a fresh tag, reload only the
dedicated cluster and verify sources before rerunning a failed startup case.
