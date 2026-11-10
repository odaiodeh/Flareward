---
name: debug-native-tracing
description: Diagnose Lumora native receiver tracing, OTLP export, session correlation, concurrent ownership, and cancellation cleanup.
---

# Diagnose native receiver tracing

Read [the native tracing contract](../../../docs/program-platform-development.md#native-tracing).
Follow the actual chain: portable element call, receiver-local settings, the
application tracing port, private provider, authenticated OTLP HTTP export.
No tracing SDK or key belongs in application coordination or invocation payloads.

The native adapter deliberately owns an independent provider/exporter per
invocation. The retained Langfuse SDK adapter shares resources by public key.
Do not replace native cleanup with per-invocation shutdown of that shared SDK:
one completed invocation could disable another. Keep acquisition, flush, and
shutdown off-loop and drain them before propagating cancellation. An acquisition
that finishes after cancellation still needs its registered owner closed.

Use both adapter and deployment evidence:

```sh
.venv/bin/python -m pytest platform/tests/adapters/test_native_tracing.py platform/tests/architecture -q
.venv/bin/python -m pytest platform/tests/integration/deployment/test_tracing.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

Deployment cases use the documented Mongo and Temporal URIs. The endpoint in
`tests/support/telemetry.py` receives real OTLP protobuf requests without a vendor
account. A held response tests actual pending export; resource-entry holding is
test-side and introduces no production fault flags. Concurrent/later owners and
batch-thread teardown distinguish flush from ownership cleanup.

For missing or misattributed spans, inspect session-derived trace IDs, actual
child execution metadata, native root/parent IDs, and parent span IDs. Receiver
roots use a fresh context; per-session attributes must propagate to every nested
observation without changing the global provider. Process settings serialize
validated URLs as scalar strings rather than quoted JSON strings.

Keep keys only in local deployment secrets and HTTP authorization. Inspect span
metadata without printing broad environments, headers, or credential-bearing
exceptions. Classify failures without raw exception messages/stack events.
Collector rejection must not trigger business retries after successful effects.
Distinguish a verified OTLP request from verified Langfuse persistence, cost
aggregation, and UI behavior. Rebuild receiving images after installed-code changes.

For remote settings, use `LUMORA_SECRETS_DIR` and Pydantic's existing file source.
Files use environment-variable names. Explicit/environment/dotenv values retain
precedence, including empty environment placeholders. An unavailable selected
directory fails; invoke-side reads are off-loop and private diagnostics stay out
of execution failures. Cancellation effects need the same source as receivers.

Kubernetes uses Run Engine's existing `secret_mounts`. The pinned OpenShell
integration can use a pre-provisioned sandbox with private files and an opaque
`sandbox_id`; the external owner retains its lifecycle. Keep settings provisioning
outside graph execution. Managed OpenShell file provisioning is a separate gap.
The remote private-settings scenario checks authenticated export, repeated use,
absence of raw/encoded keys in execution records and history, replay, and cleanup.
Use `LUMORA_RECEIVER_MODULE=lumora.bootstrap.receiver` when only remote receivers need
the built-in services. Profile `env` maps are serialized and reject declared
private settings; directory paths and secret names may travel as references.
