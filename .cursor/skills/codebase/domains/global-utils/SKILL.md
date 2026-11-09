---
name: service-support
description: Navigate infrastructure helpers genuinely shared by platform and Identity.
---

Source: `packages/service-support/src/global_utils`. Keep authentication/session
wire contracts, Identity clients, Redis helpers and currently used bridge utilities.
Domain values and use cases belong in platform features, not this shared package.
Celery, bundled ingestion and embeddings helpers are retired. Audit callers before
removing a helper; existing MCP/A2A integration still uses the async bridge.
