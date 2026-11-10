#!/usr/bin/env node
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const repo = join(dirname(fileURLToPath(import.meta.url)), '..');
const pluginPath = join(repo, 'plugins', 'joshfinnie-skills', '.claude-plugin', 'plugin.json');

const { version } = JSON.parse(readFileSync(join(repo, 'package.json'), 'utf8'));
const source = readFileSync(pluginPath, 'utf8');
const plugin = JSON.parse(source);

if (plugin.version === version) {
  console.log(`plugin.json is at ${version}`);
  process.exit(0);
}

if (process.argv.includes('--check')) {
  console.error(`plugin.json is at ${plugin.version} but package.json is at ${version}. Run \`pnpm run version\`.`);
  process.exit(1);
}

writeFileSync(pluginPath, source.replace(/("version"\s*:\s*")[^"]*(")/, `$1${version}$2`));
console.log(`plugin.json ${plugin.version} -> ${version}`);
