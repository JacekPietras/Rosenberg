#!/usr/bin/env node
// Regenerate every `mention` list: the people recognized in a document entry's
// `english` text and in each generic fact's `content`. Existing lists are
// discarded first, so the output depends only on the text and the dictionaries.
// `--check` reports files whose stored lists are stale and exits non-zero.
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { relative, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import {
  buildSourcePersonPattern, findPersonNameMentions, parsePersonNameTitles, splitPersonNameTitles,
} from '../../docs/app/data/person-name-recognition.js';
import { parsePlaces } from '../../docs/app/data/entities.js';

const root = resolve(import.meta.dirname, '../..');
const check = process.argv.includes('--check');
const read = (path) => readFile(resolve(root, path), 'utf8').catch(() => '');
const titleText = [await read('data/titles-age.md'), await read('data/titles-office.md')].filter(Boolean).join('\n');
const args = [titleText, await read('data/name-connectors.md'), await read('data/nobiliary_particles.md'),
  await read('data/names.md'), await read('data/by-names.md'), JSON.parse(await read('data/places.json'))];
const pattern = buildSourcePersonPattern(args[3], args[2], args[5], args[0], args[1], args[4]);
const places = parsePlaces(await read('data/places.json'));
const placeForms = new Map();
for (const [index, place] of places.entries()) {
  const key = place.id || place.name || `@place/${index}`;
  for (const form of place.variations || []) {
    if (!placeForms.has(form)) placeForms.set(form, new Set());
    placeForms.get(form).add(key);
  }
}
const placePatterns = [...placeForms].map(([form, keys]) => ({
  keys,
  pattern: new RegExp(`(?<![\\p{L}\\p{N}])${form.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s*,\s*/g, '\\s*,\\s*').replace(/\s+/g, '\\s+')}(?![\\p{L}\\p{N}])`, 'giu'),
}));
const knownTitles = parsePersonNameTitles(titleText).sort((left, right) => right.length - left.length);
const escape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
const leadingTitle = knownTitles.length
  ? new RegExp(`^(${knownTitles.map(escape).join('|')})(?:\\s+(?:zu|zum|an|of)\\s+[\\p{L}][\\p{L}'’.-]*)?[\\s,;]+`, 'iu') : null;


const ageGroups = [];
for (const line of (await read('data/titles-age.md')).split(/\r?\n/)) {
  if (line.trim().startsWith('#')) ageGroups.push(new Set());
  else if (ageGroups.length) parsePersonNameTitles(line).forEach((form) => ageGroups.at(-1).add(form.toLowerCase()));
}
const ageOf = (titles = []) => new Set(titles.flatMap((title) => ageGroups
  .flatMap((group, index) => (group.has(title.toLowerCase()) ? [index] : []))));
const sameAge = (left, right) => left.size === right.size && [...left].every((index) => right.has(index));

// People with the same name are one mention unless both carry different age titles.
function mergePeople(items) {
  const groups = new Map();
  const others = [];
  for (const item of items) {
    if (item.person === undefined) { others.push(item); continue; }
    if (!groups.has(item.person)) groups.set(item.person, []);
    groups.get(item.person).push(item);
  }
  const merged = [];
  for (const [person, list] of groups) {
    const clusters = [];
    const plain = [];
    for (const item of list) {
      const age = ageOf(item.personTitle);
      if (!age.size) { plain.push(item); continue; }
      const cluster = clusters.find((entry) => sameAge(entry.age, age));
      if (cluster) cluster.titles.push(...item.personTitle);
      else clusters.push({ age, titles: [...item.personTitle] });
    }
    if (!clusters.length) clusters.push({ age: new Set(), titles: [] });
    plain.forEach((item) => clusters[0].titles.push(...(item.personTitle || [])));
    for (const cluster of clusters) {
      const titles = [...new Set(cluster.titles)].sort();
      merged.push(titles.length ? { person, personTitle: titles } : { person });
    }
  }
  return [...merged, ...others];
}

function surfaceTitles(text) {
  const titles = [];
  let rest = text;
  for (let match = leadingTitle?.exec(rest); match; match = leadingTitle.exec(rest)) {
    titles.push(match[1]);
    rest = rest.slice(match[0].length);
  }
  return [...titles, ...splitPersonNameTitles(rest, titleText).titles];
}

function recognizePeople(text) {
  const { coordinated, singles } = findPersonNameMentions(text, ...args, pattern);
  const spans = [...singles, ...coordinated].map(({ start, end }) => [start, end]);
  const people = [
    ...singles.map((item) => ({ person: item.route, titles: surfaceTitles(item.text) })),
    ...coordinated.flatMap((group) => group.routes.map((person) => ({ person, titles: group.titles }))),
  ];
  return { people, spans };
}

function recognizePlaces(text, spans) {
  let masked = text;
  for (const [start, end] of spans) masked = masked.slice(0, start) + ' '.repeat(end - start) + masked.slice(end);
  const matches = [];
  for (const { keys, pattern: placePattern } of placePatterns) {
    for (const match of masked.matchAll(placePattern)) {
      matches.push({ start: match.index, end: match.index + match[0].length, keys });
    }
  }
  const taken = [];
  const found = new Set();
  const byLength = new Map();
  for (const match of matches) {
    const key = `${match.start}:${match.end}`;
    const merged = byLength.get(key) || { ...match, keys: new Set() };
    match.keys.forEach((value) => merged.keys.add(value));
    byLength.set(key, merged);
  }
  for (const match of [...byLength.values()].sort((a, b) => (b.end - b.start) - (a.end - a.start) || a.start - b.start)) {
    if (taken.some(([start, end]) => match.start < end && match.end > start)) continue;
    taken.push([match.start, match.end]);
    if (match.keys.size === 1) found.add([...match.keys][0]);
  }
  return [...found].sort();
}

export function recognizeMentions(text, { placesOnly = false } = {}) {
  if (!pattern || typeof text !== 'string' || !text.trim()) return [];
  const plain = text.replace(/[\[\]]/g, ' ');
  const { people, spans } = placesOnly ? { people: [], spans: [] } : recognizePeople(plain);
  const items = [
    ...people.map(({ person, titles }) => (titles.length
      ? { person, personTitle: [...new Set(titles)].sort() } : { person })),
    ...recognizePlaces(plain, spans).map((place) => ({ place })),
  ];
  const unique = new Map(mergePeople(items).map((item) => [JSON.stringify(item), item]));
  const name = (item) => item.person ?? item.place;
  return [...unique.values()].sort((left, right) => name(left).localeCompare(name(right))
    || JSON.stringify(left).localeCompare(JSON.stringify(right)));
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

const factTexts = (entry) => (Array.isArray(entry.facts) ? entry.facts : [])
  .flatMap((fact) => (fact?.type === 'generic' && typeof fact.content === 'string' ? [fact.content]
    : fact?.type === 'death' && typeof fact.circumstances === 'string' ? [fact.circumstances] : []));


const personKey = (person, titles) => JSON.stringify([person, [...new Set(titles || [])].sort()]);

// Person+title pairs already stated by a fact (or its nested facts) need no mention.
function statedPeople(value, found = new Set()) {
  if (Array.isArray(value)) value.forEach((item) => statedPeople(item, found));
  else if (value && typeof value === 'object') {
    if (typeof value.person === 'string') found.add(personKey(value.person, value.personTitle));
    if (typeof value.of === 'string') found.add(personKey(value.of, value.ofTitle));
    Object.entries(value).forEach(([key, child]) => { if (key !== 'mention') statedPeople(child, found); });
  }
  return found;
}

function regenerate(value, file, counter, issuance = []) {
  if (Array.isArray(value)) {
    value.forEach((item) => regenerate(item, file, counter, issuance));
    return;
  }
  if (!value || typeof value !== 'object') return;
  delete value.mention;
  const isDocument = file.includes('/data/documents/') && Array.isArray(value.entries);
  const hasEnglish = typeof value.english === 'string' && file.includes('/data/documents/');
  const isEntry = !isDocument && (hasEnglish || Array.isArray(value.facts) || Array.isArray(value.guesses));
  if (isEntry) {
    const texts = [...(hasEnglish ? [value.english] : []), ...factTexts(value)];
    const items = [...texts.flatMap((text) => recognizeMentions(text)), ...issuance];
    const unique = new Map(mergePeople(items).map((item) => [JSON.stringify(item), item]));
    const name = (item) => item.person ?? item.place;
    const stated = statedPeople(value.facts ?? (value.type ? value : null));
    const mention = [...unique.values()]
      .filter((item) => item.person === undefined || !stated.has(personKey(item.person, item.personTitle)))
      .sort((left, right) => name(left).localeCompare(name(right))
        || JSON.stringify(left).localeCompare(JSON.stringify(right)));
    if (mention.length) {
      const entries = Object.entries(value);
      for (const key of Object.keys(value)) delete value[key];
      for (const [key, child] of entries) {
        value[key] = child;
        if (key === 'english') value.mention = mention;
      }
      if (!value.mention) value.mention = mention;
      counter.mentions += mention.length;
    }
  }
  const childIssuance = isDocument && typeof value.place === 'string'
    ? recognizeMentions(value.place, { placesOnly: true }) : [];
  Object.entries(value).forEach(([key, child]) => {
    if (key === 'mention') return;
    regenerate(child, file, counter, key === 'entries' ? childIssuance : []);
  });
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) await main();

async function main() {
const counter = { mentions: 0, files: 0, stale: 0 };
for (const file of (await jsonFiles(resolve(root, 'data')))
  .filter((path) => !/\/(tree|people|places|matching)\.json$/.test(path)).sort()) {
  const original = await readFile(file, 'utf8');
  let data;
  try { data = JSON.parse(original); } catch { continue; }
  regenerate(data, file, counter);
  const updated = JSON.stringify(data, null, 2) + (original.endsWith('\n') ? '\n' : '');
  counter.files += 1;
  if (updated === original) continue;
  counter.stale += 1;
  console.log(`${check ? 'Stale mentions' : 'Updated mentions'}: ${relative(root, file)}`);
  if (!check) await writeFile(file, updated, 'utf8');
}
if (counter.stale > 0) {
  console.log(`Checked mentions: ${counter.files} files, ${counter.mentions} mentions, ${counter.stale} ${check ? 'stale' : 'updated'}.`);
}
process.exitCode = check && counter.stale ? 1 : 0;
}
