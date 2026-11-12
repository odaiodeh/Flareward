# Coordinator foundation checkpoint — 2026-11-11

This is an implementation checkpoint, not completion of the unified Program target.

## Changes

- One CoordinatorRegistry/CoordinatorRegistration contract includes native graph@1
  and plugin coordinator metadata. The UI selects both through the actual catalog.
- ProgramBody.dependencies exposes target, imports and source diagnostic location.
  Child preparation is shared across graph/custom implementations; pinned revision
  authority, owned body paths, defaults and environment imports retain their checks.
- ProgramInterfaces centralizes caller contract resolution while preserving raw
  intent validation, Pydantic normalization and serialized-result constraints.
  This is not yet the full resolved published-interface/schema editing design.
- PreparedGraph/PreparedCoordinator form the discriminated ProgramPayload body.
  The installed entrypoint is lumora-program-v7; it retains native graph delegation
  and one Run Engine submission/lifecycle. Old payloads require fresh preparation.
- Human Review registration now declares its result model. ADLC still needs the
  planned adoption of review as a configured child Program.

## Verification

- 1,055 application/domain/adapter/architecture/plugin-installation tests passed.
- Five additional coordinator catalog/dependency/interface regressions passed.
- 91 actual Local thread/process Program/composition/model/operation/condition
  tests passed, including nested graph/coordinator combinations and pinned calls.
- Three actual Temporal composition cases passed on the dedicated localhost:7234
  service, including child histories, replay and Wait worker restart.
- UI TypeScript checking, production contract checks and production build passed.
  The existing build warning for chunks larger than 500 kB remains.

No paid provider calls, image rebuilds, Kubernetes/OpenShell matrix or full browser
journey ran for this checkpoint. Earlier receiver images do not certify Program v7.
Run Engine source was not changed. No commit or push was performed.

## Remaining target

Complete canonical published interfaces and normalization metadata; authored child
binding/import consolidation; consistent saved-resource selection; ADLC review
composition; generic data routing; structured occurrence correlation; nested/control
canvas authoring and the execution workbench. Then verify rebuilt remote receivers
and browser journeys at the appropriate milestone. See ../plan.md and the target
architecture README for the remaining ADLC and operational obligations.
