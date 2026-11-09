---
name: debug-mcp-elements
description: Diagnose Flareward saved MCP provider/tool resources, async preparation, actual MCP SDK metadata/execution, task-owned protocol fixtures and pinned agent-session snapshots.
---

# Diagnose MCP element construction

Read [the saved-tool contract](../../../docs/program-platform-development.md#saved-mcp-tool-resources).
An explicit `mcp_proxy` resource needs a typed provider reference and an exact tool
name. Its pure factory returns a provider-backed adapter; native bundle preparation
awaits the provider's tool port before constructing a dependent agent. A tool schema
must be ready when the agent binds definitions, not only when it later executes.

Use `flareward.elements.construction.builder.ElementBundleBuilder` and the existing category builders. Ownership starts before async preparation.
Preparation errors/cancellation unwind the same owned scope; private errors stay
masked. The wrapper borrows provider/tool lifetimes. Avoid restoring the retired
factory's unsupported `mcp_client` constructor argument or another async bridge.

MCP schemas remain JSON Schema. Do not import the global utilities' dynamic model
generator merely to validate tool arguments; it initializes infrastructure settings
and adds an unnecessary code-generation path. Validate even empty arguments against
the declared schema. `CallToolResult.isError` is a failed tool execution, not a
successful text observation.

Run the preparation and SDK-wire tests first:

```sh
.venv/bin/python -m pytest platform/tests/application/test_element_preparation.py platform/tests/integration/providers/test_provider_tools.py -q -o addopts='--tb=short --strict-markers --import-mode=importlib'
```

The actual FastMCP server lifespan contains an AnyIO cancel scope. It must enter and
exit in the same task. Pytest async fixture setup and teardown may run in distinct
tasks; returning an app from a fixture and owning its lifespan in the test avoids
the different-task exit failure. SDK client/transport contexts also retain their
task owner. Assert that HTTP clients close after missing tools and failed execution.

Then use `integration/mongo/test_mcp_agent_sessions.py` with the dedicated Mongo and
Redis URIs from [Flareward's infrastructure guide](../../../platform/tests/infra/README.md).
It uses the existing saved-resource API, blueprint importer, real agent nodes,
shared session assertions and owned ASGI process helper. Thread/process cases require
actual remote tool calls on both turns and keep the published endpoint after its
saved provider is edited. No paid model calls are needed. This is not proof of
Kubernetes/OpenShell MCP-agent placement or external-provider availability.
