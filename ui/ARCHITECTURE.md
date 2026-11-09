# UI ownership and integration

The UI reuses the React Flow authoring canvas, resource/dependency pickers,
configuration inspectors, session interaction and execution indicators. Programs
have one library/lifecycle for graph and registered backend implementations.

```text
React App (client/src/App.tsx)
  |-- Programs: catalog, revision/configuration and graph authoring
  |     features/programs/ + components/agentic-ai/
  |-- Inventory: Element discovery and saved Resource configuration
  |-- Execution: shared result/review/artifact/child inspector
  |-- Sessions: optional conversation across executions
  |-- Reviews, schedules, reporting, administration
  |
  +-- client/src/api/*             typed transport
        |-- http/axiosAgentConfig  /api          -> platform FastAPI
        +-- http/authClient        /identity/api -> Identity /api
```

`features/programs` owns reusable Program UX; backend schemas describe typed config,
inputs and outputs. Transport clients do not schedule work, validate authority or
contain provider SDK logic. The platform publishes revisions, captures saved
resource closures, admits runs and projects live execution state. A Session is
optional interaction state, not a second engine. Review responses require the
actual authenticated human. Artifacts/checks identify retained evidence separately
from successful execution. Placement selects admitted execution profiles and named
environments, not credentials in canvas data.

Vite and production nginx share canonical routes and same-origin cookies.
Administrator and transparency-consent clients call platform services; they no
longer require the removed RAG/admin applications. Team owner selection remains
separate from the acting authenticated human.

The full target remains a coherent canvas/workbench with nested Program drill-down,
inline loops/conditions, occurrence/attempt history, contextual inspectors and
accessible design. Current forms and inspectors prove functional journeys; they
are not final UX acceptance. See [the target](../docs/architecture/README.md),
[status](../docs/status.md) and [UI verification](README.md#verification).
