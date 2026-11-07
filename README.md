# UnifAI

UnifAI is a platform for composing and executing agentic development workflows.
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
| UnifAI application: authoring, admission, Program contracts, |
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

UnifAI owns product policy, typed work contracts and authoritative business records.
Run Engine owns scheduling, coordination, native waits, invocation and environments.
An agent's successful exit is distinct from independent verification and authorized
human acceptance. Git revisions are supported identities; the core remains generic.

## Repository

| Directory | Responsibility |
| --- | --- |
| `multi-agent/` | FastAPI, application/domain contracts, Programs, capability integrations, workers and tests |
| `ui/` | React UI and shared API clients |
| `shared-resources/identity/` | Authentication, users and teams |
| `backend/` | Administration and Slack integration |
| `rag/` | Knowledge ingestion and retrieval |
| `global_utils/` | Shared infrastructure utilities |
| `local-development/`, `helm/`, `ci/` | Development setup and deployment |

## Start and develop

- [Platform setup and API/worker commands](multi-agent/README.md)
- [UI setup](ui/README.md)
- [Local service tooling](local-development/LOCAL_DEV_GUIDE.md)
- [Target architecture, ownership and ASCII diagrams](docs/architecture/README.md)
- [Implemented contracts and development guide](docs/program-platform-development.md)
- [Current status](docs/status.md) and [milestone plan](docs/plan.md)
- [Verification evidence](docs/evidence/README.md)
- [Platform tests](multi-agent/tests/README.md) and [dedicated infrastructure](multi-agent/tests/infra/README.md)

The target architecture is broader than current acceptance. Live ADLC checkpoints
exist; complete UI convergence, delivery integrations, remaining service retirement,
remote recovery and load acceptance are tracked explicitly in the status and plan.
