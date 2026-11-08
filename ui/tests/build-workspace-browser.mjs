/** Build the production App for owned signed-cookie browser scenarios. */
import { build } from 'vite';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
if (!process.argv[2]) throw new Error('Supply a temporary output directory');
await build({
  configFile: resolve(root, 'vite.config.ts'), root: resolve(root, 'tests'),
  base: '/fixture/ui/', build: {
    outDir: resolve(process.argv[2]), emptyOutDir: true,
    rollupOptions: { input: [
      resolve(root, 'tests/workspace-browser.html'),
    ] },
  },
});
