const GENERIC_BUILDING_NAMES = new Set(['abbey', 'monastery', 'burg', 'old burg', 'schloss', 'wasserschloss', 'kirche', 'evangelische kirche', 'johanniskirche', 'friedhofskapelle']);

export function parsePlaces(json) {
  const places = JSON.parse(json);
  if (!Array.isArray(places)) throw new Error('data/places.json must contain an array');
  const byId = new Map(places.filter((place) => place.id).map((place) => [place.id, place]));
  return places.map((place) => {
    const names = Array.isArray(place.variations) ? place.variations.filter((name) => typeof name === 'string' && name.trim()) : [];
    let variations = names;
    if (place.parent) {
      const parent = byId.get(place.parent);
      if (!parent || !['city', 'village'].includes(parent.category) || parent.parent) {
        throw new Error(`Invalid settlement parent for place ${place.id}: ${place.parent}`);
      }
      const parentNames = [...parent.variations].sort((left, right) => right.length - left.length);
      const parentPattern = new RegExp(`(?<![\\p{L}\\p{N}])(?:${parentNames.map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})(?![\\p{L}\\p{N}])`, 'iu');
      variations = names.flatMap((name) => {
        const match = parentPattern.exec(name);
        const localName = match
          ? `${name.slice(0, match.index)} ${name.slice(match.index + match[0].length)}`
            .replace(/^[\s,]+|[\s,]+$/g, '').replace(/\s+/g, ' ')
          : name;
        if (!localName) return [name];
        const settlement = parent.variations[0];
        const combined = [`${localName} ${settlement}`, `${settlement} ${localName}`,
          `${localName}, ${settlement}`, `${settlement}, ${localName}`];
        return match ? [name, ...combined]
          : GENERIC_BUILDING_NAMES.has(name.toLocaleLowerCase()) ? combined : [...combined, name];
      });
    }
    variations = [...new Set(variations)];
    return { ...place, name: variations[0], variations };
  });
}

export function findPlaceByName(places, query) {
  const normalizeName = (value) => String(value || '').trim().replace(/\s*,\s*/g, ', ').replace(/\s+/g, ' ').toLocaleLowerCase();
  const normalized = normalizeName(query);
  const matches = places.filter((place) => [place.name, ...(place.variations || [])]
    .some((name) => normalizeName(name) === normalized));
  if (matches.length === 1) return matches[0];
  const settlements = matches.filter((place) => ['city', 'village'].includes(place.category) && !place.parent);
  if (settlements.length === 1) return settlements[0];
  const classified = matches.filter((place) => ['city', 'village', 'castle', 'church'].includes(place.category));
  return classified.length === 1 ? classified[0] : undefined;
}

export function buildPlacePattern(places) {
  const names = [...new Set(places.flatMap((place) => Array.isArray(place.variations) ? place.variations : [place.name]).filter((name) => typeof name === 'string' && name.trim()))]
    .sort((left, right) => right.length - left.length)
    .map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s*,\s*/g, '\\s*,\\s*').replace(/ /g, '\\s+'));
  return names.length ? new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.join('|')})(?![\\p{L}\\p{N}])`, 'giu') : null;
}

export function parsePeople(json) {
  const people = JSON.parse(json);
  if (!Array.isArray(people)) throw new Error('data/people.json must contain an array');
  if (people.some((person) => !person || typeof person.name !== 'string' || !person.name.trim())) throw new Error('Invalid person record');
  const ids = people.filter((person) => person.id).map((person) => person.id);
  if (new Set(ids).size !== ids.length || people.some((person) => ids.includes(person.name))) throw new Error('Duplicate person IDs or ID/name collision');
  if (people.some((person) => person.familyGraph || Object.hasOwn(person, 'relationships'))
    && people.some((person, index) => !Array.isArray(person.relationships) || Object.hasOwn(person, 'wife') || Object.hasOwn(person, 'children') || index > 0 && person.familyGraph)) throw new Error('Incomplete generated registry');
  return people;
}

export function buildPersonPattern(people) {
  const names = people.map((person) => person.name)
    .sort((left, right) => right.length - left.length)
    .map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return names.length
    ? [{ pattern: new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.join('|')})(?![\\p{L}\\p{N}])`, 'giu'), people }]
    : [];
}
