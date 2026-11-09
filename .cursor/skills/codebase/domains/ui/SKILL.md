---
name: ui-knowledge
description: >-
  Domain knowledge for the Flareward frontend. React/TypeScript SPA with feature-oriented
  layout. Use when working on files under ui/client/src/.
metadata:
  paths: "ui/client/src/**"
---

# UI Knowledge System

React 18 SPA with Nginx reverse proxy. Presentation is feature-oriented, with typed
API boundaries, pure authoring/data helpers, and explicitly owned query/request
lifetimes. Apply the target's SOLID and dependency-direction requirements without
requiring the frontend to mirror the backend's directory names.

## Component Routing

| Path prefix | Module | Files | Description |
|-------------|--------|-------|-------------|
| `api/` | API Layer | ~19 | Typed API modules, one per backend target service |
| `components/agentic-ai/` | Agentic AI | ~51 | MAS graph display, chat, templates, inventory |
| `components/ui/` | shadcn/ui | ~51 | Radix-based UI primitives (Button, Dialog, Select, etc.) |
| `components/shared/` | Shared | ~22 | FieldRenderer, ShareWorkflow, common widgets |
| `hooks/` | Custom Hooks | ~23 | Domain hooks (sessions, graphs, workspace, etc.) |
| `contexts/` | React Contexts | 7 files / 8 contexts | Auth, Theme, View, Shared, Notification, AgenticAI, Streaming, Project |
| `http/` | HTTP Clients | 4 | Axios instances for each backend service |
| `features/` | Feature Modules | ~22 | Slack, docs, configuration slices |
| `pages/` | Pages | Route-level | Page components compose feature views |
| `types/` | Types | ~8 | Shared TypeScript types (graph, session, workspace, templates) |

## HTTP Clients (4 backends)

| Client | File | Base URL | Target |
|--------|------|----------|--------|
| `queryClient` | `http/queryClient.ts` | `/api1` | RAG |
| `axiosAgentConfig` | `http/axiosAgentConfig.ts` | `/api2` | MAS |
| `authClient` | `http/authClient.ts` | `/api3` | Identity |
| `backendClient` | `http/backendClient.ts` | `/api4` | Platform |

## Context Provider Tree

```
QueryClientProvider → ThemeProvider → AuthProvider → SharedProvider
  → ViewProvider → ProjectProvider → NotificationProvider → routes
      Route-scoped: AgenticAIProvider (agentic routes)
                    StreamingDataProvider (chat/execution views)
```

| Context | Hook | Key Responsibility |
|---------|------|--------------------|
| `AuthContext` | `useAuth` | Session, login/logout, token refresh, `X-Authenticated-User` |
| `ViewContext` | `useView` | Private vs team workspace, selected team, user groups |
| `ThemeContext` | `useTheme` | Dark/light toggle, primary color CSS vars |
| `AgenticAIContext` | `useAgenticAI` | Resource UUID↔name maps, validation caches (~760 LOC) |
| `StreamingDataContext` | `useStreamingData` | In-memory node stream map for live graph/chat |
| `NotificationContext` | `useNotifications` | Share invites (received/sent), accept/decline |

## Key Hooks

| Hook | Domain | Summary |
|------|--------|---------|
| `useWorkspaceIdentity` | Identity | Single source of truth for userId, identityType, displayName |
| `useSessionStream` | Streaming | NDJSON Redis stream: submit → subscribe → reconnect |
| `useSessionHub` | Sessions | Shared session list/CRUD/execution |
| `useGraphDisplay` | Graph | Read-only JointJS + live status overlays |
| `useTemplates` | Templates | List, detail, schema, validate, materialize |
| `useWorkspaceData` | Inventory | Category-based element CRUD |
| `useBuiltinEditLockSession` | Repository Mgmt | Owns heartbeat/release lifecycle for one held admin edit-lock |

## Nginx Path Routing (production)

| Path | Target | Notes |
|------|--------|-------|
| `/api1/*` | RAG (port 13457) | Standard proxy |
| `/api2/*` | MAS (port 8002) | Streaming: 600s timeout, `proxy_buffering off` |
| `/api3/*` | Identity | 307 redirect to `IDENTITY_HOST` |
| `/api4/*` | Platform (port 8005) | Standard proxy |

## Dev-Guide Facts

For full endpoint catalog (72 endpoints), component details, and hook documentation:
- **Service doc:** `.cursor/flareward-dev-guide/docs/services/ui.md`
- **Code → doc routing:** `.cursor/flareward-dev-guide/guide-index.yaml` (maps `ui/client/src/**` to ui.md)
- **Source map:** `.cursor/flareward-dev-guide/source-map.yaml → ui` (API modules, hooks, contexts, HTTP clients)

## Landmarks

| Landmark | Location |
|----------|----------|
| App entry | `App.tsx`, `main.tsx` |
| Route definitions | `pages/` |
| API client setup | `http/` |
| Build flareward.bootstrap.settings | `vite.config.ts`, `tailwind.config.ts` |
| Nginx flareward.bootstrap.settings | `ui/deployment/nginx.conf.template` |
| Proxy flareward.bootstrap.settings (dev) | `ui/vite.config.ts` |

## Domain Rules

Frontend-specific conventions. Feature-oriented folders describe presentation
organization; they do not exempt UI code from clean boundaries, cohesive ownership
or separation of application behavior from transport and rendering.

---

### 1. Feature-Oriented Layout

Each feature is self-contained in its directory with its own components,
hooks, and types. Shared code lives in top-level `components/`, `hooks/`,
`contexts/`, and `lib/`.

---

### 2. API Layer Separation

All backend communication goes through the `api/` layer. Components never
make direct HTTP calls. Hooks wrap API functions and use TanStack React Query v5
for server state management.

---

### 3. Type Safety

All API responses, component props, and state shapes have explicit TypeScript
interfaces. No `any` types in production code. Shared types in `types/`.

---

### 4. Workspace Identity Pattern

`useWorkspaceIdentity()` is the single source of truth for `userId`, `identityType`
(user vs team), and `displayName`. It feeds API params for every identity-scoped call.
Backed by `AuthContext` (session) + `ViewContext` (team switching).

---

### 5. Component Conventions

- Functional components only (no class components)
- Props destructured in function signature
- Custom hooks for logic extraction (heavy components → dedicated hooks)
- Composition over inheritance
- shadcn/ui primitives from `components/ui/` — do not reinvent

---

### 6. Streaming Pattern

NDJSON streaming via native `fetch` + `ReadableStream` (not axios).
`useSessionStream` hook handles submit → subscribe → reconnect.
`StreamingDataContext` holds `Map<nodeId, NodeEntry>` for live graph overlays.

---

### 7. Graph Builder (JointJS)

Authoring uses `features/programs/ProgramEditor.tsx` and `ProgramGraphEditor.tsx`
with canonical Program definitions and separate presentation positions. New Programs
start with visual composition; installed coordinators use schema configuration in
that same editor. `/programs` is the single library and authoring route. The old
workflow authoring page, NewGraph, GraphCreation and their private hooks are removed.
Existing blueprints enter through `ProgramTemplateImport` as ordinary Program drafts.
Read-only MAS graph views still use their existing display/layout components; do not
reintroduce a second authoring state model or execution experience.
