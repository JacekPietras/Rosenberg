#!/usr/bin/env node
// Complete personTitle/ofTitle of facts with titles the entry's generated
// `mention` list gives the same person. Run after generate_mentions.mjs; the
// mentions are regenerated afterwards. Reports by default; `--apply` writes.
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { relative, resolve } from 'node:path';
import {
  parsePersonNameTitles, personRouteName,
} from '../../docs/app/data/person-name-recognition.js';
import { parsePlaces } from '../../docs/app/data/entities.js';

const root = resolve(import.meta.dirname, '../..');
const apply = process.argv.includes('--apply');
const read = (file) => readFile(resolve(root, 'data', file), 'utf8');
const [names, particles, placesJson, byNames, connectors, ageText, officeText, peopleJson] = await Promise.all(
  ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md',
    'titles-age.md', 'titles-office.md', 'people.json'].map(read));
const titleText = `${ageText}\n${officeText}`;
const places = parsePlaces(placesJson);
const registry = new Map(JSON.parse(peopleJson).map((person) => [person.id, person.name]));
const route = (name) => personRouteName(name, titleText, connectors, particles, names, byNames, places);

const lower = (value) => value.toLocaleLowerCase();
const forms = (text) => text.split(/\r?\n/).filter((line) => line.trim() && !line.trim().startsWith('#')
  && !line.trim().startsWith('//')).map((line) => parsePersonNameTitles(line));
