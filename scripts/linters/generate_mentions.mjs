#!/usr/bin/env node
// Regenerate every `mention` list: the people recognized in a document entry's
// `english` text and in each generic fact's `content`. Existing lists are
// discarded first, so the output depends only on the text and the dictionaries.
// `--check` reports files whose stored lists are stale and exits non-zero.
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { relative, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { availableParallelism } from 'node:os';
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import { buildSourcePersonPattern, findPersonNameMentions } from '../../docs/app/data/person-name-recognition.js';
import { parsePlaces } from '../../docs/app/data/entities.js';
import { titleForms } from './title_forms.mjs';

const root = resolve(import.meta.dirname, '../..');
const check = process.argv.includes('--check');
const read = (path) => readFile(resolve(root, path), 'utf8').catch(() => '');
const registry = new Map(JSON.parse(await read('data/people.json')).map((person) => [person.id, person.name]));
const titleText = [await read('data/titles-age.md'), await read('data/titles-office.md')].filter(Boolean).join('\n');
const args = [titleText, [await read('data/name-connectors.md'), await read('data/title-seats.md')].join('\n'), await read('data/nobiliary_particles.md'),
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


// Same-route items are one mention only when their titles are compatible.
const mergePeople = (items) => titleForms.mergePeople(items);
const consolidateTitles = (titles) => titleForms.consolidateTitles(titles);

function recognizePeople(text) {
  const { coordinated, singles } = findPersonNameMentions(text, ...args, pattern);
  const spans = [...singles, ...coordinated].map(({ start, end }) => [start, end]);
  const people = [
    ...singles.map((item) => ({ person: item.route, titles: item.titles })),
    ...coordinated.flatMap((group) => group.members.map((member) => ({ person: member.route, titles: member.titles }))),
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

export function recognizeMentions(text, { placesOnly = false, stated = new Map() } = {}) {
  if (!pattern || typeof text !== 'string' || !text.trim()) return [];
  const plain = text.replace(/[\[\]]/g, ' ');
  const { people, spans } = placesOnly ? { people: [], spans: [] } : recognizePeople(plain);
  const items = [
    ...people.map(({ person, titles }) => (titles.length
      ? { person, personTitle: consolidateTitles(titles).sort() } : { person })),
    ...recognizePlaces(plain, spans).map((place) => ({ place })),
  ];
  const remaining = items.filter((item) => item.person === undefined || !isStated(item, stated));
  const unique = new Map(mergePeople(remaining).map((item) => [JSON.stringify(item), item]));
  const name = (item) => item.person ?? item.place;
  return [...unique.values()].sort((left, right) => name(left).localeCompare(name(right))
    || JSON.stringify(left).localeCompare(JSON.stringify(right)));
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

const factTexts = (entry) => (Array.isArray(entry.facts) ? entry.facts : [])
  .flatMap((fact) => (fact?.type === 'generic' && typeof fact.content === 'string' ? [fact.content]
    : fact?.type === 'death' && typeof fact.circumstances === 'string' ? [fact.circumstances] : []));


// People already stated by a fact (or its nested facts), with their title sets.
function statedPeople(value, found = new Map()) {
  const add = (person, titles) => {
    const key = registry.get(person) ?? person;
    found.set(key, [...(found.get(key) || []), titles || []]);
  };
  if (Array.isArray(value)) value.forEach((item) => statedPeople(item, found));
  else if (value && typeof value === 'object') {
    if (typeof value.person === 'string') add(value.person, value.personTitle);
    if (typeof value.of === 'string') add(value.of, value.ofTitle);
    Object.entries(value).forEach(([key, child]) => { if (key !== 'mention') statedPeople(child, found); });
  }
  return found;
}

// A mention is stated when a fact names the same person with compatible titles covering its own.
function isStated(item, stated) {
  return (stated.get(item.person) || []).some((titles) => titleForms.covers(titles, item.personTitle || []));
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
    const stated = statedPeople(value.facts ?? (value.type ? value : null));
    const items = [...texts.flatMap((text) => recognizeMentions(text, { stated })), ...issuance];
    const unique = new Map(mergePeople(items).map((item) => [JSON.stringify(item), item]));
    const name = (item) => item.person ?? item.place;
    const mention = [...unique.values()]
      .filter((item) => item.person === undefined || !isStated(item, stated))
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

if (!isMainThread && workerData?.mentionFiles) {
  parentPort.postMessage(await processFiles(workerData.mentionFiles));
} else if (isMainThread && process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}

async function main() {
const files = (await jsonFiles(resolve(root, 'data')))
  .filter((path) => !/\/(tree|people|places|matching)\.json$/.test(path)).sort();
const count = Math.min(4, availableParallelism(), files.length);
const batches = Array.from({ length: count }, () => []);
files.forEach((file, index) => batches[index % count].push(file));
const results = await Promise.all(batches.map((mentionFiles) => new Promise((resolve, reject) => {
  const worker = new Worker(new URL(import.meta.url), { workerData: { mentionFiles } });
  worker.once('message', resolve);
  worker.once('error', reject);
  worker.once('exit', (code) => { if (code !== 0) reject(new Error(`Mention worker exited with code ${code}`)); });
})));
const counter = results.reduce((total, result) => ({
  files: total.files + result.files, mentions: total.mentions + result.mentions,
  stale: total.stale + result.stale,
}), { files: 0, mentions: 0, stale: 0 });
for (const file of results.flatMap((result) => result.changed).sort()) {
  console.log(`${check ? 'Stale mentions' : 'Updated mentions'}: ${relative(root, file)}`);
}
if (counter.stale > 0) {
  console.log(`Checked mentions: ${counter.files} files, ${counter.mentions} mentions, ${counter.stale} ${check ? 'stale' : 'updated'}.`);
}
process.exitCode = check && counter.stale ? 1 : 0;
}

async function processFiles(files) {
const counter = { mentions: 0, files: 0, stale: 0, changed: [] };
for (const file of files) {
  const original = await readFile(file, 'utf8');
  let data;
  try { data = JSON.parse(original); } catch { continue; }
  regenerate(data, file, counter);
  const updated = JSON.stringify(data, null, 2) + (original.endsWith('\n') ? '\n' : '');
  counter.files += 1;
  if (updated === original) continue;
  counter.stale += 1;
  counter.changed.push(file);
  if (!check) await writeFile(file, updated, 'utf8');
}
return counter;
}
