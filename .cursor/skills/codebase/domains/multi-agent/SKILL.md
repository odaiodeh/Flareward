---
name: multi-agent
description: Develop UnifAI's composable program platform, typed operations, resource construction, UI contracts, and Run Engine integration with inward dependencies.
---

# UnifAI program platform

Start with [current status](../../../../../docs/status.md) and
[the active plan](../../../../../docs/plan.md). Search/read relevant sections of
[the target architecture](../../../../../docs/architecture/README.md) and
[the development guide](../../../../../docs/program-platform-development.md).
Use [selected evidence](../../../../../docs/evidence/README.md) when needed;
do not load guides/archives wholesale. Verify the relevant source before edits.

This is a fresh platform. Older stored formats, Flask/LangGraph execution paths,
old workers, dual APIs, and import aliases are not preservation requirements.
Convert useful behavior to the target contracts and remove superseded code/tests/
dependencies. Do not create compatibility fixtures or hold deletion for old-run
drain. Cancellation/resource draining for active owned work is still required.

## Ownership

- Domain: portable definitions, typed values, identities and pure invariants.
- Application: use cases, policies, owned ports, catalog and construction.
- Plugins/adapters: providers, external SDKs, storage, HTTP and engine translation.
- Bootstrap: explicit registration, settings, dependency injection and lifecycle.
- Run Engine: scheduling, invocations, children, timers/messages and environments.
- UI: authoring and observation through the same application contracts.

Specifications, factories, category builders and dependency bundles are useful
existing mechanisms. Reuse them; do not create a second registry or runner.
Typed operations have request/result models and explicit graph bindings.
Programs compose graph and registered code implementations through runtime ports.
Keep deployment settings and credentials outside operation behavior/configuration.

Authentication establishes the human; an explicitly selected team is authorized
at the boundary. Use typed Identity for owner-scoped application operations.
Authored IDs and execution metadata alone do not prove authority.

## Verification

Use [boundary refactoring](../../../refactor-agent-boundaries/SKILL.md) and
[platform tests](../../../run-platform-tests/SKILL.md) for relevant checks.
Verify behavior, cancellation, ownership, actual adapter delivery and UI integration.
Old generated MAS diagrams and deleted recipes are not architectural authority.
Do not suppress a defect merely because an old implementation used the pattern.
