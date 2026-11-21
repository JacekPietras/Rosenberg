// Canonical forms, consolidation, compatibility and merging of person titles.
// `createTitleForms` is pure (takes the dictionaries); the default instance reads data/.
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parsePersonNameTitles } from '../../docs/app/data/person-name-recognition.js';
import { createPlaceCanonicalizer } from '../../docs/app/data/place-canonical.js';

const lower = (value) => value.toLocaleLowerCase();
const escape = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
const squash = (value) => String(value).trim().replace(/\s+/g, ' ');
const LOCATIVE = 'zu|zum|ze|in|at|of';

export function createTitleForms({ ageText = '', officeText = '', places = [] }) {
  const groupOf = new Map();
  const ageClass = new Map();
  const lines = (text) => text.split(/\r?\n/).filter((line) => line.trim() && !/^\s*(#|\/\/)/u.test(line));
  for (const line of lines(`${ageText}\n${officeText}`)) {
    const group = parsePersonNameTitles(line);
    for (const form of group) groupOf.set(lower(form), group[0]);
  }
  const ranks = new Set();
  let section = '';
  for (const line of officeText.split(/\r?\n/)) {
    const header = line.match(/^\s*\/\/\s*(.+?)\s*$/u);
    if (header) section = lower(header[1]);
    else if (section === 'ranks' && line.trim()) ranks.add(lower(parsePersonNameTitles(line)[0]));
  }
  let index = -1;
  for (const line of ageText.split(/\r?\n/)) {
    if (line.trim().startsWith('#')) index += 1;
    else for (const form of parsePersonNameTitles(line)) ageClass.set(lower(groupOf.get(lower(form)) ?? form), index);
  }

  const { canonicalPlace, placeKey } = createPlaceCanonicalizer(places);

  const forms = [...groupOf.keys()].sort((left, right) => right.length - left.length).map(escape).join('|');
  const wholePattern = forms ? new RegExp(`^(${forms})$`, 'iu') : /$^/u;
  const locatedPattern = new RegExp(`^(?:(${forms || '(?!)'})\\s+)?(?:(${LOCATIVE})|(von|an))\\s+(.+)$`, 'iu');

  // Whole titles in the vocabulary, optionally followed by a place. `zu`-like
  // particles become `zu`; `von` and `an` stay. Listed places take their canonical form.
  function canonicalTitle(title) {
    const value = squash(title);
    const whole = value.match(wholePattern);
    if (whole) return groupOf.get(lower(whole[1]));
    const located = value.match(locatedPattern);
    if (!located) return title;
    const [, base, locative, other, place] = located;
    if (!base && other) return title;
    const particle = locative ? 'zu' : lower(other);
    const text = `${particle} ${canonicalPlace(place)}`;
    return base ? `${groupOf.get(lower(base))} ${text}` : text;
  }


  // kind: age | office | located | designation | other
  function parseTitle(title) {
    const value = canonicalTitle(title);
    if (ageClass.has(lower(value))) return { value, kind: 'age', age: ageClass.get(lower(value)) };
    if (groupOf.has(lower(value))) return { value, kind: 'office', base: lower(value) };
    const match = value.match(/^(?:(.+?)\s+)?(zu|von|an)\s+(.+)$/iu);
    if (!match) return { value, kind: 'other' };
    const base = match[1] && groupOf.get(lower(match[1]));
    const place = placeKey(match[3]);
    if (!match[1]) return match[2] === 'zu' ? { value, kind: 'designation', place } : { value, kind: 'other' };
    if (!base) return { value, kind: 'other' };
    // Ages and ranks never take a place: `Ritter zu Boxberg` is `Ritter` + `zu Boxberg`.
    if (ageClass.has(lower(base)) || ranks.has(lower(base))) {
      return { value, kind: 'other', split: [base, `${match[2]} ${match[3]}`] };
    }
    return { value, kind: 'located', base: lower(base), place };
  }

  const canonicalTitles = (titles) => [...new Set(titles.map(canonicalTitle)
    .flatMap((title) => parseTitle(title).split ?? [title]))];

  const keyOf = (item) => (item.kind === 'located' ? `${item.base}|${item.place}`
    : item.kind === 'designation' ? `|${item.place}` : item.kind === 'age' ? `age|${item.age}` : lower(item.value));
  const parseAll = (titles = []) => canonicalTitles(titles).map(parseTitle);
  const ageOf = (titles = []) => new Set(parseAll(titles).filter((title) => title.kind === 'age').map((title) => title.age));

  // A located office supersedes its bare office, and a designation repeating a
  // located place is dropped. Ranks and ages keep their own entry. With `join`, a
  // lone bare office plus a lone designation (`Abt`, `zu Zwettl`) are read as the
  // located office; that is a coverage test only, never written to data.
  function reduceTitles(titles, join = false) {
    let parsed = canonicalTitles(titles).map(parseTitle);
    const designations = () => parsed.filter((item) => item.kind === 'designation');
    const bare = () => parsed.filter((item) => item.kind === 'office' && !ranks.has(item.base) && !ageClass.has(item.base));
    if (join && designations().length === 1 && bare().length === 1) {
      const [designation] = designations();
      const [office] = bare();
      const merged = parseTitle(`${office.value} ${designation.value}`);
      parsed = parsed.flatMap((item) => (item === office ? [merged] : item === designation ? [] : [item]));
    }
    const locatedBases = new Set(parsed.filter((item) => item.kind === 'located').map((item) => item.base));
    const locatedPlaces = new Set(parsed.filter((item) => item.kind === 'located').map((item) => item.place));
    const seen = new Set();
    return parsed.filter((item) => !(item.kind === 'office' && locatedBases.has(item.base))
      && !(item.kind === 'designation' && locatedPlaces.has(item.place))).filter((item) => {
      const key = keyOf(item);
      return seen.has(key) ? false : (seen.add(key), true);
    }).map((item) => item.value);
  }

  const consolidateTitles = (titles) => reduceTitles(titles);

  const subset = (left, right) => [...left].every((item) => right.has(item));
  const related = (left, right) => !left.size || !right.size || subset(left, right) || subset(right, left);

  // Titles of one person never contradict: different age titles, or different
  // designations / located offices, mean different people.
  function compatible(left, right) {
    const a = parseAll(left);
    const b = parseAll(right);
    const pick = (list, kind, key) => new Set(list.filter((item) => item.kind === kind).map(key));
    const ageA = ageOf(left);
    const ageB = ageOf(right);
    if (ageA.size && ageB.size && !(subset(ageA, ageB) && subset(ageB, ageA))) return false;
    return related(pick(a, 'designation', (item) => item.place), pick(b, 'designation', (item) => item.place))
      && related(pick(a, 'located', (item) => `${item.base}|${item.place}`),
        pick(b, 'located', (item) => `${item.base}|${item.place}`));
  }

  // Same-route items are one person when their titles are compatible.
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
      for (const item of list) {
        const titles = item.personTitle || [];
        if (!titles.length) continue;
        const fits = clusters.filter((cluster) => !cluster.closed && compatible(cluster.titles, titles));
        if (fits.length === 1) fits[0].titles.push(...titles);
        else clusters.push({ titles: [...titles], closed: fits.length > 1 });
      }
      if (!clusters.length) merged.push({ person });
      for (const cluster of clusters) {
        merged.push({ person, personTitle: consolidateTitles(cluster.titles).sort() });
      }
    }
    return [...merged, ...others];
  }

  // Whether `have` (a fact person's titles) states a mention with titles `own`:
  // compatible, and adding `own` changes nothing after consolidation.
  function covers(have, own) {
    if (!compatible(have, own)) return false;
    const signature = (titles) => reduceTitles(titles, true).map((title) => keyOf(parseTitle(title))).sort().join('\n');
    const base = signature(have);
    return canonicalTitles(own).every((title) => signature([...have, title]) === base);
  }

  return {
    canonicalTitle, canonicalTitles, canonicalPlace, consolidateTitles, parseTitle, ageOf, compatible, mergePeople, covers,
  };
}

const root = resolve(import.meta.dirname, '../..');
const read = (file) => readFile(resolve(root, 'data', file), 'utf8').catch(() => '');
export const titleForms = createTitleForms({
  ageText: await read('titles-age.md'),
  officeText: await read('titles-office.md'),
  places: JSON.parse((await read('places.json')) || '[]'),
});

export const { canonicalTitle, canonicalTitles } = titleForms;
