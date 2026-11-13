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
  const sections = { 'age titles': [], 'rank titles': [] };
  let section = '';
  for (const line of String(markdown).split(/\r?\n/)) {
    if (line.startsWith('## ')) section = line.slice(3).trim().toLocaleLowerCase();
    else if (sections[section] && line.startsWith('- ')) sections[section].push(line.slice(2).trim());
  }
  return [...sections['age titles'], ...sections['rank titles']];
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
  const titleSequence = titles ? `(?:[\\s,]+(?:${titles}))*` : '';
  return new RegExp(`(?<![\\p{L}\\p{N}])(?:${names})(?:\\s+(?:${names}))*${romanOrdinal}${titleSequence}[\\s,]+(?:${particles})\\s+(?:${placeNames})(?![\\p{L}\\p{N}])`, 'giu');
}

export function personRouteName(name, titleText = '') {
  const titles = alternatives(parsePersonNameTitles(titleText));
  const ordinal = '(?:\\s+(?:\\(\\s*[IVXLCDM]+\\s*\\)|\\[\\s*[IVXLCDM]+\\s*\\]|[IVXLCDM]+\\.?))?';
  const titleSequence = titles ? `(?:[\\s,]+(?:${titles}))*` : '';
  return String(name).replace(new RegExp(`${ordinal}${titleSequence}[\\s,]+(?=von\\b)`, 'iu'), ' ');
}
