---
name: debug-coding-elements
description: Implement or debug UnifAI coding-agent CLI elements, remote images and policies, protected credentials, and explicit Kubernetes/OpenShell live workflow tests.
---

Read the [coding contract and ownership](../../../docs/program-platform-development.md#coding-agents-and-codex-cli)
and [test setup](../../../multi-agent/tests/infra/README.md#optional-live-codex-coding-workflow)
for this workflow.

Keep coding work behind `mas.application.coding.contracts.CodingAgent`; the shared
node owns state translation, and the vendor adapter owns subprocess details.
Placement and environment sharing remain program/runtime responsibilities. Do not
start another sandbox or engine from a coding element.

Verify flags against the pinned image's CLI, not only the desktop's version.
The npm launcher executes a native binary: OpenShell policy matches the actual
executable path. The Codex image installs it at `/usr/local/bin/codex` for an
architecture-independent policy path. Install its packaged `bwrap` and `rg`
helpers too; copying only the CLI binary can let model calls succeed while all
editing commands fail. Smoke-test namespace support in the actual sandbox before
paid calls. On the tested host, nested namespaces are denied, so the externally
isolated OpenShell fixture explicitly sets receiver-only
`UNIFAI_CODEX_SANDBOX_MODE=danger-full-access`. Keep workspace-write as the default
and never silently downgrade it or expose this choice in resource config. A supplied OpenShell policy replaces image
policy, including filesystem and process fields. Give Python receiver services
and Codex API calls separate endpoint/binary rules. Existing sandbox IDs retain
the policy of their external owner.

Use existing configuration-secret storage when the receiving environment can
reach it, or the operator-only `UNIFAI_CODEX_API_KEY_FILE` binding. The pinned
0.0.103 test runtime did not reach Mongo through native sockets; an HTTP endpoint
allow-list is not proof of database transport. Do not put a plaintext key in a
runner profile to work around that. Keep credential resolution at the
receiver, a private invocation-owned Codex home, and no credential argument or raw
CLI diagnostic in results. Generated shell environments must exclude the API key.
That exclusion does not isolate arbitrary hostile same-user processes; do not
claim it does. An interrupted subprocess acquisition must finish assigning the
owned handle before cleanup; terminate the process group and reap it before
propagating cancellation. TaskGroup errors need deliberate adapter translation.

The CLI can repair unsuccessful commands; a completed coding turn should not fail
merely because an intermediate command returned nonzero. Reject failed turns,
nonzero CLI exit, invalid events and incomplete results. Time, command-event and
output-byte bounds are not a strict dollar/token budget.

Run cheap subprocess and application tests before rebuilding images. After source
changes, refresh the receiver and derivative and run `verify_images.py` before
remote tests. Paid calls require user authorization and `--live-coding`; never
turn them on merely because a key exists. Verify files with the deterministic
workspace evidence step, rather than accepting a model's success claim. Separate
actual live proof, deterministic protocol coverage, external sandbox ownership,
and future automatic secret-mount provisioning in verification reports.
Pre-existing `sandbox_id` profiles can be reused directly by steps; they cannot
be adopted as owned named environments.

Select Kubernetes and OpenShell independently with `--platform-backends`; both
use the same saved-resource/blueprint/publication/coding scenario. Load the Codex
derivative into the dedicated kind cluster and select it through
`UNIFAI_TEST_K8S_IMAGE`. Kubernetes uses the shared backend fixture's private
Secret mount, with `UNIFAI_CODEX_API_KEY_FILE` derived from the receiver settings
directory. Bind both coding steps and the physical file reader to an engine-owned
named environment so they share one pod; repeated profile selection alone creates
separate invocation pods. Temporal retained environments need the worker's durable
environment journal. Check physical Job/pod removal before fixture Secret and
namespace teardown. OpenShell retains its distinct externally owned sandbox mode.
These cases use two sequential coding resources; do not describe them as proof of
concurrent editing, automatic cross-environment file transfer, or CLI conversation
resumption. Report the selected sandbox mode separately from outer placement.

Kubernetes rejects `runAsNonRoot` pods when the image declares a nonnumeric user,
even if that account is non-root. Verify the base's actual account with `id`; the
tested OpenShell base uses `998:998`, not `1000:1000`. The Codex derivative declares
that numeric identity through `CODEX_USER`. Preserve non-root enforcement instead
of weakening the pod security context. Rebuild with a fresh tag, reload only the
dedicated cluster and verify sources before rerunning a failed startup case.
