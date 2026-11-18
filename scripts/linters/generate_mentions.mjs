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

const root = resolve(import.meta.dirname, '../..');
const check = process.argv.includes('--check');
const read = (path) => readFile(resolve(root, path), 'utf8').catch(() => '');
const titleText = [await read('data/titles-age.md'), await read('data/titles-office.md')].filter(Boolean).join('\n');
const args = [titleText, await read('data/name-connectors.md'), await read('data/nobiliary_particles.md'),
  await read('data/names.md'), await read('data/by-names.md'), JSON.parse(await read('data/places.json'))];
const pattern = buildSourcePersonPattern(args[3], args[2], args[5], args[0], args[1], args[4]);
const knownTitles = parsePersonNameTitles(titleText).sort((left, right) => right.length - left.length);
const escape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
const leadingTitle = knownTitles.length
  ? new RegExp(`^(${knownTitles.map(escape).join('|')})(?:\\s+(?:zu|zum|an|of)\\s+[\\p{L}][\\p{L}'’.-]*)?[\\s,;]+`, 'iu') : null;

function surfaceTitles(text) {
  const titles = [];
  let rest = text;
  for (let match = leadingTitle?.exec(rest); match; match = leadingTitle.exec(rest)) {
    titles.push(match[1]);
    rest = rest.slice(match[0].length);
  }
  return [...titles, ...splitPersonNameTitles(rest, titleText).titles];
}

export function recognizeMentions(text) {
  if (!pattern || typeof text !== 'string' || !text.trim()) return [];
  const { coordinated, singles } = findPersonNameMentions(text, ...args, pattern);
  const found = [
    ...singles.map((item) => ({ start: item.start, people: [{ person: item.route, titles: surfaceTitles(item.text) }] })),
    ...coordinated.map((group) => ({ start: group.start, people: group.routes.map((person) => ({ person, titles: group.titles })) })),
  ].sort((left, right) => left.start - right.start);
  return found.flatMap((item) => item.people.map(({ person, titles }) => (
    titles.length ? { person, personTitle: titles } : { person })));
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

function regenerate(value, file, counter) {
  if (Array.isArray(value)) {
    value.forEach((item) => regenerate(item, file, counter));
    return;
  }
  if (!value || typeof value !== 'object') return;
  delete value.mention;
  const anchor = typeof value.english === 'string' && file.includes('/data/documents/') ? 'english'
    : value.type === 'generic' && typeof value.content === 'string' ? 'content' : null;
  if (anchor) {
    const mention = recognizeMentions(value[anchor]);
    if (mention.length) {
      const entries = Object.entries(value);
      for (const key of Object.keys(value)) delete value[key];
      for (const [key, child] of entries) {
        value[key] = child;
        if (key === anchor) value.mention = mention;
      }
      counter.mentions += mention.length;
    }
  }
  Object.values(value).forEach((child) => regenerate(child, file, counter));
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
