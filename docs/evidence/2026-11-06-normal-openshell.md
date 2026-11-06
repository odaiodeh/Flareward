# Normal OpenShell execution, policy and live Codex smoke

Recorded 2026-11-06. Normal OpenShell is the selected feature-milestone profile.
Strict Landlock filesystem checks remain explicitly optional. This checkpoint
proves normal candidate transport/policy and a separate live coding workflow;
the complete live Engineering/verifier/review/browser journey remains unfinished.

## Companion infrastructure comparison

Inspected the current adjacent Run Engine checkout's E2E skill, shared policy
builder, canonical sandbox policy, gateway Compose/config, image Dockerfile and
native policy test. Relevant policy/helper/skill files were clean at baseline
`60393440efd3876cd6c81e0b013e8bf6d9167659`; no companion files or services changed.

- Its canonical image policy uses `best_effort`, filesystem/process settings and
  endpoint/binary network rules. Its helper loads the shared policy and selects
  relevant network groups; it does not require Landlock for normal agent tests.
- Its policy accounts for actual virtualenv and Python interpreter paths. Our
  selected Python paths passed actual allowed/denied traffic tests; broad provider
  or package-install permissions were not copied into the checker profile.
- UnifAI already has `execution_policy_files` and the production profile loader.
  Policies belong to approved execution profiles, separately from agent behavior,
  graph state and resource factories. The UI selects safe profile names. Operator
  policy files load at startup and become frozen execution configuration.
- The current supported network contract is host/port/executable, not arbitrary
  URL path/method filtering. The companion fixture's disabled TLS/anonymous gateway
  configuration was not adopted; UnifAI retains its own mTLS gateway on 8090.

## Actual failure and correction

The paused normal positive control executed candidate code successfully but could
not reach either allowed endpoint. A scoped credential-free comparison reproduced
the cause: inherited OpenShell proxy settings reached the owned HTTP probe; a child
with PATH alone failed `Network is unreachable`. Exactly one request was accepted.
Only transport variable names and controlled endpoint results were printed.

`mas_plugins.subprocesses.network_environment` now selects receiver-local proxy and
certificate settings. Python evaluation combines that allow-list with its minimal
PATH. The Codex adapter reuses the helper, preserving its prior transport behavior.
No SDK or OpenShell-specific branching was added to domain/application contracts.
Provider keys, workflow settings and `RUNENGINE_PARAMS` remain excluded from the
evaluator child. Proxy bindings retain their existing deployment transport scope;
they are not new application or human authority.

A real subprocess test verifies proxy/certificate preservation and exclusion of
synthetic provider/invocation material. Test and profile configuration now default
to normal OpenShell. Only `--strict-sandbox-filesystem` requests the stronger
Landlock/write-denial contract; its unsupported-host diagnosis remains in the
[earlier strict-mode record](2026-11-05-candidate-profile.md).

## Passing gates

- Shared application/domain/architecture and affected adapters: **783 passed in
  7.56s**. Focused evaluator/comparator/Codex protocol gate: **34 passed in 8.26s**.
  These overlapping gates are not an aggregate unique-test count.
- Strict mypy passes eight selected production modules with the maintained
  MYPYPATH and `--strict --follow-imports=silent`. Final Ruff check/format passes
  seven selected Python files. Updated diagnostic skills and diff checks pass.
- Normal OpenShell candidate gate: **3 passed in 25.40s**, no skips or reported
  warnings. Positive control reaches both endpoints; selective policy allows only
  the first, with zero requests at the second; offline allows neither. All cases
  require non-root execution, absence of a host-only file, filtered child environment,
  trusted comparison outside the receiver and owned physical cleanup.
- Authorized live Codex gate: **1 passed in 30.87s**, no skips or reported warnings.
  Two saved `codex_coding` resources execute sequentially in one externally owned
  sandbox, using `gpt-5.4-nano`, at most four commands and 60 seconds per operation.
  The first writes `calculation.py`; the second is instructed to run an addition
  assertion and writes `verified.txt`. The test reads actual source and `42` file
  evidence, requires command events, provider usage and a completed execution.

