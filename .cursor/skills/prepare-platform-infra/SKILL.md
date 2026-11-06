---
name: prepare-platform-infra
description: Prepare or diagnose UnifAI's independent Docker, kind, and certificate-authenticated OpenShell test infrastructure and receiver images.
---

# Prepare independent UnifAI test infrastructure

Use [the maintained infrastructure guide](../../../multi-agent/tests/infra/README.md)
for commands, paths, and variables. Inspect the selected fixture and existing
resources before allocating infrastructure. Use this repository's Compose,
Dockerfile, PKI preparation, and kind configuration. Run Engine remains the
execution provider; these files provide UnifAI's independent deployment.

Preserve these verified integration details:

- Use explicit source build contexts and install wheels for Run Engine, UnifAI,
  and shared utilities. Never copy `.env`, credential directories, or local PKI
  into an image. Receiver images need installed program/element modules; dispatcher
  SDKs belong at the dispatcher.
  After building, run `.venv/bin/python multi-agent/tests/infra/verify_images.py`
  to compare installed Python files with all selected source/build inputs and
  record exact image identities. This does not verify optional external services.
- OpenShell's base entrypoint starts its supervisor. Preserve it, give the sandbox
  identity write access to the workspace, and select the image's installed Python
  environment in the invocation profile. A successful image-build import does not
  prove an import under the supervisor's command environment.
- The pinned Docker driver's gateway bind, published port, and supervisor callback
  must agree. SDK health can pass while sandbox startup fails on a different port.
- Generate fresh local mTLS identities with `prepare.py`; preserve them on repeated
  setup. Strict verification needs complete certificate extensions and callback
  hostname SANs. Keep TLS and client authentication enabled. Do not print keys,
  JWTs, or broad container environments while diagnosing errors.
  Expired certificates require a fresh ignored state directory. Confirm no active
  sandbox use and recreate only the owned gateway service with `--no-deps`; other
  shared services do not need to restart. Preserve the old state while it has callers.
- Use the same absolute state path inside and outside the gateway because its
  Docker driver creates sibling bind mounts. Check actual supervisor logs when
  gateway health succeeds but a sandbox stays provisioning or enters error.
- Create kind with a dedicated kubeconfig and explicit context. Load the current
  receiver image into that exact cluster. Do not switch the global context.

Receiver-local settings and service reachability are separate contracts. In the
pinned OpenShell stack, an explicit sandbox policy replaces the image's filesystem
and process settings as well as its network rules. Preserve required setup and
scope service rules to the selected endpoint and receiver binaries. The configured
fixture accepts required endpoints separately from private file values; profile
payloads carry only references. A passing collector connection does not establish
general policy enforcement. Inspect the actual image policy and backend error
before broadening access or changing host routing.

Normal OpenShell is the current feature-milestone profile. Optional strict candidate
filesystem isolation requires Landlock support in the actual host kernel and explicit
`--strict-sandbox-filesystem` / `hard_requirement`. The recorded Docker Desktop kernel lacks
`CONFIG_SECURITY_LANDLOCK`, despite its recent version. A supervisor can report ready
briefly, then restart; the SDK may report only a closed exec relay. Inspect the exact
owned container state and supervisor stderr before retrying. Keep strict acceptance
pending for a capable Linux runner only when that extra guarantee is requested.
Normal-profile execution and network policy tests do not require a new Linux VM.
See [candidate-profile evidence](../../../docs/evidence/2026-11-05-candidate-profile.md).

For environment lifetime, use Run Engine ownership and explicit child imports.
The remote scenarios distinguish one-off receivers, shared files within an owned
scope, borrowed parent environments, and shorter child-owned scopes. A reused
hostname plus persisted receiver-local data proves more than PID comparisons.
Externally provisioned `sandbox_id` mode retains deployment ownership; fixture
cleanup follows API/worker draining. Keep production lifecycle behavior in the
engine, with SDK provisioning confined to deployment/test adapters.

Track resources created for the task. Temporary diagnostic workspaces and sandboxes
need recorded IDs and targeted cleanup. Test cleanup must confirm physical absence,
then remove the owned workspace/namespace and close SDK clients. Do not stop user
services, delete pre-existing clusters, or run broad Docker cleanup. Reuse prepared
resources while an authorized test matrix is active; do not replace image tags or
PKI underneath it.

After preparation, execute a real application invocation through UnifAI's public
API and selected backend. Distinguish gateway health, sandbox readiness, receiver
imports, program completion, replay, and cleanup; each proves a different boundary.
Record versions, images, selected endpoints, and limitations without claiming
production isolation or policy enforcement from deterministic execution tests.

If a public-image build stalls at registry metadata, check its exact process tree
and public registry connectivity before retrying. A waiting credential helper is
different from an unreachable registry. For confirmed helper blockage, stop only
the owned build/helper processes and use a temporary Docker configuration with
empty `auths`, no credential store, and the already observed daemon endpoint.
Do not read, replace or print the user's Docker credentials. Keep the temporary
configuration scoped to those public-image build commands.

Check daemon responsiveness separately from Desktop's reported running state and
container state cached by the API. A successful container inspection does not
prove that container exec, gateway TLS or the build is responsive. Preserve live
handles across observation timeouts; do not restart Docker Desktop or unrelated
services as an implicit test repair. Record preflight failures separately from
test results and keep current-source remote verification pending until it runs.
