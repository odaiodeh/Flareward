---
name: identity-knowledge
description: Navigate the retained Identity authentication and team service.
---

Identity remains a separate Flask service under `identity/`, with `bootstrap/`
composition, `config/` settings, HTTP adapters, `utils/auth_manager.py`, `teams/`
and `directory/`. These are Identity's own packages, not `flareward.bootstrap`.
The shared helper source is `packages/service-support/src/global_utils`.

Identity writes server-side sessions under `identity:session:<id>` and signs the
browser cookie. The platform verifies that cookie and session record; both need
matching secret/Redis settings. Team owner selection must be checked against
membership. Vite/nginx expose Identity at `/identity/api` and Platform at `/api`.

Run `python -m pytest identity/tests` with Identity dependencies installed. Its
unit fixtures isolate OAuth/Redis/team infrastructure; optional smoke tests need
an explicit live service. Platform signed-session integration tests exercise real
Redis separately. Do not restore RAG or the old separate admin backend.
