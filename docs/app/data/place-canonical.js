import { GENERIC_BUILDING_NAMES, parsePlaces } from './entities.js';

const squash = (value) => String(value).trim().replace(/\s+/g, ' ');

// Canonical place form = the record's raw first variation in data/places.json
// (not parsePlaces' name, which prepends settlement combinations). A generic
// building name ("Schloss") keeps its settlement-qualified form. A form shared
// by several records is ambiguous and stays as written.
// `rawPlaces` is the parsed places.json array.
export function createPlaceCanonicalizer(rawPlaces) {
  const parsed = parsePlaces(JSON.stringify(rawPlaces));
  const records = new Map();
  parsed.forEach((place, index) => {
    const key = place.id || place.name || `@place/${index}`;
    const raw = rawPlaces[index]?.variations?.find((name) => typeof name === 'string' && name.trim());
    const canonical = raw && !GENERIC_BUILDING_NAMES.has(raw.toLocaleLowerCase()) ? squash(raw) : place.name;
    for (const form of place.variations || []) {
      const slot = records.get(squash(form).toLocaleLowerCase()) ?? new Map();
      slot.set(key, canonical);
      records.set(squash(form).toLocaleLowerCase(), slot);
    }
  });
  const lookup = (text) => {
    const slot = records.get(squash(text).toLocaleLowerCase());
    return slot?.size === 1 ? [...slot][0] : null;
  };
  return {
    canonicalPlace: (text) => lookup(text)?.[1] ?? squash(text),
    placeKey: (text) => lookup(text)?.[0] ?? squash(text).toLocaleLowerCase(),
  };
}
