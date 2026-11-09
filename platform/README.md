# Flareward program platform

Flareward builds reusable Programs from configured Elements and other Programs.
A graph and a registered backend coordinator are implementations of the same
Program model, publication process and execution lifecycle.
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

Program definitions and pure bindings are owned by `flareward.programs.domain`.
Program authoring, publication, registrations and runtime/repository ports are
owned by `flareward.programs`. Import placement and step metadata from their
domain owners. Execution context/lifecycle/placement values live in
`flareward.executions.domain`; submission, control, prepared snapshots and mutable runtime
context holders live in `flareward.executions`. Replaced Program/execution
packages and the old core context module have no compatibility facade; rebuild
installed receivers after module changes using the test infrastructure guide.

## One capability and execution model

- Element: specification, schema, factory and construction dependencies.
- Resource: saved Element configuration; captured as a protected dependency bundle.
- Operation: executable Element with typed input/output, independent of graph state.
- Program: configured coordination, represented by a graph or registered coordinator.
- Execution: one invocation of a published Program revision; may contain children.
- Session: optional structured interaction; conversation is selected explicitly.

New authoring uses `/programs` and its canvas/configuration editor. Existing
blueprints are workflow templates imported into ordinary Program drafts. There
is no second graph runtime or graph publication path. Generic graph state contains
portable input/results/values/output; MAS channels belong to the agent-state adapter.
A node/condition graph selects that adapter because those capabilities require it.

## Install

For an existing checkout, follow the [naming cutover](../docs/branding.md) to
replace old editable installations, private settings and receiver images.

From the repository root with Python 3.14 or newer:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -e ../run-engine -e ./packages/service-support -e './platform[dev]'
```

Use the verified Run Engine source baseline identified in the development guide.

## Local API development

This local development mode uses memory storage and the Local host. Its
coordination does not survive process loss.

```sh
export FLAREWARD_HOST='{"runner_type":"local"}'
export FLAREWARD_STORAGE=memory
export FLAREWARD_AUTHENTICATION=development
export FLAREWARD_DEVELOPMENT_USER=alice
export FLAREWARD_INTERACTIONS=disabled
.venv/bin/flareward-platform serve --host 127.0.0.1 --port 13457
```

For the normal authenticated UI, use session authentication and the shared
Identity configuration described in the development guide.

## Durable execution

Configure the API and a separate worker with the same Temporal endpoint,
namespace, task queue, and receiver settings. The dedicated test stack uses
localhost:7234; production/development service addresses are deployment inputs.

```sh
export FLAREWARD_HOST='{"runner_type":"temporal","endpoint":"127.0.0.1:7234","namespace":"default","task_queue":"flareward-programs-dev"}'
```

Start the API and worker in separate terminals with the same configuration:

```sh
.venv/bin/flareward-platform serve --host 127.0.0.1 --port 13457
```

```sh
.venv/bin/flareward-platform worker
```

Choose persistent storage, authentication, credentials, and interaction backends
explicitly for the deployment. See the development guide for Mongo, Redis,
configuration encryption, profiles, installed modules, and UI proxy settings.

Generic event-start sources are opt-in with `FLAREWARD_EVENT_SOURCES_ENABLED=true`
and Mongo storage. Human-managed sources pin a published Program and private
execution template; deliveries use a separate source key and the normal execution
service. Automatic workflow scopes require managed credential provisioning too.
See [event contracts](../docs/program-platform-development.md#authenticated-event-driven-program-starts)
for bounded consent, redelivery, revocation and Local/Temporal recovery scope.

## Native service image

Build from the repository root with the approved Run Engine source checkout:

```sh
docker build --build-context run_engine=../run-engine -f platform/Dockerfile -t flareward-platform:local .
.venv/bin/python platform/tests/infra/verify_images.py --platform --image flareward-platform:local
docker run --rm -i --entrypoint python flareward-platform:local - < platform/tests/infra/smoke_platform.py
```

The image uses Python 3.14, runs as UID/GID 1000 and has one entrypoint:
`flareward-platform`. Its default arguments serve FastAPI on port 13457. Pass `worker`
to start native durable coordination. The old `mas` command, role-switching shell
entrypoint, WSGI launcher and old worker module launcher are removed. Refresh an
existing editable install to remove its obsolete console script.

The Dockerfile-specific context allowlist excludes local environments, test fixtures
and private bindings. The separate Run Engine context must also contain only
approved build source. The default `PLATFORM_EXTRAS` installs API, credentials,
blueprints, Temporal and telemetry; select provider/tool extras deliberately through
that build argument. `RUN_ENGINE_EXTRAS` defaults to Temporal. Remote invocation
backends and coding-agent images require their own installed capabilities and
acceptance gates. Add required system tools and organization CA certificates through
an explicit derived image/configuration, rather than downloading them implicitly.

Supply deployment settings and private bindings at runtime. API and worker must
agree on host/namespace/queue, installed modules, approved profiles and relevant
credential/environment policies. A Local host supports one API worker. The health
path is `/api/health/health`. See [Helm guidance](../infra/helm/platform/README.md) for
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
.venv/bin/python -m pytest platform/tests/application platform/tests/architecture -q
```

Select real-service, UI-client, and remote cases using the test guide and explicit
Flareward infrastructure settings. Paid model tests remain opt-in.

## Source ownership and adding capabilities

The single source root is `src/`. Core features are `flareward.elements`,
`resources`, `programs`, `executions` and `services.<feature>`; each owns its
values, ports, services and adapters locally. `flareward.api` is transport;
`flareward.bootstrap` selects implementations and owns their lifetimes.

Add a capability under `src/plugins/<capability>/`. Keep its configuration,
specification, factory and implementation together; substantial plugins can use
`elements/`, `programs/`, `domain/` and `adapters/` internally. An executable Element
uses `BaseOperation` with typed input/result models. Dependencies still resolve
through normal references, specifications, category builders and frozen bundles.
A reusable backend Program supplies an `ApplicationRegistration` with config and
optional input/output schemas; graphs remain the same public Program model.

Declare `PLUGIN = PluginDefinition(key=..., version=..., elements=(...),
programs=(...))` in `plugin.py`. Element modules expose their specification classes;
Program modules expose `APPLICATION_PROGRAMS`. The composition root installs both
into the existing registries, without constructing provider clients during discovery.
`FLAREWARD_PLUGINS` is an explicit JSON list of installed manifest modules; when set it
replaces the defaults in `flareward.bootstrap.settings.plugins.DEFAULT_PLUGINS`.
Install the selected modules and their optional SDK dependencies on API, worker and
receivers as appropriate. Core code must not import a concrete plugin.

Examples: `plugins.human_review` contributes Elements and a waiting Program;
`plugins.git` is an optional repository capability; `plugins.adlc_git`
composes Git candidates with ADLC without making Git depend on Engineering.
No compatibility namespace, second registry or separate plugin scheduler is needed.
