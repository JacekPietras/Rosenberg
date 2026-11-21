#!/usr/bin/env node
// Normalize fact participant names with the same recognition rules used by the app.
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { relative, resolve } from 'node:path';
import { personRouteName } from '../../docs/app/data/person-name-recognition.js';
import { acceptNormalizedName } from './name_guard.mjs';

const root = resolve(import.meta.dirname, '../..');
const read = (path) => readFile(resolve(root, path), 'utf8');
const [names, byNames, particles, connectors, places, ageTitles, officeTitles, registry] = await Promise.all([
  read('data/names.md'), read('data/by-names.md'), read('data/nobiliary_particles.md'),
  Promise.all(['data/name-connectors.md', 'data/title-seats.md'].map(read)).then((texts) => texts.join('\n')), read('data/places.json'), read('data/titles-age.md'),
  read('data/titles-office.md'), read('data/people.json'),
]);
const titleText = `${ageTitles}\n${officeTitles}`;
const knownIds = new Set(JSON.parse(registry).map((person) => person.id));
const args = [titleText, connectors, particles, names, byNames, JSON.parse(places)];

async function jsonFiles(directory) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) files.push(...await jsonFiles(path));
    else if (entry.isFile() && entry.name.endsWith('.json') && !path.endsWith('/tree.json')) files.push(path);
  }
  return files;
}

function visit(value, file, pointer, changes) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => visit(item, file, `${pointer}/${index}`, changes));
  } else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (key === 'facts' || key === 'guesses') {
        if (!Array.isArray(child)) continue;
        child.forEach((fact, index) => {
          if (!fact || typeof fact !== 'object' || Array.isArray(fact)) return;
          for (const field of ['person', 'of']) {
            const name = fact[field];
            if (typeof name !== 'string' || knownIds.has(name) || name.includes('_')) continue;
            const canonical = personRouteName(name, ...args);
            if (canonical && canonical !== name && acceptNormalizedName(name, canonical)) {
              changes.push({ fact, field, pointer: `${pointer}/${key}/${index}`, name, canonical });
            }
          }
        });
      } else visit(child, file, `${pointer}/${key}`, changes);
    }
  }
}

let count = 0;
for (const file of await jsonFiles(resolve(root, 'data'))) {
  let data;
  try { data = JSON.parse(await readFile(file, 'utf8')); }
  catch { continue; } // The schema linter reports malformed JSON.
  const changes = [];
  visit(data, file, '', changes);
  if (!changes.length) continue;
  for (const change of changes) {
    console.log(`${relative(root, file)}#${change.pointer}/${change.field}: fixed: ${JSON.stringify(change.name)} -> ${JSON.stringify(change.canonical)}`);
    change.fact[change.field] = change.canonical;
    count += 1;
  }
  await writeFile(file, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
}
console.log(`Normalized ${count} fact participant name(s).`);
