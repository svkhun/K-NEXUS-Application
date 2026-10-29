// Fingerprint actual source bytes and built assets, without a self-referential commit.
import { createHash } from 'node:crypto';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join, relative } from 'node:path';
const root = process.cwd();
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
async function walk(dir) {
  const files = [];
  for (const item of await readdir(join(root, dir), { withFileTypes: true })) {
    if (item.name === '__pycache__' || item.name.endsWith('.pyc')) continue;
    const name = join(dir, item.name);
    if (item.isDirectory()) files.push(...await walk(name)); else files.push(name);
  }
  return files;
}
const inputs = ['index.html', 'vite.config.js', 'package.json', 'package-lock.json',
  'requirements.lock', 'requirements.txt', 'Dockerfile', 'run.py', 'scripts/build_release.mjs',
  'data/01_flowsense_user_profiles.csv', 'data/03_trustgraph_users_and_mule_labels.csv'];
for (const dir of ['src', 'public', 'config', 'models']) inputs.push(...await walk(dir));
const sources = {};
for (const path of inputs.sort()) sources[path.replaceAll('\\', '/')] = hash(await readFile(join(root, path)));
const assets = {};
for (const path of (await walk('frontend/dist')).sort()) {
  if (path.endsWith('release.json')) continue;
  assets[relative('frontend/dist', path).replaceAll('\\', '/')] = hash(await readFile(join(root, path)));
}
const release = { release_id: 'application-scenario-ux-20261030.1',
  source_sha256: hash(JSON.stringify(sources)), source_files: sources, assets,
  baseline_policy: 'history28-min7-scenario-abstain.v1', adapter: 'live-intraday-next-day.v1',
  assumption_version: 'synthetic-persona-assumptions.2026-10-29.1', synthetic_only: true };
release.demo_initialization_version = JSON.parse(await readFile(join(root, 'config/demo-initialization.v1.json'))).version;
await writeFile(join(root, 'frontend/dist/release.json'), JSON.stringify(release, null, 2)+'\n');
console.log(JSON.stringify({release_id:release.release_id, source_sha256:release.source_sha256, assets:Object.keys(assets)}));
