#!/usr/bin/env node
// Complete personTitle/ofTitle of facts with titles the entry's generated
// `mention` list gives the same person, after writing every title in canonical form. Run after generate_mentions.mjs; the
// mentions are regenerated afterwards. Reports by default; `--apply` writes.
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { relative, resolve } from 'node:path';
import { personRouteName } from '../../docs/app/data/person-name-recognition.js';
import { parsePlaces } from '../../docs/app/data/entities.js';
import { titleForms } from './title_forms.mjs';
import { enrichEntry } from './fact_title_enrichment.mjs';

const root = resolve(import.meta.dirname, '../..');
const apply = process.argv.includes('--apply');
const readData = (file) => readFile(resolve(root, 'data', file), 'utf8');
const read = (file) => (file === 'name-connectors.md'
  ? Promise.all(['name-connectors.md', 'title-seats.md'].map(readData)).then((texts) => texts.join('\n')) : readData(file));
const [names, particles, placesJson, byNames, connectors, ageText, officeText, peopleJson] = await Promise.all(
  ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md',
    'titles-age.md', 'titles-office.md', 'people.json'].map(read));
const titleText = `${ageText}\n${officeText}`;
const places = parsePlaces(placesJson);
const registry = new Map(JSON.parse(peopleJson).map((person) => [person.id, person.name]));
const route = (name) => personRouteName(name, titleText, connectors, particles, names, byNames, places);

function withTitles(fact, field, titleField, titles) {
  const entries = Object.entries(fact).filter(([key]) => key !== titleField);
  const index = entries.findIndex(([key]) => key === field) + 1;
  entries.splice(index, 0, [titleField, titles]);
  for (const key of Object.keys(fact)) delete fact[key];
  Object.assign(fact, Object.fromEntries(entries));
}

function visit(value, pointer, report) {
  if (Array.isArray(value)) value.forEach((item, index) => visit(item, `${pointer}/${index}`, report));
  else if (value && typeof value === 'object') {
    if (Array.isArray(value.facts)) {
      for (const item of enrichEntry(value, { route, registry, titles: titleForms })) report.push({ ...item, pointer });
    }
    for (const [key, child] of Object.entries(value)) if (key !== 'facts' && key !== 'guesses') visit(child, `${pointer}/${key}`, report);
  }
}

async function jsonFiles(directory) {
  if (directory === resolve(root, 'data/documents/deleted')) return [];
  const results = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) results.push(...await jsonFiles(path));
    else if (entry.isFile() && entry.name.endsWith('.json')) results.push(path);
  }
  return results;
}

function normalizeTitles(value, changes) {
  if (Array.isArray(value)) value.forEach((item) => normalizeTitles(item, changes));
  else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if ((key === 'personTitle' || key === 'ofTitle') && Array.isArray(child) && child.every((item) => typeof item === 'string')) {
        const canonical = titleForms.consolidateTitles(child);
        if (JSON.stringify(canonical) !== JSON.stringify(child)) {
          changes.push({ before: child, after: canonical });
          if (apply) value[key] = canonical;
        }
      } else if (key !== 'mention') normalizeTitles(child, changes);
    }
  }
}

let findings = 0;
for (const file of (await jsonFiles(resolve(root, 'data'))).filter((path) => !/\/(tree|people|places|matching)\.json$/.test(path))) {
  let data;
  try { data = JSON.parse(await readFile(file, 'utf8')); } catch { continue; }
  const report = [];
  const normalized = [];
  normalizeTitles(data, normalized);
  for (const { before, after } of normalized) {
    console.log(`${relative(root, file)}: ${JSON.stringify(before)} -> ${JSON.stringify(after)}`);
    findings += 1;
  }
  visit(data, '', report);
  if (!report.length && !normalized.length) continue;
  const grouped = new Map();
  for (const { person, added, final, pointer } of report) {
    const slot = grouped.get(person.fact) ?? { person, pointer, roles: [] };
    slot.roles.push({ person, added, final });
    grouped.set(person.fact, slot);
  }
  for (const { pointer, roles } of grouped.values()) {
    for (const { person, added, final } of roles) {
      const merged = final;
      console.log(`${relative(root, file)}#${pointer}: ${person.fact[person.field]} ${JSON.stringify(person.existing)} += ${JSON.stringify(added)} -> ${JSON.stringify(final)}`);
      if (apply) withTitles(person.fact, person.field, person.titleField, merged);
      findings += 1;
    }
  }
  if (apply) await writeFile(file, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
}
console.log(`Checked fact titles against entry text: ${findings} finding(s)${apply ? ' applied' : ''}.`);
