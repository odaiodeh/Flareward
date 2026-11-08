# UnifAI UI

The [review-evidence checkpoint](../docs/evidence/2026-11-07-review-evidence.md)
verifies source and admitted report previews before final approval in the actual
App, using controlled planning/coding and production checks. The
[authoring checkpoint](../docs/evidence/2026-11-08-program-authoring.md) adds UI-created
operation resources, dependency capture, incomplete drafts, process execution and
unchanged nested reuse. The [feature-authoring checkpoint](../docs/evidence/2026-11-08-feature-authoring.md)
adds a UI-created coder/designer/candidate/root and explicit Design/Engineering
revision adoption through controlled design revision, repair, final review and
retained evidence. Matched-image real-agent acceptance and the full UX redesign
remain open. Browser gates build the production App
with `node tests/build-workspace-browser.mjs <temporary-directory>`; the superseded
isolated blueprint-dialog harness is removed.

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

### Prerequisites

PNPM installed on your system.

* Upgrade your npm:
    `npm install -g npm`

* Install PNPM via Corepack (can be done via npm as well instead):
    `npm install -g corepack`
    `corepack enable`

* Install PNPM via Corepack:
    `corepack prepare pnpm@latest --activate`

### Install all Required Packages and Build

* Make sure you have the `package.json` and `pnpm-lock.yaml` files in place. These should come with the cloning and should be under the UI's main folder.
    **NOTE: IF YOU NEED TO ADD A NEW PACKAGE, YOU MUST UPDATE THE `PACKAGE.JSON` FILE, INSTALL PACKAGES, AND YOU MUST PUSH THE NEW LOCK FILE AS WELL AFTER VERIFYING THE BUILD IS WORKING.**

* Install all dependencies (including devDependencies needed for the build). `--frozen-lockfile` ensures reproducible builds based on `pnpm-lock.yaml`.
    The lock file is the output of the last successful installation, and we should use it unless we specifically need to change packages or versions.
    `pnpm install --frozen-lockfile`

* Build the UI:
    `pnpm build`

## Running the UI (Locally)

As we usually use existing backends or local ones depending on our work, we need a quick method to change the backends we run against. Until now, we used to update Axios config. This works properly but with some caveats:
1.  The changes must be removed before building the code so that Axios won't change the UI behavior.
2.  Every change needs a rebuild if we want to check the UI as a package.
3.  If we need to have a common API structure, this might be complicated.

Instead of using Axios, we need to change the usage to `vite.config.ts` proxies. This is built for the development environment. The `vite.config.ts` isn't going into the code, so it's safe to build it. That way, if Axios already has some config, we just need to adjust the config to fit it (just like Nginx config).

In order to run the UI locally, follow these steps:

1.  Update the `vite.config.ts` server/proxy section to route the requests properly to the backends and replace the api1/api2 from the UI. This step is crucial as it simulates the Nginx behavior that we use in production (see example below):

    ```
    server: {
      port: 5173, // Or whatever port Vite is running on by default
      proxy: {
        // Proxy for api1
        '/api1': {
          target: 'http://<rag_be_address>:<rag_be_port>',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api1/, '/api'), // This rewrites /api1 to /api
          secure: false, // Set to true for production if target is HTTPS and has valid cert.
                        // Set to false for dev if you're getting SSL errors with self-signed or invalid certs.
        },
        // Proxy for api2 (assuming this is still local or another service)
        '/api2': {
          target: 'http://<multiagent_be_address>:<multiagent_be_port>',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api2/, '/api'), // This rewrites /api2 to /api
          // secure: false, // Only needed if this target is HTTPS and you have SSL issues
        },
        // You can add more proxies here if needed
      }
    },
    ```

## Analyzing the UI Build (Optional)

In order to analyze the UI build bundle, we need a build analyzer tool. Since Vite (the tool for building and serving) is using Rollup, we can use the `rollup-plugin-visualizer`.

1.  Start by installing the plugin:
    `pnpm add -D rollup-plugin-visualizer`

**NOTE: Currently, Vite is being enabled only when building locally (when the NODE_ENV environment variable is not set to 'production'). In order to run the analyzer, set the environment variable `NODE_ENV="development"`. After the build, a new file will be created and opened automatically, analyzing the bundle of the UI.**

## Appendixes

### UI Building Infra

#### Tools
* PNPM - Package manager
* Vite - Code building and serving tool

#### Important Files

* `package.json`

    Includes all packages needed for our app.
    Includes a `scripts` part. In this part, when we run a builder/installer, it goes to the `scripts` part, and if the arguments are there, it takes them.
    For example:

    ```
    "scripts": {
      "build:frontend": "vite build",
      "build": "pnpm run build:frontend",
    }
    ```

    When we run `pnpm build` or `pnpm run build`, it first goes to the `scripts` part and sees that it needs to run the command: `pnpm run build:frontend`, which in turn changes `build:frontend` to `vite build`. So, the actual final command is `vite build`.
    NOTE: If your script line includes `pnpm run <command>`, this will send PNPM again to the `scripts` part to look for a line named `<command>`.

* `pnpm-lock.yaml`

    Lock files are more specific package dependency files. In `package.json`, we usually give a range or general rules as to what versions are allowed/required. But when we actually install the packages, we get specific versions. This is listed in the lock files, and it allows us to use them as the base for future installations and prevent conflicts and problems due to version issues.

    In our case, since we use PNPM, the lock file to use is `pnpm-lock.yaml`.

    **NOTE: If you need to update a package and reinstall, you'll need to update the lock file (or run `install` to overwrite the lock file and push it after install + build are successful).**

* `vite.config.ts`

    As we use Vite as the build tool, we need to have the Vite configuration file set. In it, we set the input/output folders, proxies, and plugins we want to use during our build. The syntax is TypeScript.
