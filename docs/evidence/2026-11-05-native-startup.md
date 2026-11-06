# Canonical service startup and installed-image checkpoint

The installed package now exposes only `mas-platform`, with `serve` and `worker`.
The obsolete `mas` entrypoint, Flask/Gunicorn CLI, WSGI/dev wrappers, old worker
module launcher, legacy demonstration main, shell role dispatcher and backup
Dockerfile are removed. Refreshing the editable install removes its old console
script; cold-import tests reject replaced launchers and legacy startup imports.
Residual old service/runner bodies still require behavior migration and retirement.

The main Dockerfile uses Python 3.14, the approved Run Engine source as a named
context, deliberate API/worker extras and UID/GID 1000. It copies source explicitly
with a Dockerfile-specific context allowlist, not local environments, test fixtures
or private bindings. Operator-specific clients/certificates and optional capability
extras are explicit image/deployment inputs. API and worker use the same image.

The API chart passes native `serve` arguments and probes `/api/health/health`.
The worker chart passes `worker`, removes its fictitious HTTP service/port and
process-name probes. Shared settings use canonical `UNIFAI_*` names. The ingress
template now has a valid YAML filename. No cluster deployment was performed.
Worker poller-based automated rollout readiness is still missing; ordinary process
restart is not readiness. The examples require actual environment service addresses,
shared private configuration and the same host/namespace/queue on API and worker.

Both Podman CI build functions pass the approved `RUN_ENGINE_SOURCE` named context
and explicit ignore file for this component. Missing source configuration fails;
Jenkins/Podman execution has not been verified. Documentation names these inputs.

## Checks and outcomes

- Final shared-layer gate: 639 application/domain/architecture tests passed (6.09s).
- Final real CLI gate: two Local thread/process cases passed (5.04s), exercising
  loopback HTTP, publication, graph execution and graceful shutdown after the editable
  metadata refresh. An earlier run overlapped metadata installation and is not the
  final frozen-checkpoint proof.
- Provider async contracts: 18 passed (0.91s), no paid calls. A discovery/architecture
  gate also passed 27 tests; counts overlap the shared-layer gate.
- Both Helm charts lint and render with Helm v3.17.3. Only the optional icon advice
  remains. Rendered YAML was parsed and checked for native arguments, API probe
  paths, absent interactive TTY/ROLE settings and absent worker HTTP service/probes.
- Ruff lint/format passed on the five changed Python test/provider files. The
  existing test skill was updated and passed its frontmatter validator.

The isolated-build dependency refresh succeeded after the first no-build-isolation
attempt found no local setuptools backend. This changed package metadata/scripts,
not provider dependencies. The build used a clean approved Run Engine checkout at
`60393440efd3876cd6c81e0b013e8bf6d9167659`; no companion source changed.

From the repository root:

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/domain multi-agent/tests/architecture -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
.venv/bin/python -m pytest multi-agent/tests/integration/http/test_cli.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
.venv/bin/python -m pytest multi-agent/tests/adapters/test_async_llms.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib' -p no:cacheprovider
docker build --build-context run_engine=../run-engine -f multi-agent/Dockerfile -t unifai-platform:startup-20261105 .
.venv/bin/python multi-agent/tests/infra/verify_images.py --platform --image unifai-platform:startup-20261105
docker run --rm -i --entrypoint python unifai-platform:startup-20261105 - < multi-agent/tests/infra/smoke_platform.py
```

The actual image identity is
`sha256:1da5550a245d99e42a228540368d825210f025467ce553ddd48d5d24d17792a8`.
Its base resolved to
`python:3.14-slim@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d`.
Build pip's root-user warning concerns its installation layer; runtime uses UID 1000.

The common verifier matched 1,259 installed package files and checked absent retired
namespaces/console scripts. An additional streamed source-hash check matched 1,278
Python files including the residual old adapter package. The build-source manifest
contains 1,286 source/package inputs; this does not mean all those modules were
executed. [Build-source identity](2026-11-05-native-startup-source.json) aggregate:
`979a3064f21706ec9a61d816938a58ac0ca15d73e269e24ad13b9b4ecf3f4dd5`.
The separate [gate/deployment manifest](2026-11-05-native-startup-gates.json) records
verification sources, charts, CI changes and explicit deleted paths.

## Clean-image failures resolved

The first image built but failed API startup: another dependency installed the
`google` namespace without optional `google.genai`. `from google import genai`
raised ImportError rather than the expected missing-module signal. The adapter now
imports the fully qualified SDK module; discovery still rejects broken installed
SDKs instead of swallowing arbitrary ImportError. The image was rebuilt before the
final checks. Its deliberate missing extras produce unavailable-adapter warnings.

The first successful HTTP image run failed a test-only exit assertion because its
Uvicorn version preserves SIGTERM after graceful shutdown. The reusable smoke script
uses the same `(0, -SIGTERM)` convention as the existing subprocess harness and
requires the shutdown-complete marker. Local mode passed after that correction.

## Separate image worker proof

Two temporary containers used `unifai-e2e_default`, without mounts or published
ports, and one unique `unifai-startup-<uuid>` task queue. The worker ran the actual
image's `worker` entrypoint. The API smoke script's `UNIFAI_SMOKE_HOST` selected
Temporal at `temporal:7233`; it required actual workflow pollers before launching
the API, used a unique Mongo database at `mongodb://mongo:27017`, published a core
Wait Program, executed its native timeout and shut down cleanly. The script dropped
its owned database, and the controller stopped/reaped the worker and verified that
no owned worker containers remained. Completed Temporal test history remains under
normal retention; no active execution or retained environment was left by this gate.

The first separate-worker attempt correctly refused memory application records for
durable coordination. The fixture was corrected to use Mongo; no validation was
bypassed. The final separate-worker gate passed. This proves one actual image
startup/coordination path, not recovery, replay, remote invocation or tenant scale.

## Remaining acceptance

No image was pushed and no Helm release was deployed. CI/Podman, automated worker
rollout readiness, immutable dependency locking, larger replica/failure scenarios,
Kubernetes/OpenShell invocation, private receiver delivery and adverse cleanup
remain open. The service image is not the coding-agent/sandbox image. It intentionally
omits optional provider/tool SDKs unless selected through image extras.

Old AppContainer, Flask adapters, old Temporal/LangGraph runner and related session/
reporting/administration modules remain in source and the image pending required
behavior migration and full retirement. The canonical startup checkpoint does not
complete the runtime/dead-code audit, credential milestone or entire platform goal.
