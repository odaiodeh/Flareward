---
name: helm
description: Navigate retained Lumora deployment charts and release groups.
---

Read `infra/helm/README.md` and the selected chart values/templates. Groups are
Platform (HTTP and worker), Identity, UI, and shared services. RAG and old admin
charts/hooks are removed. Test infrastructure is separate under
`platform/tests/infra`; do not deploy to external clusters without authorization.
