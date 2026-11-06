# Candidate profile prerequisite and prepared sandbox images

Historical strict-mode investigation. The user subsequently selected normal
OpenShell for the feature milestone. Current tests use that normal profile by default;
the stronger filesystem cases require `--strict-sandbox-filesystem`. The host gap
below does not block normal workflows and no replacement Linux runner is required.

Recorded 2026-11-05. Strict OpenShell candidate acceptance is **not achieved** on
this host. Investigation establishes a missing kernel capability, fresh authenticated
infrastructure and current-source receiver/Codex images. No model calls were made.

## Required policy gate

`integration/deployment/test_candidate_policies.py` runs the separated production
verifier through the signed API, Mongo/Redis and a normal OpenShell placement.
The trusted API cannot execute candidate Python. Operator JSON is loaded through
the existing production profile loader; application/domain contracts gain no SDKs.

Three controlled candidate cases require:

- Positive control: both owned HTTP endpoints reachable and `/app`/`/var/tmp` writes
  permitted explicitly, proving destinations and filesystem permissions are usable.
- Restricted policy: first endpoint works, second receives zero requests; writes
  to the same image paths are denied. The candidate still runs as non-root.
- Offline policy: neither endpoint receives a request and the filesystem restrictions
  remain. Comparison is outside the candidate receiver and checks exact outcomes.

All cases use `landlock.compatibility=hard_requirement`. They are not skipped or
weakened when explicitly selected on an unsupported OpenShell host. Each sandbox and
workspace is owned/scoped by existing infrastructure fixtures. No new scheduler or
environment manager was introduced.

Initial gate: **3 failed in 26.29s**. Owner-scoped execution diagnostics then showed
retryable infrastructure relay failure. A targeted positive-control run was
**1 failed, 2 deselected in 6.98s**, with `exec relay closed before the command reported
an exit status`. These are failed invocation/startup observations, not policy proof.

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
UNIFAI_TEST_OPENSHELL_ENDPOINT=127.0.0.1:8090 \
UNIFAI_TEST_OPENSHELL_PKI="$PWD/multi-agent/tests/infra/.state/openshell-20261105/pki" \
UNIFAI_TEST_OPENSHELL_IMAGE=unifai-sandbox:python-boundary-20261105 \
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_candidate_policies.py \
  --platform-backends=openshell --platform-hosts=local -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' \
  --junitxml=multi-agent/tests/infra/.state/reports/20261105-candidate-policies.xml \
  -p no:cacheprovider
