# Program platform: active plan

Updated 2026-11-09. Read [status](status.md) and relevant source; the
[target checklist](architecture/README.md#architecture-acceptance-checklist) defines completion.
The stored overall goal remains paused. The user explicitly authorized the repository
reorganization below; this task does not resume or complete the larger goal.

## Completed requested milestone: feature-owned repository and plugin layout

[Accepted cutover](evidence/2026-11-09-repository-structure.md). Outcome: remove unused applications and replaced runtimes, retain useful capability
construction and product flows, make component ownership visible in the directory
structure, and verify the cutover without compatibility aliases.

- `platform/src/flareward`: feature-owned Elements, Resources, Programs, Executions,
  shared product services, FastAPI transport and composition roots. Local domain,
  ports, services and adapters; no global domain/application directory split.
- `platform/src/plugins`: capability-owned plugins, optionally contributing
  both Elements and Programs through manifests and the existing registries.
- Retain `ui`, move Identity to `identity`, actual shared helpers to
  `packages/service-support`, deployment to `infra`, development/CI to `tools`.
- Remove bundled RAG, separate admin backend, user CLI, old Flask/custom/LangGraph
  platform execution, singleton composition and unused scheduling/session facades.
  Keep specs/factories/builders, transitive resource snapshots and agent behavior.
- Retain administration/consent through native platform services and actual UI
  clients. Keep generic Program state separate from explicit conversation state.
- Verify baseline/native/client/browser/package gates; rebuild matched receivers
  for representative Kubernetes and normal OpenShell execution. Record exact scope.
- Update active README/skills/tooling/deployment references; leave historical evidence
  snapshot-specific. No commit/push/staging unless the user requests it.

The additional user-authorized [Flareward naming cutover](branding.md) is complete
within its [recorded verification scope](evidence/2026-11-09-flareward-rename.md). It updates
core/imports, capability `plugins`, CLI/configuration, UI and deployment names.
Historical evidence and actual external service identities remain snapshot-specific.

## Accepted product prerequisite

The [live authored feature](evidence/2026-11-08-live-feature-authoring.md) accepts a
thin UI-authored designer/coder/candidate/root, real OpenShell planning/coding,
independent checks, exact human review and retained source after compute removal.
Controlled tests cover design revision and repair. Full UX and platform acceptance
remain open; do not repeat paid/live investigations without a relevant reason.

[Completion contracts](evidence/2026-11-08-completion-contracts.md) and
[file/Git proof](evidence/2026-11-08-git-completion.md) provide named Engineering
choices, frozen candidate/check contracts, direct file/nested Git selection,
repair/check/review and retained work through one published revision.

## Remaining overall milestone order

| Order | Outcome | Remaining acceptance |
| --- | --- | --- |
| 1 | Feature-owned repository cutover | Accepted within the linked cutover scope. |
| 2 | Completion alternatives and delivery | Choice UX, live Git, authorized intake/CI/CD, uncertain-effect reconciliation and larger unchanged reuse. |
| 3 | Broader composition, observation and unified authoring | Library/canvas/workbench convergence, inline controls/bindings, revision adoption, occurrence/attempt hierarchy, gaps and pagination. |
| 4 | Remaining controls and remote operation | Credential recovery/rotation/private delivery, stale fencing, tenant/profile capacity/fairness, admitted dynamic work and remaining service behavior migration. |
| 5 | Operational and final acceptance | Required current-source host/backend/load/recovery/cleanup matrices, cluster deployment and requirement-by-requirement audit. |

Boundaries: Elements construct through specs/factories/builders; Programs compose
through typed runtime ports. Run Engine owns scheduling/waits/invocation/environment
lifetimes. Flareward owns authority, accepted outcomes and business records. Git is an
optional capability; ordinary results remain typed data. Preserve exact candidate
-> independent checks -> approval -> delivery receipt -> validation semantics.
Do not add Git/ADLC-specific compiler branches or another scheduler/registry.

Required carry-over obligations remain:

- Private isolated receiver delivery: inspect the [SDK request](../integrations/run-engine-private-receiver-delivery-request.md).
  Never expose root-wide material/vault keys or substitute broad credentials.
- Remaining worker/Session/schedule/crash combinations, cleanup-outbox recovery,
  bounded renewal/revocation, source/workflow credential rotation and stale attempts.
- Current-image isolation/reuse, terminal/adverse cleanup and child ownership across
  the full host/backend matrix. Cutover now passes all four child-owned combinations;
  remaining adverse/private-delivery cases need the broad remote milestone.
- Native sharing create/accept/copy and curated draft/nested editing where still
  pending. Preserve retained behavior rather than restoring removed singleton roots.
- Complete Session/browser acceptance, occurrence/attempt views and elegant,
  accessible canvas/inspector/root overview with nested execution drill-down.
- External-effect intent identities and reconciliation of lost acknowledgements;
  uncertainty never permits blind redispatch. No mocked delivery presented as live.

## Verification cadence

Use focused tests/static checks during implementation; coherent integration gates
at milestones. Batch Docker/Temporal/Kubernetes/OpenShell/browser work, with full
final coverage. Rebuild matched images after installed code changes; historical
images do not prove the current source. Use dedicated Flareward infrastructure only.
Poll confirmed-live handles; observation timeout does not justify duplicate runs.
No implicit paid calls. Record scope, source/image identities and limitations in
focused [evidence](evidence/README.md). Keep status <=100 and plan <=120 lines;
rewrite facts rather than appending diaries. Continuous SOLID/hexagonal boundaries,
typed models/enums, cohesive classes, minimal Python and owned async lifetimes apply
to production and test code throughout, not as a final hardening phase.
