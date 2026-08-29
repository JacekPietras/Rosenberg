export function parsePlaces(json) {
  const places = JSON.parse(json);
  if (!Array.isArray(places)) throw new Error('data/places.json must contain an array');
  return places.map((place) => {
    const variations = Array.isArray(place.variations) ? place.variations.filter((name) => typeof name === 'string' && name.trim()) : [];
    return { ...place, name: variations[0] };
  });
}

export function buildPlacePattern(places) {
  const names = [...new Set(places.map((place) => place.name).filter(Boolean))]
    .sort((left, right) => right.length - left.length)
    .map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return names.length ? new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.join('|')})(?![\\p{L}\\p{N}])`, 'giu') : null;
}

export function parsePeople(json) {
  const people = JSON.parse(json);
  if (!Array.isArray(people)) throw new Error('data/people.json must contain an array');
  return people.filter((person) => person && typeof person.name === 'string' && person.name.trim());
}

export function buildPersonPattern(people) {
  const names = people.map((person) => person.name)
    .sort((left, right) => right.length - left.length)
    .map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return names.length
    ? [{ pattern: new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.join('|')})(?![\\p{L}\\p{N}])`, 'giu'), people }]
    : [];
}
