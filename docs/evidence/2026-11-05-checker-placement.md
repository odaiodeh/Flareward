# Current-image Kubernetes checker placement

Recorded 2026-11-05. Controlled-source placement and lifecycle checkpoint, not live
agent acceptance, hardened sandbox certification or adversarial verifier integrity.

## Behavior and ownership

- Reuses the signed-session/Mongo/Redis verifier setup, normal publication, pinned
  Program-check binding, graph operation placement and Run Engine Kubernetes runner.
  No production scheduler, compiler branch or environment manager was added.
- `prepared_verifier` accepts a deployment target in its infrastructure layer.
  Native and deployed tests share start/settle behavior through `ProgramCheckAPI`.
  SDK types remain in test infrastructure, outside application/domain contracts.
- The trusted API reads the exact bounded candidate through ArtifactService. The
  receiver gets inline source, not an artifact token, database/vault credential or
  all-root private directory. Check and comparison configuration remains pinned.
- Kubernetes creates a unique namespace and token-free receiver service account.
  The SDK observer records actual pod namespace/image/image ID, non-root setting,
  host access, secret/projected mounts and environment names without logging values.
  Descriptive namespace context is no longer read from a service-account mount.
- Passing/failing candidates assert actual non-root execution, the installed image
  marker, absence of a host-only file/token and no inherited UNIFAI child settings.
  A controlled three-second delay makes the real pod observable. This is fixture
  source, not model-produced or hostile source.
- Reports identify the exact candidate. Candidate owners cannot inspect the full
  verifier execution; its configured owner can. Completed check/report bytes survive
  API shutdown/restart after the receiver has been removed.
- Cancellation observes a dispatched receiver, cancels the plan and uses GET-only
  upkeep observation until the owned check closes. The exact execution is cancelled,
  no new evidence is recorded, and Jobs/pods are physically absent. Its six-second
  check bound permits SDK draining; cancellation acknowledgement is not preemption.
- An existing named-environment operation regression still constructs transitive
  dependencies, returns placed results and removes its retained receiver.

## Image and infrastructure identity

Dedicated `unifai-e2e` kind cluster, explicit kubeconfig/context; Kubernetes 1.36.1,
Docker server 29.1.3. Mongo `127.0.0.1:27018`, Redis `127.0.0.1:6380/15`.
Run Engine baseline `60393440efd3876cd6c81e0b013e8bf6d9167659`; no companion edits.

Final image: `unifai-receiver:python-checks-20261105-v2`.

- Docker index: `sha256:31470b71e2d38292f0e799392ce7901d3ffd881bea2a85ee03316fc3f510c11d`.
- Image config/CRI ID: `sha256:1d6ed9c01ffd16b7875c766777cbde10bbcc200f657938e44c2d4792a9cd87ee`.
- kind imported digest: `sha256:7826c2441f31ea6e6cec3bceede9b535bfca259fa1f5f9bba6d316033d07650b`.
- Source verifier matched all **1,389 installed Python files**, including receiver
  fixtures, and confirmed its selected retired paths absent. This is source matching,
  not an exhaustive dependency/SBOM or arbitrary dead-code audit.

```sh
docker build --build-context unifai="$PWD" --build-context run_engine="$PWD/../run-engine" --file multi-agent/tests/infra/Dockerfile.receiver --tag unifai-receiver:python-checks-20261105-v2 multi-agent/tests/infra
.venv/bin/python multi-agent/tests/infra/verify_images.py --image unifai-receiver:python-checks-20261105-v2
kind load docker-image unifai-receiver:python-checks-20261105-v2 --name unifai-e2e
```

## Verification

Final focused remote gate:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
UNIFAI_TEST_KUBECONFIG="$PWD/multi-agent/tests/infra/.state/kubeconfig" \
UNIFAI_TEST_K8S_CONTEXT=kind-unifai-e2e \
UNIFAI_TEST_K8S_IMAGE=unifai-receiver:python-checks-20261105-v2 \
.venv/bin/python -m pytest \
  multi-agent/tests/integration/deployment/test_program_checks.py \
  multi-agent/tests/integration/deployment/test_remote_programs.py \
  --platform-backends=k8s --platform-hosts=local \
  -k 'remote_python_verifier or cancelled_remote or named-environment' -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' \
  -o junit_family=legacy \
  --junitxml=multi-agent/tests/infra/.state/reports/20261105-python-checks-k8s-final.xml \
  -p no:cacheprovider
```

**4 passed, 9 deselected in 48.47s**, no skips or reported warnings. Deselection
intentionally bounds this checkpoint; it is not the complete remote matrix.
JUnit properties retain actual passing/failing receiver identities, copied into
the focused source manifest. Owned namespaces, Jobs and pods were absent after
fixture teardown. The owned preliminary image/tag was removed from Docker and kind;
the final v2 image remains available for reuse. Shared services remain running; no Docker restart,
global context switch or broad resource pruning occurred.

Shared native fixture regression: **12 passed in 110.11s** using
`integration/verification/test_program_checks.py`, the same Mongo/Redis URIs and
pytest options above (without deployment selection/JUnit). Covers thread/process
pass/fail, API reconstruction and plan/root cancellation. This ran before the final
Kubernetes namespace-probe correction, which those native paths do not exercise.

Final architecture gate: **16 passed in 3.34s**. Ruff check/format passes six changed
Python files. No production implementation or UI source changed, so unchanged
browser, provider and broad recovery suites were not repeated.

## Diagnosed failures and correction

The first two deployment cases failed their expected environment-name assertion:
the engine legitimately adds `RUNENGINE_PARAMS` for invocation transport. The test
now admits that exact additional name; its payload is never printed.

The first cancellation/retained regression gate had **1 pass, 1 failure, 11
deselected in 19.01s**. Cancellation passed; the old retained receiver probe expected
the namespace file from a service-account token volume. It now uses non-secret
fixture context while SDK observation supplies independent physical evidence.
The corrected installed fixture required the v2 image; the four-case gate above
follows that rebuild. The preliminary image was not treated as final-source proof.

## Limits and next acceptance

The candidate and comparator still share an OS identity. Expected answers omitted
from child stdin can remain reachable through same-UID parent process data, including
the receiver's invocation environment. Minimal child environment is insufficient
to certify adversarial verdict integrity. Separate trusted comparison from the
candidate execution authority using existing Program/operation boundaries.
The existing application `ProgramRuntime.invoke_element` port and its Run Engine
adapter already accept a separately selected operation placement and transport its
bundle/input rather than the enclosing Program configuration. Investigate and reuse
that path for the trusted comparator; no new execution subsystem is indicated.

The kind fixture has no enforcing deny-by-default egress policy, and the current
engine configuration does not express every hardened container security setting.
Non-root, token-free, no host mounts and physical cleanup prove narrower properties.
Do not execute live/untrusted candidates on the trusted host or claim hostile-code
isolation from this checkpoint. Verify a restricted candidate profile before live
Engineering acceptance. This is the next focused dependency, not a broad matrix.

OpenShell, Temporal/in-flight recovery, prompt interruption, private remote delivery,
full environment ownership/failure matrices, live coding and the final integrated
Engineering/browser journey remain open. Broader target obligations are unchanged.

## Source identity

[Focused source/image manifest](2026-11-05-checker-placement-source.json) records
the changed infrastructure/tests, referenced production contracts, engine baseline
and observed image identities. Its scope is explicit; it is not a full build manifest.
Source aggregate SHA-256: `4c43fd58b23eaf35b4a823259520b110b20fb70e798592cf498dbe919f6781b8`.
