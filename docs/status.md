# Program platform: current status

Snapshot: 2026-11-12. Coordinator unification remains active; [plan](plan.md) and [target](architecture/README.md) define remaining acceptance.

## Coordinator unification

[Milestone specification and acceptance](architecture/coordinator-programs/README.md).

Common `CoordinatorRegistration`/`CoordinatorRegistry` catalog now includes native
`graph@1`; [explicit strategies](evidence/2026-11-12-coordinator-strategies.md) derive kind and isolate entrypoints.
Shared dependency projection drives publication diagnostics and child compilation.
Published revisions now freeze raw/model/canonical interfaces and owned-body contracts.
Composition, admission, UI invocation and Program v12 workers use the frozen boundary;
installed-schema drift rejects execution. See [verification](evidence/2026-11-11-published-interfaces.md).
[Saved-resource capture](evidence/2026-11-11-configuration-resources.md) now includes typed nested coordinator fields and owned bodies.
[Step A](evidence/2026-11-11-coordinator-step-a.md) is accepted locally. [Reviewer dependencies](evidence/2026-11-11-reviewer-dependencies.md) replace direct ADLC review calls; [result routing](evidence/2026-11-11-result-routing.md) is verified locally. [Mixed delivery C5](evidence/2026-11-12-mixed-delivery.md) passes controlled thread/process cases; [C6 recovery](evidence/2026-11-12-adlc-review-recovery.md) passes Local/Temporal. [Occurrence views](evidence/2026-11-12-occurrences.md) advance Step C; nested authoring/browser/remote gates remain.

## Repository cutover

The [naming guide](branding.md) defines the package/configuration cutover;
[current evidence](evidence/2026-11-10-lumora-rename.md) records its verification.
Core/native/Identity gates pass 2,037 tests; UI checks/build and wheel inspection pass.
This naming gate does not rebuild images or repeat Kubernetes/OpenShell acceptance.
Earlier [Flareward acceptance](evidence/2026-11-09-flareward-rename.md) remains
historical and does not certify renamed source or images.

Core source is `platform/src/lumora`, grouped by feature with local domain values,
ports, services and adapters. `plugins` groups capability contributions and
can install Elements and Programs together through the existing registries.
Retained roots: `ui`, `identity`, `packages/service-support`, `infra`, `tools`, docs.
Bundled RAG, separate admin backend, product CLI, singleton composition and replaced
Flask/custom/LangGraph execution are removed without import aliases. Useful specs,
factories, category builders, resource closures and agent behavior are retained.
Administrator settings/consent now use native platform services and production UI
clients. Generic graph data and explicit MAS conversation remain separate contracts.
See [cutover evidence](evidence/2026-11-09-repository-structure.md) for exact verification.

The [checkout move](evidence/2026-11-10-lumora-checkout.md) to `lumora` and
`odaiodeh/Lumora` origin is complete, with retained tracking and verified tooling.

## Implemented foundation

| Area | Current capability | Remaining acceptance |
| --- | --- | --- |
| Elements/resources | Specs/factories/builders, saved configurations, frozen dependencies, plugin manifests | Continuing semantic/extension audit |
| Operations | Typed contracts/context independent of graph state | Complete async/extension audit of retained integrations |
| Programs | One model/library, graph/backend implementations, schemas/revisions and optional conversation | Complete authoring consistency and UX |
| Composition | Pinned calls, owned bodies, Map/Repeat/Choose/Wait, bindings, conditions and joins | Complex-flow and full recovery acceptance |
| Placement | Profiles, owner policy, per-call selection, named environments and child imports | Complete isolation/recovery/adverse-cleanup matrix |
| Human Review | App-owned decisions with native waiting, actual live-browser feature proof | Remaining current-source recovery matrix |
| Authority/control | Root-scoped credentials, recoverable issuance/renewal/retirement and work/depth limits | Rotation/private delivery/stale fencing and tenant fairness |
| Artifacts/checks | Durable results, configurable file/Git candidates, independent checks, repair/review and retention | Live Git, choice UX and delivery integration |
| UI/observation | Shared execution routes, authoring canvas, resources, Sessions and hierarchy | Full elegant workspace/workbench and occurrence/attempt views |

## Accepted product checkpoints

The [live authored feature](evidence/2026-11-08-live-feature-authoring.md) joins
UI-created coder/designer/candidate/root, pinned Design/Engineering adoption, real
OpenShell planning/coding, independent checks, exact pre-approval previews and fresh
source/report retrieval after compute deletion. All managed capabilities retire.
[Controlled authoring](evidence/2026-11-08-feature-authoring.md) covers design
revision, failed checks and bounded repair. The live task passed first try; it does
not prove every repair path. Full canvas UX and complete ADLC delivery remain open.

[Completion contracts](evidence/2026-11-08-completion-contracts.md) and
[file/Git completion](evidence/2026-11-08-git-completion.md) select both deliverables
through one Engineering 3 revision, forward Feature selection after approval,
check/review exact candidates and retain source after compute removal. Git is an
optional capability; core Programs and ordinary Operation results remain generic.
The earlier live OpenShell checkpoint retains its version-2 source/image scope.

Curated inspection, resource publication/edit leases, reporting, provider streaming,
signed-session UI clients and native review/verification each have focused evidence.
Inspection is an observation, not revision-pinned certification. Remaining sharing
create/accept/copy and curated nested editing are tracked in the plan.
Old AppContainer/runners are now removed; pending useful behavior must migrate into
native services rather than restoring them. Current local package startup and the
cutover gate are separate from external cluster deployment acceptance.

## Required remaining acceptance

The [private receiver request](../integrations/run-engine-private-receiver-delivery-request.md)
records the SDK gap. Isolated private delivery, remaining credential/crash/rotation
combinations, stale-attempt fencing, tenant capacity/fairness, dynamic work,
authoritative occurrence history and the full remote/load/recovery matrix remain.
Local source ownership cannot migrate environments after host loss.

The earlier repository cutover passed 20 remote cases, including all four then-unreached
child-owned host/backend combinations. Focused cutover results do not certify the full
adverse/private-delivery matrix. Normal OpenShell is supported; strict Landlock checks remain optional
and need a capable Linux kernel. No paid calls are implicit in regression tests.

Run Engine baseline: `60393440efd3876cd6c81e0b013e8bf6d9167659`; unchanged externally.
Current formats: request v10, Program v12, state v4, elements v4, scheduled admission
v2, bundle v2; Engineering 4/Design 2/review subject 2, Python evaluator 2.0.0. Recreate old
publications after namespace cutover; use rebuilt matched images, not old aliases.

## Maintenance

Keep status <=100 and plan <=120 lines; snapshot evidence does not replace full acceptance.
