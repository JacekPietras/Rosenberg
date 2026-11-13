function escapePattern(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
}

function alternatives(values) {
  return [...new Set(values.filter(Boolean))]
    .sort((left, right) => right.length - left.length)
    .map(escapePattern)
    .join('|');
}

export function parsePersonNameTitles(markdown = '') {
  return String(markdown).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim()))
    .filter(Boolean);
}

export function buildSourcePersonPattern(namesText, particlesText, places, titleText = '') {
  const names = alternatives(String(namesText || '').split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((name) => name.trim())));
  const particles = alternatives(String(particlesText || '').split(/\r?\n/).map((line) => line.split('//')[0].trim()));
  const placeNames = alternatives(places.flatMap((place) => place.variations || [place.name]));
  const titles = alternatives(parsePersonNameTitles(titleText));
  if (!names || !particles || !placeNames) return null;
  const romanOrdinal = '(?:\\s+(?:\\(\\s*[IVXLCDM]+\\s*\\)|\\[\\s*[IVXLCDM]+\\s*\\]|[IVXLCDM]+\\.?))?';
  const titleMatch = titles ? `(?:${titles})(?:\\s+(?:zu|an|of)\\s+(?:${placeNames}))?` : '(?!)';
  const titleSequence = titles ? `(?:[\\s,;]+${titleMatch})*` : '';
  const leadingTitles = titles ? `(?:${titleMatch}[\\s,;]+)*` : '';
  const particle = `(?:${particles}|of)`;
  const placeClause = `(?:${placeNames})(?:\\s+(?:zu|an)\\s+(?:${placeNames}))?`;
  const suffixTitles = `(?:[\\s,;]+${titleMatch})*`;
  const nameNote = '(?:\\s*\\(\\s*or\\s+[^)]*\\))?';
  return new RegExp(`(?<![\\p{L}\\p{N}])${leadingTitles}(?:${names})(?:\\s+(?:${names}))*${nameNote}${romanOrdinal}${titleSequence}[\\s,]+${particle}\\s+${placeClause}${suffixTitles}(?![\\p{L}\\p{N}])`, 'giu');
}

export function personRouteName(name, titleText = '') {
  const titles = alternatives(parsePersonNameTitles(titleText));
  const ordinal = '(?:\\s+(?:\\(\\s*[IVXLCDM]+\\s*\\)|\\[\\s*[IVXLCDM]+\\s*\\]|[IVXLCDM]+\\.?))?';
  const titleSequence = titles ? `(?:[\\s,]+(?:${titles}))*` : '';
  return String(name)
    .replace(new RegExp(`^(?:${titles}(?:\\s+(?:zu|an|of)\\s+[^,]+)?[\\s,;]+)+`, 'iu'), '')
    .replace(/\s*\(\s*or\s+[^)]*\)/iu, '')
    .replace(new RegExp(`${ordinal}${titleSequence}[\\s,;]+(?=(?:von|v\\.?|van|de|in|der|die|das|des|of)\\b)`, 'iu'), ' ')
    .replace(new RegExp(`[\\s,;]+(?:${titles})(?:\\s+(?:zu|an|of)\\s+[^,;]+)?(?:[\\s,;]+(?:${titles})(?:\\s+(?:zu|an|of)\\s+[^,;]+)?)*$`, 'iu'), '')
    .trim();
}