The live test proves the real CLI/model/shared-workspace path, not independent
trusted verification, concurrent agents, Human Review or complete ADLC acceptance.
It uses the existing receiver-only Codex sandbox mode inside the external OpenShell
sandbox; it does not prove nested Codex namespace isolation. Private provider data
is provisioned through the authenticated fixture, not images or portable definitions.
Published revision/execution data excluded the real key. A separate scoped audit
confirmed the owned API log also excluded it, without printing the value.

After the passing live gate, equivalent secrecy assertions were refined to fail
with a constant message and no credential-bearing pytest introspection, and to check
the API log in future runs. Paid calls were not repeated for that diagnostic-only
change. The post-run log audit checked the already completed execution's actual log.

## Commands and identity

Common environment: dedicated Mongo `mongodb://127.0.0.1:27018`, Redis
`redis://127.0.0.1:6380/15`, OpenShell `127.0.0.1:8090`, PKI at
`multi-agent/tests/infra/.state/openshell-20261105/pki`. The private live credential
was loaded by the opt-in fixture; no value is recorded here.

```sh
export UNIFAI_TEST_MONGO_URI=mongodb://127.0.0.1:27018
export UNIFAI_TEST_REDIS_URI=redis://127.0.0.1:6380/15
export UNIFAI_TEST_OPENSHELL_ENDPOINT=127.0.0.1:8090
export UNIFAI_TEST_OPENSHELL_PKI="$PWD/multi-agent/tests/infra/.state/openshell-20261105/pki"
UNIFAI_TEST_OPENSHELL_IMAGE=unifai-sandbox:normal-candidate-20261106 .venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_candidate_policies.py --platform-backends=openshell --platform-hosts=local -q -o addopts='--tb=short --strict-markers --import-mode=importlib' --junitxml=multi-agent/tests/infra/.state/reports/20261106-normal-candidate-policies-final.xml -p no:cacheprovider
UNIFAI_TEST_OPENSHELL_IMAGE=unifai-codex:normal-candidate-20261106 .venv/bin/python -m pytest multi-agent/tests/integration/deployment/test_codex_agents.py --live-coding --platform-backends=openshell --platform-hosts=local -q -o addopts='--tb=short --strict-markers --import-mode=importlib' --junitxml=multi-agent/tests/infra/.state/reports/20261106-live-codex-openshell.xml -p no:cacheprovider
```

Fresh receiver and Codex derivative were built once each for this coherent fix,
using the existing Dockerfiles/named source contexts. `verify_images.py --image`
matched **1,392 selected installed Python files per image** and selected retired-path
checks. Codex reports `codex-cli 0.166.0`.

- `unifai-sandbox:normal-candidate-20261106`:
  `sha256:68e9e322e20f9dcb8a72ba5dbe3e771afedfdf58599517a9cb2936748ba61fe0`.
- `unifai-codex:normal-candidate-20261106`:
  `sha256:933135af5f057f36744412de1585fcb45107ab94132d100ffd6715ad5def0aea`.

All test/diagnostic workspaces and containers from these images were absent at final
inspection. Shared gateway/databases/Temporal/kind and pre-existing images remain.
There was no Docker restart, context switch, companion-stack use or permission
change. The original private test credential remains in its ignored operator store.

## Remaining work

Next: replace the complete Engineering fixture's checker peer with the production
verifier Program, preserve saved-resource capture/repair/HITL/artifact behavior and
connect the same path through the shared UI. Then prove that full live journey and
unchanged published nested reuse. Current images do not establish full Temporal,
Kubernetes live coding, concurrent-agent, recovery or remote private-delivery matrices.
Broader controls, packaging and legacy retirement remain on the full target checklist.

[Focused manifest](2026-11-06-normal-openshell-source.json) identifies the changed
source/tests, compared companion files and images; it is not a full build/SBOM audit.
