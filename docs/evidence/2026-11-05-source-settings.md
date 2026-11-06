# Source settings and isolated receiver delivery handoff

Event source owners can inspect the frozen admitted profile catalog and work
limits through `GET /api/program-events/sources/{id}/settings`. The application
projects the persisted prepared snapshot without exposing its adapter payload.
The catalog describes approved names/default, not observed availability or a
complete per-call placement preview. Ownership is checked before projection.

Focused application/architecture tests passed 26 cases. The production
TypeScript-client journey against dedicated Mongo/Redis passed one case with ten
deselected, comparing source settings to the execution that ran. Strict mypy on
three production modules, Ruff on four Python files, and UI typecheck passed.
No remote images or broad Temporal matrix ran for this change.

The six changed code/test files have aggregate SHA-256
`466a24d87762b44672fdaf14f5c6788e930338d0b52ad19516efe32f56c2faf3`, calculated
over a sorted JSON map of path to file SHA-256. The prior full-source manifest is
historical. The goal remains active; this is not full platform acceptance.

The [Run Engine handoff](../../integrations/run-engine-private-receiver-delivery-request.md)
records the inspected public SDK boundary and requested trusted identity/private
setup capability. It is a proposal, not an implemented or tested remote delivery
path. Continue independent backend work while preserving the outstanding scope.
