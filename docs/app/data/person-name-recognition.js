function escapePattern(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
}

function alternatives(values) {
  return [...new Set(values.filter(Boolean))]
    .sort((left, right) => right.length - left.length)
    .map(escapePattern)
    .join('|');
}

export function personMentionClass(name) {
  return /\b(?:Rosenberg|Uissigheim)\b/iu.test(name)
    ? 'person-mention-blue'
    : 'person-mention';
}

export function parsePersonNameTitles(markdown = '') {
  return String(markdown).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim()))
    .filter(Boolean);
}

export function buildSourcePersonPattern(namesText, particlesText, places, titleText = '', connectorText = '') {
  const nameForms = String(namesText || '').split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((name) => name.trim()).filter(Boolean));
  const names = [...new Set([
    ...nameForms.map(escapePattern),
    ...nameForms.filter((name) => /^\p{L}+$/u.test(name)).flatMap((name) =>
      Array.from({ length: name.length - 1 }, (_, index) => `${escapePattern(name.slice(0, index + 1))}\\(${escapePattern(name.slice(index + 1))}\\)`))
  ])].sort((left, right) => right.length - left.length).join('|');
  const particles = alternatives(String(particlesText || '').split(/\r?\n/).map((line) => line.split('//')[0].trim()));
  const placeNames = alternatives(places.flatMap((place) => place.variations || [place.name]));
  const titles = alternatives(parsePersonNameTitles(titleText));
  const connectors = alternatives(String(connectorText).split(/\r?\n/)
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
  if (!names || !particles || !placeNames) return null;
  const romanOrdinal = '(?:\\s+(?:\\(\\s*[IVXLCDM]+\\s*\\)|\\[\\s*[IVXLCDM]+\\s*\\]|[IVXLCDM]+\\.?))?';
  const titlePlace = `(?:${placeNames}|[\\p{L}][\\p{L}'’.-]*)`;
  const titleMatch = titles ? `(?:${titles})(?:\\s+(?:zu|an|of)\\s+${titlePlace})?` : '(?!)';
  const titleSequence = titles ? `(?:[\\s,;]+${titleMatch})*` : '';
  const leadingTitles = titles ? `(?:${titleMatch}\\s+)*` : '';
  const particle = `(?:${particles}|of)`;
  const placeClause = `(?:${placeNames})(?:\\s+(?:zu|an)\\s+(?:${placeNames}))?`;
  const suffixTitles = `(?:[\\s,;]+${titleMatch})*`;
  const placeNote = '(?:\\s*\\(-?[\\p{L}\\p{N}]+-?\\))?';
  const nameNote = '(?:\\s*\\(\\s*or\\s+[^)]*\\))?';
  const leadingConnector = connectors ? `(?:(?:${connectors})\\s+)?` : '';
  const namingConnector = connectors ? `(?:\\s+(?:${connectors}))?` : '';
  return new RegExp(`(?<![\\p{L}\\p{N}])${leadingTitles}${leadingConnector}(?:${names})(?:\\s+(?:${names}))*${nameNote}${romanOrdinal}${titleSequence}${namingConnector}[\\s,]+${particle}\\s+${placeClause}${placeNote}${suffixTitles}(?![\\p{L}\\p{N}])`, 'giu');
}

export function personRouteName(name, titleText = '', connectorText = '') {
  const titles = alternatives(parsePersonNameTitles(titleText));
  const connectors = alternatives(String(connectorText).split(/\r?\n/)
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
  const ordinal = '(?:\\s+(?:\\(\\s*[IVXLCDM]+\\s*\\)|\\[\\s*[IVXLCDM]+\\s*\\]|[IVXLCDM]+\\.?))?';
  const titleSequence = titles ? `(?:[\\s,]+(?:${titles}))*` : '';
  return String(name)
    .replace(new RegExp(`^(?:${titles})[\\s,;]+(?:${connectors})[\\s,;]+`, 'iu'), '')
    .replace(new RegExp(`^(?:${titles}(?:\\s+(?:zu|an|of)\\s+[^,]+)?[\\s,;]+)+`, 'iu'), '')
    .replace(new RegExp(`^(?:${connectors})\\s+`, 'iu'), '')
    .replace(/\s*\(\s*or\s+[^)]*\)/iu, '')
    .replace(new RegExp(`${ordinal}${titleSequence}[\\s,;]+(?=(?:von|v\\.?|van|de|in|der|die|das|des|of)\\b)`, 'iu'), ' ')
    .replace(new RegExp(`[\\s,;]+(?:${titles})(?:\\s+(?:zu|an|of)\\s+[^,;]+)?(?:[\\s,;]+(?:${titles})(?:\\s+(?:zu|an|of)\\s+[^,;]+)?)*$`, 'iu'), '')
    .replace(/\s*\([^)]*\)$/u, '')
    .trim();
}
