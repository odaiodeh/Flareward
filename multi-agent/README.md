# UnifAI program platform

UnifAI composes reusable capabilities into graph and application-code programs.
FastAPI exposes application use cases; Run Engine supplies execution infrastructure.

## Architecture references

- [Target architecture and ASCII diagrams](../docs/architecture/README.md):
  agreed components, contracts, repository structure, placement, and Human Review.
- [Development guide](../docs/program-platform-development.md):
  implemented behavior, setup, current APIs, and limitations.
- [Current status](../docs/status.md) and [active plan](../docs/plan.md):
  compact starting point, current milestone and remaining acceptance.
- [Evidence index](../docs/evidence/README.md): focused milestone records and
  opt-in historical lookup. Do not load archives/reference guides in full by default.
- [Tests](tests/README.md) and [dedicated infrastructure](tests/infra/README.md).

The target is a fresh platform. Old Flask/LangGraph execution paths, worker
contracts, storage formats, and forwarding aliases are removal targets. Preserve
useful specifications, factories, builders, resources, and application behavior
through the canonical new implementation.

Program definitions and pure bindings are owned by `mas.domain.programs`.
Program authoring, publication, registrations and runtime/repository ports are
owned by `mas.application.programs`. Import placement and step metadata from their
domain owners. Execution context/lifecycle/placement values live in
`mas.domain.execution`; submission, control, prepared snapshots and mutable runtime
context holders live in `mas.application.execution`. Replaced Program/execution
packages and the old core context module have no compatibility facade; rebuild
installed receivers after module changes using the test infrastructure guide.

## Install

From the repository root with Python 3.14 or newer:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -e ../run-engine -e ./global_utils -e './multi-agent[dev]'
```

Use the verified Run Engine source baseline identified in the development guide.

## Local API development

This local development mode uses memory storage and the Local host. Its
coordination does not survive process loss.

```sh
export UNIFAI_HOST='{"runner_type":"local"}'
export UNIFAI_STORAGE=memory
export UNIFAI_AUTHENTICATION=development
export UNIFAI_DEVELOPMENT_USER=alice
export UNIFAI_INTERACTIONS=disabled
.venv/bin/mas-platform serve --host 127.0.0.1 --port 13457
```

For the normal authenticated UI, use session authentication and the shared
Identity configuration described in the development guide.

## Durable execution

Configure the API and a separate worker with the same Temporal endpoint,
namespace, task queue, and receiver settings. The dedicated test stack uses
localhost:7234; production/development service addresses are deployment inputs.

```sh
export UNIFAI_HOST='{"runner_type":"temporal","endpoint":"127.0.0.1:7234","namespace":"default","task_queue":"unifai-programs-dev"}'
```

Start the API and worker in separate terminals with the same configuration:

```sh
.venv/bin/mas-platform serve --host 127.0.0.1 --port 13457
```

```sh
.venv/bin/mas-platform worker
```

Choose persistent storage, authentication, credentials, and interaction backends
explicitly for the deployment. See the development guide for Mongo, Redis,
configuration encryption, profiles, installed modules, and UI proxy settings.

Generic event-start sources are opt-in with `UNIFAI_EVENT_SOURCES_ENABLED=true`
and Mongo storage. Human-managed sources pin a published Program and private
execution template; deliveries use a separate source key and the normal execution
service. Automatic workflow scopes require managed credential provisioning too.
See [event contracts](../docs/program-platform-development.md#authenticated-event-driven-program-starts)
for bounded consent, redelivery, revocation and Local/Temporal recovery scope.

## Native service image

Build from the repository root with the approved Run Engine source checkout:

```sh
docker build --build-context run_engine=../run-engine -f multi-agent/Dockerfile -t unifai-platform:local .
.venv/bin/python multi-agent/tests/infra/verify_images.py --platform --image unifai-platform:local
docker run --rm -i --entrypoint python unifai-platform:local - < multi-agent/tests/infra/smoke_platform.py
```

The image uses Python 3.14, runs as UID/GID 1000 and has one entrypoint:
`mas-platform`. Its default arguments serve FastAPI on port 13457. Pass `worker`
to start native durable coordination. The old `mas` command, role-switching shell
entrypoint, WSGI launcher and old worker module launcher are removed. Refresh an
existing editable install to remove its obsolete console script.

The Dockerfile-specific context allowlist excludes local environments, test fixtures
and private bindings. The separate Run Engine context must also contain only
approved build source. The default `MAS_EXTRAS` installs API, credentials,
blueprints, Temporal and telemetry; select provider/tool extras deliberately through
that build argument. `RUN_ENGINE_EXTRAS` defaults to Temporal. Remote invocation
backends and coding-agent images require their own installed capabilities and
acceptance gates. Add required system tools and organization CA certificates through
an explicit derived image/configuration, rather than downloading them implicitly.

Supply deployment settings and private bindings at runtime. API and worker must
agree on host/namespace/queue, installed modules, approved profiles and relevant
credential/environment policies. A Local host supports one API worker. The health
path is `/api/health/health`. See [Helm guidance](../helm/multiagent/README.md) for
service arguments, configuration and the remaining cluster acceptance limitations.

## Components

- Specifications, factories, category builders, and bundles own construction.
- Typed operations validate input/result models independently of graph state.
- Programs coordinate reusable calls through application-owned runtime ports.
- Profiles and named environments select placement and explicit reuse.
- Run Engine owns dispatch, durable waits, children, recovery, and compute cleanup.
- Application services own authority, artifacts, decisions, and accepted outcomes.

Typed-operation catalog, graph/code invocation, HTTP, thread/process delivery,
and Temporal replay have tests. The full target is still in progress; production
coding-operation conversion, visual typed-port composition, durable artifacts, and
Human Review must be verified through their corresponding implementation slices.

## Verify

```sh
.venv/bin/python -m pytest multi-agent/tests/application multi-agent/tests/architecture -q
```

Select real-service, UI-client, and remote cases using the test guide and explicit
UnifAI infrastructure settings. Paid model tests remain opt-in.
