// Deploy the built dashboard into the dir the Python control-plane server serves.
// Source lives in ~/.agents/dashboard-app; the server serves ~/.agents/dashboard
// at the /dashboard/ URL path. We build to ./dist then sync into ../dashboard.
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const projectDir = resolve(here, '..');
const dist = join(projectDir, 'dist');
const target = resolve(projectDir, '..', 'dashboard');

if (!existsSync(join(dist, 'index.html'))) {
  console.error(`[deploy] no build found at ${dist} (run the build first)`);
  process.exit(1);
}

mkdirSync(target, { recursive: true });
// Clean the served dir (no backward-compat artifacts), then copy the fresh build.
for (const entry of readdirSync(target)) {
  rmSync(join(target, entry), { recursive: true, force: true });
}
cpSync(dist, target, { recursive: true });
console.log(`[deploy] synced ${dist} -> ${target}`);
