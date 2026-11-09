# Flareward

Flareward is a platform for composing and executing agentic development workflows.
Configured capabilities perform work; reusable Programs coordinate those capabilities
and other Programs through typed contracts and a shared execution lifecycle.

## One public model

- **Element:** an installed capability specification, configuration schema, factory
  and dependency requirements. An **Operation** is an executable Element.
- **Resource:** saved Element configuration, captured with its dependency closure.
- **Program:** configured work with input/output contracts and published revisions.
  Visual graph composition and registered backend coordination implement this same
  model. Either can invoke operations or other Programs.
- **Execution:** one run of a published Program, with results, children, reviews,
  artifacts and execution placement. A **Session** optionally retains interaction
  across Executions; structured data and conversation are explicit choices.

Existing blueprint documents are workflow templates imported into Program drafts.
New authoring uses the Programs library and its canvas/configuration editor.
Construction dependencies describe what to build; execution edges describe what to
run. Specifications, factories and builders remain the capability construction path.

## Architecture

```text
+---------------------------- UI -----------------------------+
| Resources | Programs library/canvas | Executions | Reviews  |
| Optional Sessions | Results and retained artifacts           |
+------------------------------+------------------------------+
                               | HTTP
+------------------------------v------------------------------+
| Flareward application: authoring, admission, Program contracts, |
| construction, verification, review and artifact services     |
| Domain values and application-owned ports                   |
+------------------------------+------------------------------+
                               | adapters
+------------------------------v------------------------------+
| Run Engine | Storage | Identity | Capability integrations    |
| Coordination and graphs | Invocation and environment reuse  |
+------------------------------+------------------------------+
                               |
+------------------------------v------------------------------+
| Temporal | Workers | Thread/process | Kubernetes | OpenShell |
| Coding agents | Models | Tools | External services           |
+-------------------------------------------------------------+
```

Flareward owns product policy, typed work contracts and authoritative business records.
Run Engine owns scheduling, coordination, native waits, invocation and environments.
An agent's successful exit is distinct from independent verification and authorized
human acceptance. Git revisions are supported identities; the core remains generic.

## Repository

| Directory | Responsibility |
| --- | --- |
| `platform/` | Feature-owned core (`flareward`) and optional capability plugins (`plugins`), API, workers and tests |
| `ui/` | React canvas, catalogs, execution workbench and shared API clients |
| `identity/` | Authentication, users, teams and directory integration |
| `packages/service-support/` | Infrastructure utilities shared by platform and Identity (`global_utils` package) |
| `infra/` | Deployment charts; dedicated test infrastructure remains under `platform/tests/infra/` |
| `tools/dev/`, `tools/ci/` | Local service tooling and CI pipelines |

Core features own their models, ports, services and adapters locally. Plugin folders
are organized by capability and may contribute Elements and Programs together.
Only the composition root selects concrete plugins. There is no old `mas` namespace
or second execution engine. RAG ingestion, the separate admin app and the user CLI
have been removed; platform administration and consent use the platform API.

## Start and develop

- [Flareward naming, package installation and configuration cutover](docs/branding.md)

- [Platform setup and API/worker commands](platform/README.md)
- [UI setup](ui/README.md)
- [Local service tooling](tools/dev/LOCAL_DEV_GUIDE.md)
- [Target architecture, ownership and ASCII diagrams](docs/architecture/README.md)
- [Implemented contracts and development guide](docs/program-platform-development.md)
- [Current status](docs/status.md) and [milestone plan](docs/plan.md)
- [Verification evidence](docs/evidence/README.md)
- [Platform tests](platform/tests/README.md) and [dedicated infrastructure](platform/tests/infra/README.md)

The target architecture is broader than current acceptance. Live ADLC checkpoints
exist; complete UI convergence, delivery integrations, remaining service retirement,
remote recovery and load acceptance are tracked explicitly in the status and plan.
