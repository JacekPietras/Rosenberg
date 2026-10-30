import { escapeHtml } from './html.js';

const RELATIONS = { parent: 'is parent of', sibling: 'is sibling of', spouse: 'is spouse of' };
const hasDate = (value) => value && typeof value === 'object' && Object.hasOwn(value, 'date');
const escapePattern = (value) => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function isTypedFact(fact) {
  return !!fact && typeof fact === 'object' && Object.hasOwn(fact, 'type');
}

export function factDate(fact, defaultDate = '') {
  return (hasDate(fact) ? fact.date : defaultDate) ?? '';
}

export function sourceFactDate(fact, doc, entry, path = '') {
  const isBookOrNote = /^data\/(?:books|notes)\//.test(path) || !!doc?.book;
  return factDate(fact, isBookOrNote ? '' : hasDate(entry) ? entry.date : doc?.date);
}

function personName(value, people) {
  return people.find((person) => person.id && person.id === value)?.name || String(value || '');
}

function titles(value) {
  return Array.isArray(value) ? value.filter((title) => typeof title === 'string' && title.trim()).join(', ') : '';
}

function typedText(fact, participant, literal) {
  if (fact.type === 'title') return `${participant(fact.person)} is designated ${literal(titles(fact.personTitle))}.`;
  if (fact.type === 'death') {
    const when = fact.diedOn ? `died on ${literal(fact.diedOn)}` : `died before ${literal(fact.diedBefore || '')}`;
    const circumstances = typeof fact.circumstances === 'string' && fact.circumstances.trim()
      ? ` (${literal(fact.circumstances)})` : '';
    return `${participant(fact.person, fact.personTitle)} ${when}${circumstances}.`;
  }
  const person = participant(fact.person, fact.personTitle);
  const other = participant(fact.of, fact.ofTitle);
  if (fact.type === 'kin') return `${person} is kin of ${other} (${literal(fact.term || '')}).`;
  return RELATIONS[fact.type] ? `${person} ${RELATIONS[fact.type]} ${other}.` : '';
}

export function factText(fact, people = []) {
  if (!isTypedFact(fact)) return fact && typeof fact === 'object' ? String(fact.text || '') : String(fact || '');
  return typedText(fact, (value, designations) => {
    const title = titles(designations);
    return `${personName(value, people)}${title ? `, ${title}` : ''}`;
  }, String);
}

// Returns an exact ID match, a name-only discovery match, or no match.
export function factPersonMatch(fact, query, people = []) {
  const selected = people.find((person) => person.id && person.id === query);
  const name = selected?.name || String(query || '');
  if (!name) return '';
  const sameName = (value) => String(value).toLocaleLowerCase() === name.toLocaleLowerCase();
  if (isTypedFact(fact)) {
    let nameMatch = false;
    for (const value of [fact.person, fact.of]) {
      if (typeof value !== 'string') continue;
      const identified = people.find((person) => person.id && person.id === value);
      if (selected) {
        if (identified?.id === selected.id) return 'direct';
        if (!identified && sameName(value)) nameMatch = true;
      } else if (sameName(identified?.name || value)) return 'direct';
    }
    return nameMatch ? 'ambiguous' : '';
  }
  const text = factText(fact);
  if (selected && text.includes(`[${selected.id}]`)) return 'direct';
  if (new RegExp(`(?<![\\p{L}\\p{N}])${escapePattern(name)}(?![\\p{L}\\p{N}])`, 'iu').test(text)) return selected ? 'ambiguous' : 'direct';
  if (!selected && people.some((person) => person.id && sameName(person.name) && text.includes(`[${person.id}]`))) return 'direct';
  return '';
}

// Explicit IDs stay specific; plain names use the generic name route.
export function renderFactText(fact, { people = [], personNames = [], inlineMarkup }) {
  const peopleById = new Map(people.filter((person) => person.id).map((person) => [person.id, person]));
  if (isTypedFact(fact)) {
    return typedText(fact, (value, designations) => {
      const person = peopleById.get(value);
      const name = person?.name || String(value || '');
      const title = titles(designations);
      return `<a class="person-link" href="?person=${encodeURIComponent(person?.id || name)}">${escapeHtml(name)}</a>${title ? `, ${escapeHtml(title)}` : ''}`;
    }, escapeHtml);
  }
  const links = [];
  let text = factText(fact).replace(/\[([^\]]+)\]/g, (match, id) => {
    const person = peopleById.get(id);
    if (!person) return match;
    const marker = `\u0001FACTPERSON${links.length}\u0002`;
    links.push(`<a class="person-link" href="?person=${encodeURIComponent(person.id)}">${inlineMarkup(person.name, false)}</a>`);
    return marker;
  });
  const names = [...new Set([...people.map((person) => person.name), ...personNames].filter(Boolean))]
    .sort((left, right) => right.length - left.length)
    .map(escapePattern);
  if (names.length) {
    const pattern = new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.join('|')})(?![\\p{L}\\p{N}])`, 'giu');
    text = text.replace(pattern, (match) => {
      const name = [...people.map((person) => person.name), ...personNames]
        .find((name) => name.toLocaleLowerCase() === match.toLocaleLowerCase());
      const marker = `\u0001FACTPERSON${links.length}\u0002`;
      links.push(`<a class="person-link" href="?person=${encodeURIComponent(name)}">${inlineMarkup(match, false)}</a>`);
      return marker;
    });
  }
  const rendered = inlineMarkup(text, false);
  return rendered.replace(/\u0001FACTPERSON(\d+)\u0002/g, (match, index) => links[Number(index)] ?? match);
}