const groupOf = new Map();
const ageOf = new Map();
for (const group of forms(titleText)) {
  for (const form of group) groupOf.set(lower(form), group[0]);
}
let ageClass = null;
for (const line of ageText.split(/\r?\n/)) {
  const header = line.match(/^#\s*(\w+)/u);
  if (header) ageClass = header[1];
  else for (const form of parsePersonNameTitles(line)) ageOf.set(lower(groupOf.get(lower(form)) ?? form), ageClass);
}
const byNameForms = new Set(forms(byNames).flat().map(lower));
const placeCanonical = new Map(places.flatMap((place) => place.variations.map((form) => [lower(form), place.variations[0]])));

const escape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
const titleForms = [...groupOf.keys()].filter((form) => !byNameForms.has(form)).sort((a, b) => b.length - a.length);
const titlePattern = new RegExp(`(?<![\\p{L}\\p{N}])(${titleForms.map(escape).join('|')})(?:\\s+(?:zu|zum|an|of)\\s+([\\p{L}][\\p{L}'’.-]*))?(?![\\p{L}\\p{N}])`, 'giu');

function titlesOf(mention) {
  const found = [];
  for (const match of mention.matchAll(titlePattern)) {
    const base = groupOf.get(lower(match[1]));
    const age = ageOf.has(lower(base));
    const place = match[2] && !age && placeCanonical.get(lower(match[2]));
    if (match[2] && !age && !place) continue;
    if (match[2] && age) continue;
    found.push(place ? `${base} zu ${place}` : base);
  }
  return found;
}
const baseOf = (title) => {
  const form = titleForms.find((candidate) => lower(title) === candidate || lower(title).startsWith(`${candidate} `));
  return form ? groupOf.get(form) : title;
};
const placeOf = (title) => {
  const place = title.split(' zu ')[1];
  return place && lower(placeCanonical.get(lower(place)) ?? place);
};
const ageOfTitles = (titles) => [...new Set(titles.map((title) => ageOf.get(lower(baseOf(title)))).filter(Boolean))];

function participants(entry) {
  const result = [];
  for (const fact of entry.facts ?? []) {
    if (!fact || typeof fact !== 'object' || fact.type === 'title' || fact.date !== undefined) continue;
    for (const [field, titleField] of [['person', 'personTitle'], ['of', 'ofTitle']]) {
      const name = fact[field];
      if (typeof name !== 'string') continue;
      if (registry.has(name)) {
        result.push({ fact, field, titleField, key: route(registry.get(name)), registered: true, existing: [] });
        continue;
      }
      if (route(name) !== name) continue;
      result.push({ fact, field, titleField, key: route(name), existing: fact[titleField] ?? [], deceased: Boolean(fact[`${field}Deceased`]) });
    }
  }
  return result;
}

function canonicalTitle(title) {
  const found = titlesOf(title);
  if (found.length === 1) return found[0];
  const place = title.match(/^zu\s+(\S+)$/iu);
  const canonical = place && placeCanonical.get(lower(place[1]));
  return canonical ? `zu ${canonical}` : null;
}

function mentionsOf(entry) {
  return (entry.mention ?? []).filter((item) => typeof item.person === 'string').map((item) => ({
    key: item.person,
    titles: (item.personTitle ?? []).map(canonicalTitle).filter(Boolean),
  }));
}

const known = (title) => baseOf(title) !== title || title.startsWith('zu ');
const offices = (titles) => new Set(titles.filter((title) => !ageOf.has(lower(baseOf(title)))).map(baseOf));
const overlaps = (left, right) => [...left].some((item) => right.has(item));

function enrich(entry, report) {
  const people = participants(entry);
  if (!people.length) return;
  const mentions = mentionsOf(entry);
  for (const key of new Set(people.map((person) => person.key))) {
    const mine = people.filter((person) => person.key === key);
    if (mine.some((person) => person.registered)) continue;
    if (new Set(mine.map((person) => person.deceased)).size > 1
      || mine.some((person) => person.fact.person === person.fact.of)) continue;
    if (mine.some((person) => people.some((other) => other.fact === person.fact && other !== person && other.key === key))) continue;
    const theirs = mentions.filter((mention) => mention.key === key);
    const classes = new Set([...mine.map((p) => p.existing), ...theirs.map((m) => m.titles)].flatMap(ageOfTitles));
    const titled = [...mine.map((p) => p.existing), ...theirs.map((m) => m.titles)]
      .map(offices).filter((set) => set.size);
    const ambiguous = titled.some((left) => titled.some((right) => !overlaps(left, right)));
    for (const person of mine) {
      const own = ageOfTitles(person.existing)[0];
      if (classes.size && !own) continue;
      const mine_ = offices(person.existing);
      if (ambiguous && !mine_.size) continue;
      const sources = [...theirs.map((m) => m.titles), ...mine.map((p) => p.existing)]
        .filter((titles) => classes.size < 2 || !ageOfTitles(titles).length || ageOfTitles(titles)[0] === own)
        .filter((titles) => !ambiguous || overlaps(mine_, offices(titles)));
      const added = [];
      for (const title of sources.flat().filter((item) => known(item) || ageOf.has(lower(item)) || theirs.some((m) => m.titles.includes(item)))) {
        const covered = [...person.existing, ...added].some((have) => lower(have) === lower(title)
          || lower(have).startsWith(lower(title)) || lower(have).includes(lower(baseOf(title)))
          || (ageOf.has(lower(baseOf(title))) && ageOf.get(lower(baseOf(have))) === ageOf.get(lower(baseOf(title))))
          || (baseOf(have) === baseOf(title) && (!placeOf(title) || placeOf(have))));
        if (!covered) added.push(title);
      }
      if (added.length) report.push({ person, added });
    }
  }
}

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
      const found = [];
      enrich(value, found);
      for (const item of found) report.push({ ...item, pointer });
    }
    for (const [key, child] of Object.entries(value)) if (key !== 'facts' && key !== 'guesses') visit(child, `${pointer}/${key}`, report);
  }
}

async function jsonFiles(directory) {
  const results = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) results.push(...await jsonFiles(path));
    else if (entry.isFile() && entry.name.endsWith('.json')) results.push(path);
  }
  return results;
}

let findings = 0;
for (const file of (await jsonFiles(resolve(root, 'data'))).filter((path) => !/\/(tree|people|places|matching)\.json$/.test(path))) {
  let data;
  try { data = JSON.parse(await readFile(file, 'utf8')); } catch { continue; }
  const report = [];
  visit(data, '', report);
  if (!report.length) continue;
  const grouped = new Map();
  for (const { person, added, pointer } of report) {
    const slot = grouped.get(person.fact) ?? { person, pointer, roles: [] };
    slot.roles.push({ person, added });
    grouped.set(person.fact, slot);
  }
  for (const { pointer, roles } of grouped.values()) {
    for (const { person, added } of roles) {
      const merged = [...person.existing, ...added];
      console.log(`${relative(root, file)}#${pointer}: ${person.fact[person.field]} ${JSON.stringify(person.existing)} += ${JSON.stringify(added)}`);
      if (apply) withTitles(person.fact, person.field, person.titleField, merged);
      findings += 1;
    }
  }
  if (apply) await writeFile(file, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
}
console.log(`Checked fact titles against entry text: ${findings} finding(s)${apply ? ' applied' : ''}.`);
