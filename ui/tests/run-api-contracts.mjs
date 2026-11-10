/** Compile and execute the real API clients with the UI's existing Vite dependency. */
import { mkdir, mkdtemp, rm } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { build } from 'vite';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const suites = {
  api: 'editor-resources.ts', blueprints: 'editor-blueprints.ts', sessions: 'chat-sessions.ts',
  shares: 'sharing-notifications.ts', reviews: 'human-reviews.ts', programs: 'program-composition.ts', contracts: 'ui-contracts.ts',
  access: 'workflow-access.ts',
  consent: 'schedule-consent.ts',
  events: 'program-events.ts',
  reporting: 'reporting.ts',
  administration: 'administration.ts',
  builtins: 'builtin-administration.ts',
  curated_inspection: 'curated-inspection.ts',
};
const suite = process.argv[2] ?? 'api';
if (!Object.hasOwn(suites, suite)) throw new Error(`Unknown UI contract suite: ${suite}`);
const cache = join(root, 'node_modules/.cache');
await mkdir(cache, { recursive: true });
const directory = await mkdtemp(join(cache, 'lumora-api-tests-'));
try {
  await build({
    configFile: false,
    logLevel: 'warn',
    resolve: { alias: { '@': join(root, 'client/src') } },
    build: {
      ssr: join(root, 'tests', suites[suite]),
      outDir: directory,
      rollupOptions: { output: { format: 'cjs', exports: 'named', entryFileNames: 'editor-client.cjs' } },
    },
  });
  const { default: verify } = createRequire(import.meta.url)(join(directory, 'editor-client.cjs'));
  await verify();
} catch (error) {
  console.error(error instanceof Error ? error.message : 'Editor API contract failed');
  process.exitCode = 1;
} finally {
  await rm(directory, { recursive: true, force: true });
}
