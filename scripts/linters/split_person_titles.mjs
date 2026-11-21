#!/usr/bin/env node
// Find titles embedded in fact participant names and move them to the
// corresponding personTitle/ofTitle arrays.
import { readFile, writeFile } from 'node:fs/promises';
import { resolve, relative } from 'node:path';
import { pathToFileURL } from 'node:url';
import { splitPersonNameTitles } from '../../docs/app/data/person-name-recognition.js';
import { acceptTitleSplit } from './name_guard.mjs';
import { titleForms } from './title_forms.mjs';

const root = resolve(import.meta.dirname, '../..');
const apply = !process.argv.includes('--check');
const titleText = [
  await readFile(resolve(root, 'data/titles-age.md'), 'utf8'),
  await readFile(resolve(root, 'data/titles-office.md'), 'utf8'),
].join('\n');

async function jsonFiles(directory) {
  const { readdir } = await import('node:fs/promises');
  const results = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) results.push(...await jsonFiles(path));
    else if (entry.isFile() && entry.name.endsWith('.json')) results.push(path);
  }
  return results;
}

function visit(value, file, pointer, changes) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => visit(item, file, `${pointer}/${index}`, changes));
  } else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (key === 'facts' || key === 'guesses') {
        if (Array.isArray(child)) child.forEach((fact, index) => {
          if (!fact || typeof fact !== 'object' || Array.isArray(fact)) return;
          for (const [nameField, titleField] of [['person', 'personTitle'], ['of', 'ofTitle']]) {
            if (typeof fact[nameField] !== 'string') continue;
            const split = splitPersonNameTitles(fact[nameField], titleText);
            if (!split.titles.length || !acceptTitleSplit(fact[nameField], split)) continue;
            changes.push({ fact, nameField, titleField, pointer: `${pointer}/${key}/${index}`,
              original: fact[nameField], ...split });
          }
        });
      } else visit(child, file, `${pointer}/${key}`, changes);
    }
  }
}

let findings = 0;
for (const file of (await jsonFiles(resolve(root, 'data'))).filter((path) => !path.endsWith('/tree.json'))) {
  let data;
  try { data = JSON.parse(await readFile(file, 'utf8')); }
  catch { continue; } // The schema linter reports malformed JSON.
  const changes = [];
  visit(data, file, '', changes);
  if (!changes.length) continue;
  for (const change of changes) {
    const existing = Array.isArray(change.fact[change.titleField]) ? change.fact[change.titleField] : [];
    const moved = change.titles.filter((title) => !existing.includes(title));
    console.log(`${relative(root, file)}#${change.pointer}/${change.nameField}: ${JSON.stringify(change.original)} -> ${JSON.stringify(change.name)}; ${change.titleField} += ${JSON.stringify(moved)}`);
    if (apply) {
      change.fact[change.nameField] = change.name;
      change.fact[change.titleField] = titleForms.canonicalTitles([...existing, ...moved]);
    }
    findings += 1;
  }
  if (apply) await writeFile(file, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
}
console.log(`Checked fact participant names: ${findings} finding(s)${apply ? ' applied' : ''}.`);
process.exitCode = findings && !apply ? 1 : 0;
