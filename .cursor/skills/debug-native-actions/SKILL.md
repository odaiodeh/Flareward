---
name: debug-native-actions
description: Diagnose or extend Lumora editor action discovery and async execution, including authenticated credentials, model capabilities and provider probes.
---

# Diagnose native editor actions

Trace the actual UI action UID through `lumora.api.actions`,
`lumora.services.actions.service` and `lumora.bootstrap.actions`. Native routes retain
`GET /api/actions/actions.list` and `POST /api/actions/action.execute`, with
`inputData`, `context`, `userId` and `teamId` compatibility fields. Stable UIDs and
Pydantic schemas also drive existing element form hints. An empty successful list
is not a substitute for missing registrations.

Contracts, metadata, the instance-owned registry and credential use cases belong
in `lumora.services.actions`; network/SDK implementations belong in
`plugins.actions`. Register injected instances in composition. Do not restore
subclass-global discovery, singleton lookup or the removed `lumora.actions` package.
Optional external SDK absence may omit its action; internal import errors must
still fail startup. The catalog refuses duplicate UIDs and synchronous classes
before dispatch. Extensible UIDs/type keys are strings; action kinds/categories
are enums.

`ActionContext.owner` can be a verified team; `credential_user_id` is the
authenticated human. The service overwrites declared input `user_id` from that
trusted context. Check request/body forgery and concurrent users before changing
auth behavior. Provider headers must be per request, never shared mutable client
headers. Validation and provider failures must not echo input secrets or raw SDK
errors. Cancellation propagates rather than becoming a business failure.

OpenAI metadata actions share one injected `ModelCapabilities` cache per
composition, with a lock, TTL and detached values. `MongoActionSettings` reads the
configured admin database/collection asynchronously; it does not generate text or
query a model API. A process-global cache can mix unrelated readers. The RAG
action client owns native async HTTP lifetimes and reuses wire models through
their explicit module; importing the old aggregate client can load Flask/global
configuration. MCP binds credentials asynchronously; A2A uses its owned client
context. Retained synchronous credential-store operations are awaited off-loop
with `await_owned`. The existing async bridge is used only by the legacy Flask
action adapter, pending cutover.

Run focused evidence from the repository root with its `.venv`:

```sh
.venv/bin/python -m pytest platform/tests/application/test_actions.py platform/tests/architecture platform/tests/adapters/test_action_capabilities.py platform/tests/integration/providers/test_action_lifetimes.py -q
```

`integration/redis/test_actions.py` uses actual signed cookies, Redis, Mongo and
encryption to check human/team scope, private errors and model metadata.
`integration/providers/test_action_http.py` starts separate native API/MCP/A2A
services. Use explicit own-service URIs and
[the platform test workflow](../run-platform-tests/SKILL.md); neither test needs a
paid model call. `support/team_http.py` owns signed-cookie team fixtures, while
application scenarios import no infrastructure adapters.

Strict typing of this slice:

```sh
MYPYPATH=platform/src .venv/bin/python -m mypy platform/src/lumora/services/actions platform/src/plugins/actions platform/src/lumora/services/administration/adapters/mongo/action_settings.py platform/src/lumora/api/actions.py platform/lumora.bootstrap/actions.py --python-version 3.14 --explicit-package-bases --follow-imports=silent --ignore-missing-imports --disable-error-code=import-untyped --strict
```

For a visible form failure use the actual full App fixture in
[session UI diagnostics](../debug-session-ui/SKILL.md).
Model/reasoning discovery uses synthetic Mongo capabilities and no provider call.
Keep browser, HTTP protocol, typing and deployment evidence distinct. After
installed-module changes, rebuild/verify both receivers and run the selected
remote matrix. Missing share notifications, OAuth callbacks and administrative
service startup are separate migration requirements.
