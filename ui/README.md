# Flareward UI

The [review-evidence checkpoint](../docs/evidence/2026-11-07-review-evidence.md)
verifies source and admitted report previews before final approval in the actual
App, using controlled planning/coding and production checks. The
[authoring checkpoint](../docs/evidence/2026-11-08-program-authoring.md) adds UI-created
operation resources, dependency capture, incomplete drafts, process execution and
unchanged nested reuse. The [feature-authoring checkpoint](../docs/evidence/2026-11-08-feature-authoring.md)
adds a UI-created coder/designer/candidate/root and explicit Design/Engineering
revision adoption through controlled design revision, repair, final review and
retained evidence. [Live authored acceptance](../docs/evidence/2026-11-08-live-feature-authoring.md)
now uses separate UI-created designer/coder resources and pinned Programs with real
OpenShell planning/coding, offline checks, exact pre-approval previews and fresh
retrieval after compute deletion. This accepts the thin product journey; the full
UX redesign remains open. Browser gates build the production App
with `node tests/build-workspace-browser.mjs <temporary-directory>`; the superseded
isolated blueprint-dialog harness is removed.

Engineering now publishes named completion choices with candidate schemas and frozen
check requirements. [Backend/native proof](../docs/evidence/2026-11-08-git-completion.md)
uses version 3 for direct file/nested Feature Git selection, repair and retained work;
choice-specific authoring/invocation and Git-source review browser acceptance remain open.
The live authored checkpoint above retains its earlier version-2 source/image scope.

## Target experience

Build on the current React Flow authoring canvas and existing design system,
resource pickers, inspectors and execution indicators. Retained JointJS surfaces
serve read-only MAS views; do not restore a competing authoring product. Aim for
a spacious canvas, clear hierarchy, restrained color/motion and readable status,
with configuration details revealed in context. Judge this through rendered
browser journeys, including keyboard use and reduced motion, not library choice alone.
Current forms/workbench are an intermediate functional experience. The dedicated
UX milestone must reduce exposed configuration clutter and deliver coherent canvas,
contextual inspectors and nested execution navigation; readiness checks do not fulfill it.

The [target UI design](../docs/architecture/README.md#unified-ui-and-live-execution-experience)
unifies the resource library, Program builder and optional Session experience
into one Program-authoring workspace and shared execution workbench. Programs are
reusable library/canvas components. Structured inputs and optional conversation
use the same execution contracts. Preserve and improve live visualization of
active work, nested Programs, iterations, retries and waits, using authoritative
execution state and exact published revisions.

The canvas belongs to the Program being composed; called Programs appear as reusable
blocks. In execution mode, start at the selected root Program and support both
inline expansion and focused child inspection with parent/root breadcrumbs. Choose
the actual iteration/item/attempt when a block has multiple occurrences. Keep pinned
definition inspection separate from execution drill-down; editing reusable work
creates a draft/new revision and callers adopt it explicitly. Backend Programs expose
configuration and observed calls without an invented editable graph. See
[nested navigation](../docs/architecture/README.md#root-overview-and-nested-execution-navigation).
This is target interaction design; current child links are not full live-canvas proof.

Reuse useful existing components and patterns while allowing substantial
improvements to layout, navigation, accessibility and visual presentation. New authoring uses one Programs library and canvas/configuration editor. The
superseded Workflows page and its private authoring implementation are removed.
Existing blueprints can be imported as Program drafts. Sessions remain an optional
interaction view; full live occurrence/attempt visualization remains unfinished.
Program invocation now opens the shared `/executions/:id` route; the embedded
Program runner was removed. Session/review links use the same execution view.
See the [development guide](../docs/program-platform-development.md#program-discovery-saved-library-and-authoring)
for implemented behavior and [the active plan](../docs/plan.md#remaining-milestone-order)
for remaining work. Start/resume with [current status](../docs/status.md); read
only relevant reference sections. These links describe targets and status separately.

Work backend-led while connecting thin UI journeys as contracts stabilize. Shared
schema fields and protected saved-resource capture now have a focused
[browser checkpoint](../docs/evidence/2026-11-05-program-configuration.md). Structured
invocation and shared execution/review now have their own
[checkpoint](../docs/evidence/2026-11-05-execution-workbench.md). Owner-filtered workflow
permissions and verified text previews now support a [controlled Engineering journey](../docs/evidence/2026-11-05-feature-ui.md),
including approval, repair and durable artifact retrieval. A [live OpenShell browser
checkpoint](../docs/evidence/2026-11-06-live-feature-ui.md) now joins real Codex,
production checks and fresh output retrieval after compute removal. The newer
[configured-designer checkpoint](../docs/evidence/2026-11-07-configurable-designer.md)
adds real planning before design approval. The review-evidence checkpoint above
proves source and admitted report previews before the decision. Complete authoring
and Session browser journeys, occurrence views and later visual refinement remain
required. The old authoring builder is removed; retained JointJS surfaces are
read-only MAS views. The current React Flow editor and panel-based execution view
still require the nested live-canvas experience described above.

## Building the UI

When building the UI, we currently work with a lock file. This allows us to keep working in the same environment without constant synchronization of development environments. In addition, it makes the production build more stable (as we only lock after a successful build). If a change needs to be made to one of the packages, the developer in question is responsible for removing the lock file and installing the modules anew using the updated `package.json`. This means the developer will have to resolve all issues with packages/modules versions prior to merging into the `main` branch.

### Development

Use Node 22+ and the package-manager version declared in `package.json`:

```sh
cd ui
pnpm install --frozen-lockfile
PLATFORM_HOST=http://127.0.0.1:8002 IDENTITY_HOST=http://127.0.0.1:13456 pnpm start
pnpm build
```

`/api` targets the platform FastAPI API. `/identity/api` targets Identity's `/api`.
Both use the browser's same-origin signed session. Production nginx uses the same
paths, with `PLATFORM_IP`/`PLATFORM_PORT` and `IDENTITY_SVC_IP`/`IDENTITY_SVC_PORT`.
The old RAG and separate administration clients/routes are removed. Administration
and transparency consent use the platform API.

## Verification

```sh
node_modules/.bin/tsc --noEmit -p tsconfig.json
node tests/run-api-contracts.mjs contracts
node_modules/.bin/vite build
```

Native TypeScript client and actual-App browser scenarios are documented in
`platform/tests/README.md`. A successful build alone is not browser acceptance.
See [UI ownership](ARCHITECTURE.md) and [the target design](../docs/architecture/README.md).
