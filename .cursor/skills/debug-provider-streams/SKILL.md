---
name: debug-provider-streams
description: Diagnose Flareward async LLM stream ownership, early consumer exit, cancellation, and provider error translation using real SDK transports without live model calls.
---

# Diagnose provider stream lifecycle

Use the repository Python 3.14 environment and declared `flareward[openai,gemini]`
extras. Start with the actual SDK transports, not mocked model methods:

```sh
.venv/bin/python -m pytest platform/tests/adapters/test_async_llms.py platform/tests/application/test_agent_execution.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

`tests/support/llm_wire.py` supplies in-memory HTTP/SSE responses to the installed
SDKs. Its byte streams record physical closure and can hold or fail mid-response.
This exercises real parsing without credentials, Docker, or paid model calls.
Keep vendor wire fixtures here; application execution tests use application ports.

Distinguish normal exhaustion, early consumer exit, a failure during iteration,
and cancellation while waiting for another chunk. A generator's `aclose()` being
called does not establish that its underlying response closed. Assert closure of
the HTTP byte stream, preservation of cancellation, and cleanup completion before
the owner releases its resources. An SDK failure can occur after stream acquisition.

The GenAI 2.34 implementation has nested async generators that do not forward
early closure to their underlying HTTP response. Reinspect the installed SDK when
upgrading; do not assume a later release retains or fixes that behavior. The local
`google_genai/transport.py` adapter uses public HTTPX response hooks, a per-call
ContextVar, and an owned AsyncExitStack to close captured responses. It preserves
borrowed client ownership and isolates concurrent stream scopes. Keep this at the
provider boundary; do not patch SDK private methods or add workflow cleanup logic.

Tool-bound LLM copies share their original resource owner's client. Closing a
temporary bound view must not disable the original. GenAI borrows an injected
HTTPX client; OpenAI closes the injected client when its SDK client closes. Tests
must distinguish SDK ownership from fixture-owned transports.

For iterator failures, follow node execution, packet handlers, async strategy
thinking, execution handlers, and the tool executor. Pure construction, bindings,
and validation stay synchronous. Iteration and tool trace contexts must close on
cancellation. Blocking SDK work must drain before resource cleanup; a timeout can
therefore exceed its deadline while an unavoidable blocking call finishes.

Provider failures pass through `llms/common/errors.py`; assert that raw diagnostics
and credentials stay out of errors/traces. Avoid broad environment/header dumps.
SDK transport coverage does not establish live model behavior, remote placement,
or durable recovery. Use [the platform test workflow](../run-platform-tests/SKILL.md)
for those suites and rebuild receiver images after installed-code changes.