```

## Authoritative diagnosis and cleanup

A credential-free `python -c` probe reproduced failure below UnifAI. It used a unique
diagnostic workspace and the same hard-requirement sandbox, with no provider/workflow
credentials. SDK readiness sometimes returned before supervisor restart. Exact
owned-container inspection showed restarting, exit code 1, no OOM and restart count 3.
Bounded supervisor stderr reported:

```text
Landlock unavailable in hard_requirement mode:
not implemented (kernel lacks CONFIG_SECURITY_LANDLOCK)
```

Kernel version alone therefore cannot establish support. The selected strict policy
correctly refuses to execute; changing it to best-effort would change the contract.
A Landlock-capable Linux runner is required. No local Lima/Colima/QEMU/Multipass/
Podman runner was installed or existing Lima directory found. The user was asked
for an existing runner or a dedicated-VM decision. Only `default` and `desktop-linux`
Docker contexts were listed. No answer or VM authorization is inferred from elapsed
time; Engineering/verifier integration can proceed independently.

All three test workspaces and diagnostic sandboxes were removed. An initial manual
diagnostic assumed synchronous deletion and stopped before removing its workspace;
the final authoritative sweep identified that exact workspace, waited for sandbox
deletion, removed it and confirmed no `diag-`/`uf-` workspace remained. No containers
from the new sandbox image remained. Cleanup acknowledgements alone were not treated
as proof. Provider SDK stderr also emitted gRPC fork/poll diagnostics; these are
distinct from the supervisor's permanent capability failure.

The [engine diagnostics request](../../integrations/run-engine-sandbox-capability-diagnostics-request.md)
records the opaque retryable relay classification. The host prerequisite is not a
UnifAI scheduling bug; no engine code or isolation requirement was changed.

## Gateway and certificate rotation

The existing dedicated gateway's client certificate expired at
`2026-11-05 13:22:18 UTC`. A first health probe used an incorrect HTTPS-prefixed SDK
address; correcting it to `127.0.0.1:8090` exposed the actual expiry. No active sandbox
containers were present before rotation. Existing old state and other services were
preserved. Preparation created new private state at
`multi-agent/tests/infra/.state/openshell-20261105`; its client certificate expires
`2026-11-12 21:40:39 UTC`.

```sh
.venv/bin/python multi-agent/tests/infra/prepare.py --state-dir "$PWD/multi-agent/tests/infra/.state/openshell-20261105"
UNIFAI_E2E_STATE_DIR="$PWD/multi-agent/tests/infra/.state/openshell-20261105" docker compose --file multi-agent/tests/infra/compose.yaml --profile openshell up -d --no-deps gateway
```

Only the dedicated gateway was recreated. mTLS health passed with gateway/supervisor
0.0.103; anonymous access and disabled TLS were not enabled. Mongo, Redis, Temporal,
the kind cluster and unrelated services were not restarted. Private keys/certificates
were not copied into images, evidence or portable definitions. The PKI refusal
message now directs gateway-only recreation; actual expired-state refusal was checked.

## Current-source preparation

```sh
docker build --build-arg RECEIVER_BASE=ghcr.io/nvidia/openshell-community/sandboxes/base:latest --build-arg RECEIVER_USER=sandbox --build-context unifai="$PWD" --build-context run_engine="$PWD/../run-engine" --file multi-agent/tests/infra/Dockerfile.receiver --tag unifai-sandbox:python-boundary-20261105 multi-agent/tests/infra
docker build --build-arg SANDBOX_IMAGE=unifai-sandbox:python-boundary-20261105 --file multi-agent/tests/infra/Dockerfile.codex --tag unifai-codex:python-boundary-20261105 multi-agent/tests/infra
.venv/bin/python multi-agent/tests/infra/verify_images.py --image unifai-sandbox:python-boundary-20261105 --image unifai-codex:python-boundary-20261105
```

Both images matched **1,391 installed Python files** and the verifier's selected
retired-path checks. The Codex image reports **codex-cli 0.166.0** and its bundled
`bubblewrap built for Codex` binary through credential-free `--version` commands.
This proves installation, not live coding or supervised execution acceptance.

- Sandbox index: `sha256:18971c0b7c03b49814c816dcc43ae6bcb34eb7bfd860bc6204aed6dead53f67e`.
- Codex index: `sha256:0687fa2e39ee2ec765f417efa2124bb7072983db5d1eac0604efcef908c745b0`.
- Run Engine remains `60393440efd3876cd6c81e0b013e8bf6d9167659` with no companion edits.

Ruff check/format passes the new policy module and preparation utility. Both updated
infrastructure/policy skills validate. Compact status/plan/index limits and diff checks
pass. Unchanged application/UI/native/Temporal suites were not repeated for this
deployment-only addition. The earlier [separated-checker evidence](2026-11-05-checker-boundary.md)
retains its passing scope; it does not establish this strict-profile acceptance.
Final collection finds all three cases. Diagnostics were then refined to show the
controlled report on mismatched outcomes; the unsupported-host gate was not repeated.

[Focused source/image manifest](2026-11-05-candidate-profile-source.json) records
selected test/infrastructure, policy and evaluator sources. Full Linux-host policy,
live Engineering, multi-Codex and broader remote/recovery acceptance remain required.
Source aggregate SHA-256: `8a187bd1d70c1f24c91c2fe778e713d674570ff3ab858aa0285fa8b8d218b28c`.
