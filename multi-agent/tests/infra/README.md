# Independent platform test infrastructure

Run commands from the UnifAI repository root. This stack belongs to UnifAI and
does not require Run Engine's Compose files, cluster, gateway, or local credentials.
Docker Desktop, `kind`, and `kubectl` are needed for the selected remote backends.
The dispatcher uses Python 3.14 and the committed Run Engine baseline described
in [development](../../../docs/program-platform-development.md). Rebuild receiver
images after SDK/source changes; do not apply archived prototype patches.

Use this setup/build/deployment workflow at planned milestones, not after every
edit. Reuse prepared services and batch related source changes before rebuilding
receivers or running Kubernetes/OpenShell and broad recovery/E2E suites. Use
focused checks during implementation. Follow the user's
[verification cadence](../../../docs/plan.md#verification-cadence);
unchanged policy/provider suites can wait for their own milestone. Current-image
evidence is still required when the selected remote gate runs.

```sh
.venv/bin/python -m pip install -e '../run-engine[kubernetes,openshell,temporal]'
.venv/bin/python -m pip install -e './multi-agent[e2e]'
export UNIFAI_E2E_STATE_DIR="$PWD/multi-agent/tests/infra/.state"
.venv/bin/python multi-agent/tests/infra/prepare.py --state-dir "$UNIFAI_E2E_STATE_DIR"
docker compose --file multi-agent/tests/infra/compose.yaml up -d --wait
export UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018
export UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15
export UNIFAI_TEST_TEMPORAL_ENDPOINT=127.0.0.1:7234
```

The default stack exposes Mongo on 27018, Redis on 6380, and Temporal on 7234,
all on loopback. Run broad regression and remote deployment gates sequentially on
memory-constrained Docker hosts. If both direct health checks and fixtures time
out, diagnose the dedicated stack before rerunning; raising test timeouts does
not establish correctness. Do not restart the user's whole Docker environment or
stop unrelated containers to recover this stack.
These ports differ from the usual development services. Core
ports can be overridden through `UNIFAI_E2E_{MONGO,REDIS,TEMPORAL}_PORT`; update
the corresponding test URIs too. Inspect existing resources before starting a
stack. Never stop another project's services to free a port.

## Transaction-capable catalog tests

Curated resource administration atomically updates resource/descriptor dependency
closures. It requires a Mongo replica set or transaction-capable sharded deployment;
standalone Mongo fails closed. The optional test profile adds a separate single-node
replica set without restarting the ordinary Mongo, Redis or Temporal services:

```sh
UNIFAI_E2E_STATE_DIR="$PWD/multi-agent/tests/infra/.state" docker compose --file multi-agent/tests/infra/compose.yaml --profile transactions up -d --wait --no-deps mongo-transactions
export UNIFAI_TEST_MONGO_TRANSACTION_URI='mongodb://127.0.0.1:27019/?directConnection=true'
```

Inspect existing container/port ownership first. The replica advertises its dedicated
network name; host-side tests use `directConnection=true`. The port can be overridden
with `UNIFAI_E2E_MONGO_TRANSACTION_PORT`. Its health check initializes only its own
replica and waits for a writable primary. This is not failover/load acceptance.
Ordinary Mongo remains on 27018 for the explicit unsupported-storage refusal test.
The transaction fixture and ordinary fixture share isolated database/client cleanup;
neither drops unrelated databases. Leaving this owned service healthy allows reuse
at later milestones. Stop only this service when intentionally retiring the fixture.

## Remote fixture material

The preparation command generates a fresh local CA, separate gateway/client/guest
certificates, and signing keys in the ignored state directory. Certificates expire
after seven days. Repeating preparation preserves existing keys; incomplete or
expired PKI is refused. For rotation, first confirm no active sandbox use, prepare
a fresh ignored state directory, then recreate only `gateway` with `--no-deps` and
that `UNIFAI_E2E_STATE_DIR`. Mongo, Redis and Temporal need no restart. Keep private
files out of commits, images, logs, and test results.
The state path must be absolute: the Docker driver binds generated state into
its sibling sandbox containers at the same path.

## Receiver images

The named build contexts copy runtime and application source explicitly; local
environment files and test PKI are excluded. Rebuild after changing installed
code or receiver fixtures. Use a fresh tag for parallel runs and update the image
settings consistently. The following tags match the checked-in gateway default.

```sh
docker build --build-context unifai="$PWD" --build-context run_engine="$PWD/../run-engine" --file multi-agent/tests/infra/Dockerfile.receiver --tag unifai-receiver:program-boundaries-20261103 multi-agent/tests/infra
docker build --build-arg RECEIVER_BASE=ghcr.io/nvidia/openshell-community/sandboxes/base:latest --build-arg RECEIVER_USER=sandbox --build-context unifai="$PWD" --build-context run_engine="$PWD/../run-engine" --file multi-agent/tests/infra/Dockerfile.receiver --tag unifai-sandbox:program-boundaries-20261103 multi-agent/tests/infra
.venv/bin/python multi-agent/tests/infra/verify_images.py
```

Kubernetes supplies Run Engine's receiver command explicitly. OpenShell uses its
base image's entrypoint to start the supervisor, then Run Engine invokes
`python -m runengine.invocation.receiver --output base64` inside the sandbox.
Preserve that base entrypoint. The image gives the receiving user ownership of
`/app`; the OpenShell supervisor validates workspace write access before startup.
OpenShell's invocation profile explicitly selects `/sandbox/.venv/bin` in `PATH`
and `/opt/test-fixtures` in `PYTHONPATH`, because its command environment differs
from the image-build environment. The receiver needs application/runtime packages,
not the Kubernetes or OpenShell dispatcher SDKs.

## Kubernetes

Create a dedicated cluster with a dedicated kubeconfig. These commands do not
switch the user's global Kubernetes context.

```sh
kind create cluster --name unifai-e2e --config multi-agent/tests/infra/kind.yaml --kubeconfig "$UNIFAI_E2E_STATE_DIR/kubeconfig"
kind load docker-image unifai-receiver:program-boundaries-20261103 --name unifai-e2e
export UNIFAI_TEST_KUBECONFIG="$UNIFAI_E2E_STATE_DIR/kubeconfig"
export UNIFAI_TEST_K8S_CONTEXT=kind-unifai-e2e
export UNIFAI_TEST_K8S_IMAGE=unifai-receiver:program-boundaries-20261103
```

The fixture uses an isolated SDK client and creates a unique namespace per case.
The test kubeconfig needs namespace and Job/pod lifecycle privileges. Receivers
do not call the Kubernetes API. Normal completion verifies that jobs and pods
are gone; teardown removes only the fixture's namespace and closes its client.
The fixture creates a dedicated receiver service account with token automount
disabled. Namespace display uses a non-secret setting; SDK observation independently
checks the actual pod. This fixture does not enforce deny-by-default egress or
certify a hardened hostile-code sandbox. The focused Python-check deployment cases
exercise controlled source; see [their checkpoint](../../../docs/evidence/2026-11-05-checker-placement.md).

## OpenShell

The pinned gateway and supervisor are version 0.0.103; the dispatcher SDK requires
0.0.104 or newer for the tested mTLS configuration. The localhost gateway requires
client certificates and owns sibling containers through the Docker socket. Use
this stack only with a development Docker daemon. It runs neither anonymous
authentication nor disabled TLS.

```sh
docker compose --file multi-agent/tests/infra/compose.yaml --profile openshell up -d
export UNIFAI_TEST_OPENSHELL_ENDPOINT=127.0.0.1:8090
export UNIFAI_TEST_OPENSHELL_IMAGE=unifai-sandbox:program-boundaries-20261103
export UNIFAI_TEST_OPENSHELL_PKI="$UNIFAI_E2E_STATE_DIR/pki"
```

Gateway bind, published port, and the supervisor callback must all use port 8090
with this Docker driver. A different host/container port mapping can let the SDK
health check pass while the supervisor cannot connect. Server certificates include
`host.openshell.internal` and localhost. Their AKI/SKI, constraints, usages, and
server SAN satisfy strict TLS verification. Do not bypass certificate checks to
diagnose a startup failure.

The fixture owns a unique workspace (OpenShell limits its name to 19 characters),
checks physical sandbox absence, and removes that workspace after draining work.
Run Engine owns invocation and retained-environment sandbox lifetimes. UnifAI
does not implement another sandbox manager.

Normal `test_candidate_policies.py` cases use the existing OpenShell profile and
test real network policy, non-root execution, host-file separation and private
environment exclusion. Optional `--strict-sandbox-filesystem` additionally requests
`hard_requirement` and checks filesystem denial. That option requires a Linux kernel
built with `CONFIG_SECURITY_LANDLOCK`; kernel version alone is insufficient. It is
not a prerequisite for normal OpenShell workflows. On this unsupported Docker Desktop
kernel, an explicitly strict receiver can briefly report ready before exiting.
See [the scoped diagnosis](../../../docs/evidence/2026-11-05-candidate-profile.md)
for current images, fresh gateway PKI state and required Linux-host acceptance.

## Run and diagnose

```sh
.venv/bin/python -m pytest multi-agent/tests --ignore=multi-agent/tests/integration/deployment/test_remote_programs.py --ignore=multi-agent/tests/integration/deployment/test_openshell_policies.py --ignore=multi-agent/tests/integration/deployment/test_codex_agents.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_remote_programs.py --platform-hosts=local,temporal --platform-backends=k8s,openshell -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_openshell_policies.py --platform-hosts=local,temporal --platform-backends=openshell -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

Select only prepared backends. An omitted remote selector skips remote cases;
an explicitly selected broken backend fails. Host and backend are independent.
The remote suite checks three actual receivers with transitive element construction,
ordinary versus retained lifetime, graph/application/graph ancestry, application
failure cleanup, explicit child borrowing with continued parent use, and Temporal
history replay. Evidence includes Linux, image
marker, namespace, hostname, dependencies, and execution identity. PID inequality
alone does not establish placement across container namespaces.

The verification helper compares installed Python content with the exact local
runtime, shared utilities, application, adapters, bootstrap/configuration, and
installed fixture sources. It reports image identities and matched-file counts;
use `--image` repeatedly or `--run-engine` when selecting different build inputs.
It runs temporary inspection containers with their entrypoint overridden and
removes them afterward; it does not alter the images' configured entrypoints.
The images include the native telemetry extra. The tracing deployment tests use
actual OTLP HTTP with host-local thread/process receivers. The remote private-
settings cases use a test-owned local protocol collector and synthetic keys.
Kubernetes projects private files through the engine's secret mounts. OpenShell
pre-provisions private files over authenticated SDK stdin before execution and
uses an exact collector host/port rule scoped to the receiving Python binaries.
Its custom policy retains filesystem, process, and Landlock setup, since a supplied
policy replaces the image policy. The kind namespace has no egress-denying policy;
these connectivity checks do not establish general network-policy enforcement.
The separate OpenShell policy module checks actual allow/deny behavior with
operator-file policies under both hosts and both environment lifetime modes.
It proves two local services reachable in a positive control, then checks that
restricting one endpoint prevents requests to that service while the other works.
Temporal histories replay and owned sandboxes/workspaces are removed. The policy
subset is host/port plus executable paths; URL-path/method filters are unsupported.

On failure inspect the owned API/worker logs in pytest's temporary directory,
the selected namespace, or the exact owned sandbox. Gateway health alone does not
prove supervisor startup, correct Python, or successful application execution.
Keep observation timeouts separate from terminal test results; poll a known live
test process rather than starting another copy. Report counts and warning policy.
No scenario here uses paid model calls. Remote approval and worker-loss recovery
require additional scenarios. The policy module does not establish full OpenShell
policy-schema support or enforcement on untested gateway/kernel versions.

## Cleanup

Let fixture teardown finish before shutting down services. Remove only resources
created for this run. Never use a global Docker prune or delete another cluster.

```sh
docker compose --file multi-agent/tests/infra/compose.yaml --profile openshell down
kind delete cluster --name unifai-e2e --kubeconfig "$UNIFAI_E2E_STATE_DIR/kubeconfig"
```

The ignored state directory retains keys and gateway state for reuse. Remove it
only after its stack and sandboxes have stopped and its contents are no longer
needed. A failed test may require targeted cleanup of its recorded namespace or
workspace; fixture resource identities, rather than name prefixes alone, establish
ownership.

## Optional live Codex coding workflow

Build the OpenShell receiver as above, then its dedicated derivative:

```sh
docker build --file multi-agent/tests/infra/Dockerfile.codex \
  --tag unifai-codex:program-boundaries-20261103 multi-agent/tests/infra
.venv/bin/python multi-agent/tests/infra/verify_images.py \
  --image unifai-codex:program-boundaries-20261103
export UNIFAI_TEST_OPENSHELL_IMAGE=unifai-codex:program-boundaries-20261103
kind load docker-image unifai-codex:program-boundaries-20261103 --name unifai-e2e
export UNIFAI_TEST_K8S_IMAGE=unifai-codex:program-boundaries-20261103
```

Supply `UNIFAI_TEST_OPENAI_API_KEY` privately, or save it in the ignored file
`multi-agent/tests/infra/.state/llm/UNIFAI_TEST_OPENAI_API_KEY` with directory mode
0700 and file mode 0600. Do not include the value in shell history, command-line
arguments, source files, Docker arguments or logs. The key alone enables no paid
tests; explicitly select:

```sh
.venv/bin/python -m pytest \
  multi-agent/tests/integration/deployment/test_codex_agents.py \
  --live-coding --platform-backends=k8s,openshell --platform-hosts=local,temporal \
  -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

Select only prepared backends; either `k8s` or `openshell` can also run alone.
Use the independent Mongo/Redis/Temporal and selected backend exports above. An
explicit live selection without its credential or backend fails. Without the
flag, the live scenario is skipped. Each backend/host case runs two small
`gpt-5.4-nano` turns with low reasoning effort, a 60-second timeout and at most four reported command
starts per turn. Time/command/output bounds do not impose a strict API spend cap.
The test creates saved coding resources, imports their references through a
blueprint, publishes a graph, shares one environment between writing and testing
steps, and reads the resulting files through a deterministic evidence element.
The receiver receives only the credential file path through
`UNIFAI_CODEX_API_KEY_FILE`; the CLI reads the key locally. Kubernetes uses the
existing fixture's private Secret mount and an engine-owned named environment.
Both coding agents and the deterministic file reader bind to that environment,
so they share a pod; completion checks physical pod/Job cleanup before deleting
the fixture's Secret and namespace. OpenShell uses a fixture-owned pre-provisioned
sandbox, a private API-key file and per-binary egress rules. Each step selects
the same pre-existing sandbox profile. Teardown deletes that sandbox and workspace.
It is deliberately not adopted as an owned named environment, which Run Engine
rejects. This does not verify automatic secret provisioning into newly created
OpenShell sandboxes. Both variants verify the receiver image and namespace, and
Temporal additionally replays history. The remote fixture explicitly selects
receiver-only `UNIFAI_CODEX_SANDBOX_MODE=danger-full-access` and relies on the
selected container's external isolation. The tested OpenShell host blocks nested
user namespaces and also enforces its filesystem and network policy. The kind
fixture does not enforce an egress policy or certify the nested CLI sandbox.
Production resource authors cannot request this override. The ordinary default remains
workspace-write with the bundled Bubblewrap helper available on PATH.

The image declares the existing `sandbox` account numerically (`998:998`) so
Kubernetes can enforce `runAsNonRoot`. If selecting a different base image, verify
its account and set the `CODEX_USER` build argument accordingly; do not disable
non-root validation to accommodate a named image user.

These are two distinct, sequential coding resources. This scenario does not
establish concurrent coding, CLI thread resumption, or automatic file sharing
between separate pods/sandboxes. Independent concurrent edits should use separate
workspace names; moving files between environments requires an explicit artifact
or shared-storage contract.
