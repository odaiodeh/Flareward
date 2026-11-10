# Lumora naming cutover

Date: 2026-11-10. The user chose Lumora, requested the naming cutover, and asked
for the name's meaning in the main README. The broader ADLC goal remains paused.
Baseline: `10874fe1` (the committed Flareward repository/namespace milestone).
No staging, commit, push, hosted repository rename or checkout move was performed.

## Changed surfaces

- Product/readmes/UI/API/catalog descriptions: **Lumora**.
- Main README: **From intent to reality.** and **lumen** (light) + **aurora**
  (dawn), intelligence bringing ideas into reality. Login uses the same tagline.
- Core: `platform/src/lumora`, imports `lumora.*`. Concrete capabilities remain
  under `plugins.*`; shared utilities and Run Engine keep their existing names.
- Python distributions/commands: `lumora-platform`, `lumora-dev`; fallback script
  `tools/dev/lumora-dev`; UI package `lumora-ui`.
- Application/test settings, wire labels, capability references, defaults, queues,
  image recipes, charts, CI/developer tools and active test skills use Lumora.
- Identity diagram filenames follow the new name; captured image contents and
  historical evidence retain their original snapshot identities.
- Local editable distributions were reinstalled without dependency upgrades.
  Retired Flareward imports and console commands are absent, without aliases.
- Removed two unused product-named formatter aliases from the generic shared
  logging module; actual services already use its generic formatter classes.

The [naming guide](../branding.md) documents new environment names, fresh
publications/grants, matched API/worker/receiver installation and explicit data
locations. Existing data, credentials, histories and publications were not rewritten.
The physical checkout and real Git remote remain named Flareward. Actual external
service URLs, GitHub secrets, Vault/Jenkins identities and prior evidence were
preserved. Existing owned Docker/Kubernetes services were reused by explicit
addresses; none were renamed, stopped or recreated for this cutover.

## Verification

- Core domain/application/architecture/adapters/catalog and developer tooling:
  **1,350 passed**.
- Identity: **22 passed, 1 skipped** (explicit optional service smoke case).
- UI static types, actual graph/session contract runner and production build pass.
  The existing bundle-size warning remains. The host supplies pnpm 11 while the
  project pins pnpm 10.13.1: verification reused installed locked dependencies
  with `--config.verify-deps-before-run=false`, avoiding a host-settings-driven
  reinstall; dependency versions and lockfile were unchanged.
- Renamed CLI help, settings, all 23 manifests, available Element registry and
  15 backend Program descriptors load; unavailable optional Claude/Deep Agent
  SDK adapters remain unavailable rather than being represented as installed.
- Built platform/developer wheels include the canonical packages and renamed
  entry points; retired packages are absent. Editable installation agrees.
- Ruff import/syntax/undefined-name checks and formatting pass across 1,507
  platform source/test files. Parsed 1,655 Python and 43 non-template YAML files;
  12 shell files pass shell syntax checks. `git diff --check` passes.
- AST comparison with the committed baseline matches the naming-only transform
  for 1,651 Python files. Three explicit exceptions are the unused formatter
  alias removal and additional retired-namespace checks in architecture/image
  verification. Formatting does not change behavior.
- Native integration: **665 passed** in 780.44 seconds, selecting
  `platform/tests/integration` except deployment/catalog, with `--ui-clients` and
  explicit dedicated service URIs. Catalog was included in the core gate above.
  Real Local thread/process execution, native Temporal replay/recovery, resource
  construction, nested Programs, approvals, retained work and production API
  clients run against renamed modules. Total core/native/Identity: **2,037 passed**,
  plus the explicit optional Identity skip. No selected case failed.
- [Active-source manifest](2026-11-10-lumora-rename-source.json) records the final
  non-evidence checkout bytes. Historical manifests were not rewritten.

## Scope

The native regression uses the existing dedicated Mongo (27018), transaction
Mongo (27019), Redis (6380/15) and Temporal (7234), with unique test-owned databases
and execution identities. It includes real TypeScript API clients. It does not
rename infrastructure resources or use another project's default services.

Production/receiver images and Kubernetes/OpenShell deployment matrices were not
rebuilt or rerun for this naming task. Fresh `lumora-*:rename-20261110` defaults
are build targets, not claims about existing images. Prior Flareward remote
results remain scoped to their recorded source/images. No paid model call, strict
Landlock, load/adverse recovery or external deployment acceptance is implied.
