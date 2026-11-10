---
name: codebase
description: Navigate the feature-owned Lumora platform and its capability plugins.
---

Read `docs/status.md`, `docs/plan.md`, and relevant parts of
`docs/architecture/README.md`. Core Python source is `platform/src/lumora`;
installed plugins are `platform/src/plugins`. `ui` is the React frontend;
`identity` authenticates users and teams. `packages/service-support` provides only
shared infrastructure helpers (Python import `global_utils`).

Features own domain values, ports, services and adapters locally. Core must not
import concrete plugins except in `lumora.bootstrap`; plugins consume core contracts.
Read `.cursor/skills/codebase/domains/platform/SKILL.md` for construction/runtime
ownership and `.cursor/skills/run-platform-tests/SKILL.md` for verification.

Removed apps (`rag`, old admin `backend`, user `cli`) and old `lumora` imports must not
be restored. Historical evidence is snapshot-specific and may contain old paths.
Use current source and current README commands, not archived/generated catalogs.
