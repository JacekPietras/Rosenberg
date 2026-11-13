function escapePattern(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
}

function alternatives(values) {
  return [...new Set(values.filter(Boolean))]
    .sort((left, right) => right.length - left.length)
    .map(escapePattern)
    .join('|');
}

export function buildSourcePersonPattern(namesText, particlesText, places) {
  const names = alternatives(String(namesText || '').split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((name) => name.trim())));
  const particles = alternatives(String(particlesText || '').split(/\r?\n/).map((line) => line.split('//')[0].trim()));
  const placeNames = alternatives(places.flatMap((place) => place.variations || [place.name]));
  if (!names || !particles || !placeNames) return null;
  const romanOrdinal = '(?:\\s+(?:\\(\\s*[IVXLCDM]+\\s*\\)|\\[\\s*[IVXLCDM]+\\s*\\]|[IVXLCDM]+\\.?))?';
  return new RegExp(`(?<![\\p{L}\\p{N}])(?:${names})(?:\\s+(?:${names}))*${romanOrdinal}\\s+(?:${particles})\\s+(?:${placeNames})(?![\\p{L}\\p{N}])`, 'giu');
}

export function personRouteName(name) {
  return String(name).replace(/\s+[([]?\s*[IVXLCDM]+\.?\s*[)\]]?(?=\s+von\b)/giu, '');
}
