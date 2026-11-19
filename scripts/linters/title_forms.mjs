// Canonical forms of person titles from data/titles-*.md; place names are kept as written.
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parsePersonNameTitles } from '../../docs/app/data/person-name-recognition.js';

const root = resolve(import.meta.dirname, '../..');
const read = (file) => readFile(resolve(root, 'data', file), 'utf8');
const lower = (value) => value.toLocaleLowerCase();
const escape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');

const text = `${await read('titles-age.md')}\n${await read('titles-office.md')}`;
const groupOf = new Map();
for (const line of text.split(/\r?\n/)) {
  if (!line.trim() || /^\s*(#|\/\/)/u.test(line)) continue;
  const group = parsePersonNameTitles(line);
  for (const form of group) groupOf.set(lower(form), group[0]);
}

const forms = [...groupOf.keys()].sort((left, right) => right.length - left.length).map(escape).join('|');
const wholePattern = new RegExp(`^(${forms})$`, 'iu');

// Whole titles in the vocabulary, optionally followed by `zu <place>`; anything else is kept.
export function canonicalTitle(title) {
  const value = String(title).trim().replace(/\s+/g, ' ');
  const whole = value.match(wholePattern);
  if (whole) return groupOf.get(lower(whole[1]));
  const located = value.match(new RegExp(`^(?:(${forms})\\s+)?(?:zu|zum|ze)\\s+(.+)$`, 'iu'));
  if (!located) return title;
  const place = located[2];
  return located[1] ? `${groupOf.get(lower(located[1]))} zu ${place}` : `zu ${place}`;
}

export function canonicalTitles(titles) {
  return [...new Set(titles.map(canonicalTitle))];
}
