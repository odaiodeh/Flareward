# Trusted comparator and candidate evaluator separation

Recorded 2026-11-05. Closes the concrete receiver-parent expected-answer disclosure
path identified by the [placement checkpoint](2026-11-05-checker-placement.md).
Restricted-profile and live Engineering acceptance remain open.

## Contracts and ownership

- The normal `operations/python_function_evaluate` resource configures function
  and timeout. Its input contains an exact inline artifact and argument sets.
  Its output contains actual values or a typed evaluation failure, never a verdict.
  Normal specification, factory, builder and operation invocation paths are retained.
- `mas_plugins.testing.program` registers `python_function_check@1` through the
  existing backend Program registry. Its configuration captures an evaluator bundle,
  expected cases and explicit placement. It validates the exact candidate identity,
  invokes the evaluator through `ProgramRuntime.invoke_element`, then compares on
  the coordinator. No scheduler, engine adapter branch or Program category was added.
- Pure evaluation contracts live in the optional testing plugin. The evaluator
  imports no check-plan or verification-verdict contracts. The comparator depends
  on application runtime ports and portable data, without subprocess/SDK integration.
- Expected answers and check-plan metadata are not evaluator arguments. No artifact,
  database or verifier credential is delivered. Existing bounded inline source
  transport remains explicit: candidate data is stored in authorized history.
- Results are schema/count/byte validated, then JSON-type compared. A returned
  `verdict`, unknown fields, contradictory values/failure or malformed result cannot
  attest success. Deadline/output/execution errors are safe typed failures. Parent
  cancellation propagates rather than becoming an error verdict.
- The previous combined `python_function_check` operation and its factory/spec
  were removed. Existing fresh configurations must capture the evaluation operation
  and publish the backend verifier; no legacy aliases/readers were introduced.
- Native and remote tests share verifier setup, case data and public API behavior.
  A deployment target disables candidate evaluation on the trusted API host; only
  the receiver profile enables it. Native controlled-source fixtures retain their
  explicit local enablement.

## Verification

Shared application/domain/architecture and affected adapter gate:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain \
  multi-agent/tests/architecture multi-agent/tests/adapters/test_python_function_checks.py \
  multi-agent/tests/adapters/test_verification_settings.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**782 passed in 7.35s**. Application cases cover normal registration/invocation,
correct/incorrect values, bool versus integer, malformed/count/contradictory outputs,
receiver-supplied verdict refusal, exact candidate identity, cancellation and a
captured runtime boundary without expected answers or check metadata. Actual adapter
cases retain bounded output, private diagnostics, deadlines, process reaping and
directory collection; they no longer pretend evaluation itself is verification.

Native HTTP/Mongo/Redis and thread/process gate:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
.venv/bin/python -m pytest multi-agent/tests/integration/verification/test_program_checks.py -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
```

**12 passed in 108.12s**, including pinned operator ownership, passing/failing checks,
report survival after API restart, plan/root cancellation and bounded cleanup.
The later helper change disables host evaluation only when a deployment target is
supplied; that branch is exercised by the remote gate below, not these native cases.

Current-image Kubernetes gate:

```sh
UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018 \
UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15 \
UNIFAI_TEST_KUBECONFIG="$PWD/multi-agent/tests/infra/.state/kubeconfig" \
UNIFAI_TEST_K8S_CONTEXT=kind-unifai-e2e \
UNIFAI_TEST_K8S_IMAGE=unifai-receiver:python-boundary-20261105 \
.venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_program_checks.py \
  --platform-backends=k8s --platform-hosts=local -q \
  -o addopts='--tb=short --strict-markers --import-mode=importlib' \
  -o junit_family=legacy \
  --junitxml=multi-agent/tests/infra/.state/reports/20261105-python-boundary-k8s.xml \
  -p no:cacheprovider
```

**4 passed in 52.70s**, no skips or reported warnings. The candidate recovery probe
reads only its own receiver parent's actual `/proc/.../environ`, locates
`RUNENGINE_PARAMS`, validates the argument envelope and searches its JSON for expected
answers. An unpredictable synthetic answer exists only in coordinator configuration.
The exact report requires failed comparison with actual value `no comparator answer
in receiver`, rather than accepting an execution error as proof that the probe ran.
This is one concrete disclosure test, not universal hostile-code certification.

Other cases require passing/failing comparison, owner boundaries, report retrieval
after API restart, bounded cancellation without new evidence, and physical Job/pod
cleanup. SDK observation checks actual receiver identity, non-root configuration,
absence of host/secret/token mounts and exact declared environment names. The trusted
host has no candidate workspace. Final inspection found no owned namespaces, Jobs or
pods. Dedicated shared services and the final reusable image remain available.

Strict mypy passes all six testing-plugin modules with the maintained MYPYPATH and
`--strict --follow-imports=silent`. Ruff check/format passes thirteen selected Python
files; verification-skill validation and diff checks pass. The first focused gate
had **37 passes**; final counts above cover the coherent implementation. No UI,
provider, OpenShell or broad Temporal/recovery gate was repeated.

## Image and source identity

Image `unifai-receiver:python-boundary-20261105` was built once from frozen current
sources using the existing receiver Dockerfile/named contexts, verified using
`verify_images.py --image`, then loaded only into `unifai-e2e`.

- Docker index: `sha256:c945b6fde4f371e674c62299c344bfdeccbc9bcf03b5498fb7faccc55a4af7b6`.
- Config/CRI ID: `sha256:9df4962f54a0be30095c4248b7bf12b1f78b6699d786539cbe36eca3beb70982`.
- kind digest: `sha256:cf62d20f0b98258a0f775c61a93ddfe5dde7c3771a94c6f4bcb8a1388ccaf80e`.
- **1,391 installed Python files matched** current source; selected retired paths
  remained absent. This is not a full dependency/SBOM or dead-code audit.
- Companion baseline remains `60393440efd3876cd6c81e0b013e8bf6d9167659`; no engine edits.

[Focused source/image manifest](2026-11-05-checker-boundary-source.json) records
changed contracts, implementation/tests, referenced runtime port/adapter and actual
receiver observations. It is not a full build manifest.
Source aggregate SHA-256: `5b41d7105773b754041f0c8933121086805bfcf17e1243a8d2616ffd5b5ac803`.

## Remaining acceptance

Actual candidate isolation remains a deployment obligation. The kind fixture does
not enforce deny-by-default egress or every hardened container security option.
Native same-UID execution is suitable only for controlled fixtures. Use a restricted
candidate profile and verify its real filesystem/process/network policy before
live-source acceptance; the trusted comparator's placement must remain outside it.

Next is that narrow profile/live-coding integration, not a full infrastructure matrix.
Prompt invocation interruption, private remote capability delivery, full OpenShell/
Temporal recovery/ownership/failure coverage, real Engineering/browser acceptance,
unchanged nested reuse and all broader target requirements remain active.
