function escapePattern(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
}

function alternatives(values) {
  return [...new Set(values.filter(Boolean))]
    .sort((left, right) => right.length - left.length)
    .map(escapePattern)
    .join('|');
}

export function personMentionClass(name, connectorText = '', particleText = '') {
  const connectors = alternatives(String(connectorText).split(/\r?\n/)
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
  const particles = alternatives(String(particleText).split(/\r?\n/).map((line) => line.split('//')[0].trim()));
  const personName = connectors && particles
    ? String(name).replace(new RegExp(`[\\s,;]+(?:${connectors})[\\s,;]+(?:${particles})\\s+[^,;]+$`, 'iu'), '')
    : String(name);
  return /\b(?:Rosenberg|Uissigheim)\b/iu.test(personName)
    ? 'person-mention-blue'
    : 'person-mention';
}

export function parsePersonNameTitles(markdown = '') {
  return String(markdown).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim()))
    .filter(Boolean);
}

function parsePersonNameRouteTitles(markdown = '') {
  let inRouteTitles = false;
  const routeTitles = new Set();
  for (const line of String(markdown).split(/\r?\n/)) {
    const header = line.trim().match(/^\/\/\s*(.*?)\s*$/u);
    if (header) {
      inRouteTitles = header[1].toLocaleLowerCase() === 'route titles';
    } else if (inRouteTitles) {
      for (const form of line.split('//')[0].split(',').map((value) => value.trim()).filter(Boolean)) {
        routeTitles.add(form.toLocaleLowerCase());
      }
    }
  }
  return routeTitles;
}

export function coordinatedByNameMatches(text, titleText = '', connectorText = '', particleText = '', namesText = '', byNamesText = '', places = []) {
  const titles = alternatives(parsePersonNameTitles(titleText));
  const names = alternatives(String(namesText).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
  const byNames = alternatives(String(byNamesText).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
  const particles = alternatives(String(particleText).split(/\r?\n/).map((line) => line.split('//')[0].trim()));
  const placeNames = alternatives(places.flatMap((place) => place.variations || [place.name]));
  if (!names || !byNames || !placeNames) return [];
  const byNameVariants = new Map(String(byNamesText).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .map((line) => line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean))
    .filter((forms) => forms.length)
    .flatMap(([canonical, ...forms]) => [canonical, ...forms].map((form) => [form.toLocaleLowerCase(), canonical])));
  const givenName = `(?:${names})`;
  const givenItem = `${givenName}(?:\\s+${givenName})*`;
  const surname = `(?<byName>${byNames})(?:\\s+(?<byNameParticle>${particles})\\s+(?<byNamePlace>${placeNames}))?|(?<particle>${particles})\\s+(?<place>${placeNames})`;
  const sharedTitle = titles ? `(?:[,\\s]+(?<sharedTitle>${titles}))?` : '';
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}])(?<givenList>${givenItem}(?:\\s*,\\s*${givenItem})*(?:\\s*,?\\s+(?:and|und)\\s+${givenItem}))(?:,?\\s+brothers)?\\s+(?<surname>${surname})${sharedTitle}(?![\\p{L}\\p{N}])`, 'giu');
  const contextPattern = new RegExp(`(?<byName>${byNames})\\s+(?<particle>${particles})\\s+(?<place>${placeNames})`, 'giu');
  const matches = [];
  for (const match of String(text).matchAll(pattern)) {
    if (titles && new RegExp(`(?:${titles})[\\s,;]+$`, 'iu').test(String(text).slice(0, match.index))) continue;
    let surnameText = match.groups.surname;
    if (match.groups.byName && !match.groups.byNameParticle) {
      const before = String(text).slice(0, match.index);
      const prior = [...before.matchAll(contextPattern)].at(-1);
      if (prior && byNameVariants.get(prior.groups.byName.toLocaleLowerCase())
          === byNameVariants.get(match.groups.byName.toLocaleLowerCase())) {
        surnameText += ` ${prior.groups.particle} ${prior.groups.place}`;
      }
    }
    matches.push({
      text: match[0],
      start: match.index,
      end: match.index + match[0].length,
      givenList: match.groups.givenList,
      givenListEnd: match.index + match[0].indexOf(match.groups.givenList) + match.groups.givenList.length,
      brothersAfterList: /\bbrothers\b/iu.test(match[0].slice(match[0].indexOf(match.groups.givenList) + match.groups.givenList.length)),
      givenNames: match.groups.givenList.split(/\s*,\s*(?:(?:and|und)\s+)?|\s+(?:and|und)\s+/iu).map((givenName) => givenName.trim()),
      surnameText,
      surnameSurface: match.groups.surname,
      titles: match.groups.sharedTitle ? [match.groups.sharedTitle] : [],
      routes: match.groups.givenList.split(/\s*,\s*(?:(?:and|und)\s+)?|\s+(?:and|und)\s+/iu).map((givenName) => givenName.trim()).map((givenName) =>
        personRouteName(`${givenName} ${surnameText}`.trim(),
          titleText, connectorText, particleText, namesText, byNamesText, places)),
    });
  }
  return matches;
}

export function findPersonNameMentions(text, titleText = '', connectorText = '', particleText = '', namesText = '', byNamesText = '', places = [], sourcePattern = null, personPatterns = []) {
  const value = String(text);
  const coordinated = coordinatedByNameMatches(value, titleText, connectorText,
    particleText, namesText, byNamesText, places);
  const singles = [];
  const explicitIds = [...value.matchAll(/\[[^\]]+\]/gu)].map((match) => [match.index, match.index + match[0].length]);
  const patterns = [
    ...(sourcePattern ? [{ kind: 'source', pattern: sourcePattern }] : []),
    ...(personPatterns || []).map(({ pattern, people }) => ({ kind: 'registry', pattern, people })),
  ];
  for (const candidate of patterns) {
    const { pattern } = candidate;
    const lastIndex = typeof pattern.lastIndex === 'number' ? pattern.lastIndex : undefined;
    if (lastIndex !== undefined) pattern.lastIndex = 0;
    for (const match of value.matchAll(pattern)) {
      const start = match.index;
      const end = start + match[0].length;
      if (coordinated.some((group) => group.start < end && start < group.end)) continue;
      if (explicitIds.some(([idStart, idEnd]) => idStart < end && start < idEnd)) continue;
      if (singles.some((item) => item.start === start && item.end === end
          || item.start <= start && end <= item.end)) continue;
      const route = personRouteName(match[0], titleText, connectorText,
        particleText, namesText, byNamesText, places);
      singles.push({ kind: candidate.kind, text: match[0], start, end, route, people: candidate.people });
    }
    if (lastIndex !== undefined) pattern.lastIndex = lastIndex;
  }
  return { coordinated, singles };
}

export function coordinatedByNameRouteNames(...args) {
  return coordinatedByNameMatches(...args).flatMap((match) => match.routes);
}

export function buildSourcePersonPattern(namesText, particlesText, places, titleText = '', connectorText = '', byNamesText = '') {
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
  const routeTitles = alternatives([...parsePersonNameRouteTitles(titleText)]);
  const connectors = alternatives(String(connectorText).split(/\r?\n/)
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
  const byNames = alternatives(String(byNamesText).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
  if (!names || !particles || !placeNames) return null;
  const romanOrdinal = '(?:\\s+(?:\\(\\s*[IVXLCDM]+\\s*\\)|\\[\\s*[IVXLCDM]+\\s*\\]|[IVXLCDM]+\\.?))?';
  const titlePlace = `(?:${placeNames}|[\\p{L}][\\p{L}'’.-]*)`;
  const titleMatch = titles ? `(?:${titles})(?:\\s+(?:zu|zum|an|of)\\s+${titlePlace})?` : '(?!)';
  const titleSuffixMatch = titles ? `(?:${titleMatch})(?!\\s+(?:${names})\\b)` : '(?!)';
  const titleSequence = titles ? `(?:[\\s,;]+${titleSuffixMatch})*` : '';
  const leadingTitles = titles ? `(?:${titleMatch}\\s+)*` : '';
  const particle = `(?:${particles}|of)`;
  const placeClause = `(?:${placeNames})(?:\\s+(?:zu|zum|an)\\s+(?:${placeNames}))?`;
  const suffixTitles = `(?:[\\s,;]+${titleSuffixMatch})*`;
  const placeNote = '(?:\\s*\\(-?[\\p{L}\\p{N}]+-?\\))?';
  const nameNote = '(?:\\s*\\(\\s*or\\s+[^)]*\\))?';
  const leadingConnector = connectors ? `(?:(?:${connectors})\\s+)?` : '';
  const namingConnector = connectors ? `(?:\\s+(?:${connectors}))?` : '';
  const alternateDesignation = connectors ? `(?:[\\s,;]+(?:${connectors})[\\s,;]+${particle}\\s+${placeClause})?` : '';
  const birthSurname = `[\\s,;]+\\(?\\s*(?:née|nee)[\\s,;]+(?:(?:${names}|${byNames})\\s+)?(?:von|v\\.?|van|de|in|der|die|das|des|of|zu)\\s+(?:${placeNames})\\s*\\)?`;
  const byNameSurname = byNames ? `[\\s,]+(?:${byNames})(?:\\s+(?:${particle})\\s+(?:${placeNames}))?(?:\\s+(?:zu|zum)\\s+${titlePlace})?${placeNote}${suffixTitles}` : '(?!)';
  const surname = `(?:${byNameSurname}|[\\s,]+${particle}\\s+${placeClause}${placeNote}${suffixTitles}${alternateDesignation}(?:${birthSurname})?|${birthSurname}|[\\s,]+(?:${placeNames})${birthSurname}|[\\s,]+(?:${placeNames}))`;
  const titledGivenName = routeTitles ? `(?:${routeTitles})\\s+(?:${names})(?![\\p{L}\\p{N}])` : '(?!)';
  return new RegExp(`(?<![\\p{L}\\p{N}])(?:${leadingTitles}${leadingConnector}(?:${names})(?:\\s+(?:${names}))*${nameNote}${romanOrdinal}${titleSequence}${namingConnector}${surname}(?![\\p{L}\\p{N}])|${titledGivenName})`, 'giu');
}

export function personRouteName(name, titleText = '', connectorText = '', particleText = '', namesText = '', byNamesText = '', places = []) {
  const titles = alternatives(parsePersonNameTitles(titleText));
  const connectors = alternatives(String(connectorText).split(/\r?\n/)
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
  const particles = alternatives(String(particleText).split(/\r?\n/).map((line) => line.split('//')[0].trim()));
  const variantMap = (text) => new Map(String(text).split(/\r?\n/)
    .filter((line) => line.trim() && !line.trim().startsWith('#'))
    .map((line) => line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean))
    .filter((forms) => forms.length > 0)
    .flatMap(([canonical, ...forms]) => [canonical, ...forms].map((form) => [form.toLocaleLowerCase(), canonical])));
  const canonicalGiven = variantMap(namesText);
  const canonicalTitle = variantMap(titleText);
  const routeTitles = parsePersonNameRouteTitles(titleText);
  const canonicalByName = variantMap(byNamesText);
  const canonicalPlaces = new Map(places.flatMap((place) =>
    (place.variations || [place.name]).filter(Boolean).map((form) => [form.toLocaleLowerCase(), place.name || form])));
  const placeForms = [...canonicalPlaces.keys()].sort((left, right) => right.length - left.length);
  const canonicalizePlaces = (value) => placeForms.length
    ? String(value).replace(new RegExp(`(?<![\\p{L}\\p{N}])(?:${alternatives(placeForms)})(?![\\p{L}\\p{N}])`, 'giu'),
      (form) => canonicalPlaces.get(form.toLocaleLowerCase()) || form)
    : String(value);
  const particleForms = String(particleText).split(/\r?\n/).map((line) => line.split('//')[0].trim()).filter(Boolean);
  const normalizeRouteName = (value) => {
    let parts = String(value).trim().split(/\s+/);
    if (!parts.length) return '';
    const byNameIndex = parts.findIndex((part, index) => index > 0 && canonicalByName.has(part.toLocaleLowerCase()));
    const particleIndex = parts.findIndex((part, index) => index > 0 && particleForms.some((particle) => particle.toLocaleLowerCase() === part.toLocaleLowerCase()));
    const familyIndex = byNameIndex >= 0 ? byNameIndex : particleIndex >= 0 ? particleIndex : 1;
    for (let index = 0; index < familyIndex; index += 1) {
      parts[index] = canonicalGiven.get(parts[index].toLocaleLowerCase()) || parts[index];
    }
    if (byNameIndex >= 0) parts[byNameIndex] = canonicalByName.get(parts[byNameIndex].toLocaleLowerCase()) || parts[byNameIndex];
    parts = parts.map((part) => part.toLocaleLowerCase() === 'zum' ? 'zu' : part);
    const byNameZuRosenberg = byNameIndex >= 0 && particleIndex === byNameIndex + 1
      && parts[particleIndex]?.toLocaleLowerCase() === 'zu'
      && parts[particleIndex + 1]?.toLocaleLowerCase() === 'rosenberg';
    if (byNameZuRosenberg) parts[particleIndex] = 'von';
    if (particleIndex >= 0) {
      const particle = parts[particleIndex].toLocaleLowerCase();
      if (particle === 'v.' || particle === 'von.') parts[particleIndex] = 'von';
    }
    const surnameStart = particleIndex >= 0 ? particleIndex + 2 : byNameIndex >= 0 ? byNameIndex + 1 : 1;
    const titlePlaceIndex = parts.findIndex((part, index) => index >= surnameStart
      && ['zu', 'zum'].includes(part.toLocaleLowerCase()));
    if (titlePlaceIndex >= 0) parts = parts.slice(0, titlePlaceIndex);
    return canonicalizePlaces(parts.join(' '));
  };
  const givenNameForms = alternatives(String(namesText).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean)));
  const standaloneTitledGivenName = titles && givenNameForms
    ? String(name).match(new RegExp(`^(${titles})\\s+(${givenNameForms})$`, 'iu'))
    : null;
  if (standaloneTitledGivenName) {
    const title = canonicalTitle.get(standaloneTitledGivenName[1].toLocaleLowerCase()) || standaloneTitledGivenName[1];
    const givenName = canonicalGiven.get(standaloneTitledGivenName[2].toLocaleLowerCase()) || standaloneTitledGivenName[2];
    return routeTitles.has(title.toLocaleLowerCase()) ? `${title} ${givenName}` : givenName;
  }
  const birthName = String(name).match(/^(.*?)[\s,;]+\(?\s*(?:née|nee)[\s,;]+(.+?)\s*\)?$/iu);
  if (birthName) {
    const marriedRoute = personRouteName(birthName[1], titleText, connectorText, particleText, namesText, byNamesText, places);
    const particleSurname = particles && new RegExp(`[\\s,;]+(?:${particles}|of)\\s+.+$`, 'iu').test(marriedRoute);
    const givenNames = particleSurname
      ? marriedRoute.replace(new RegExp(`[\\s,;]+(?:${particles}|of)\\s+.+$`, 'iu'), '')
      : marriedRoute.replace(/[\s,;]+\S+$/u, '');
    const canonicalGivenNames = givenNames.replace(/[\p{L}’'-]+/gu,
      (form) => canonicalGiven.get(form.toLocaleLowerCase()) || form);
    return normalizeRouteName(`${canonicalGivenNames} ${birthName[2]}`);
  }
  const ordinal = '(?:\\s+(?:\\(\\s*[IVXLCDM]+\\s*\\)|\\[\\s*[IVXLCDM]+\\s*\\]|[IVXLCDM]+\\.?))?';
  const titleSequence = titles ? `(?:[\\s,]+(?:${titles}))*` : '';
  const byNameForms = [];
  String(byNamesText).split(/\r?\n/).filter((line) => !line.trim().startsWith('#'))
    .forEach((line) => line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean).forEach((form) => byNameForms.push(form)));
  let routeName = String(name)
    .replace(/[\s,;]+(?:née|nee)[\s,;]+/iu, ' ')
    .replace(new RegExp(`^(?:${titles})[\\s,;]+(?:${connectors})[\\s,;]+`, 'iu'), '')
    .replace(new RegExp(`^(?:${titles}(?:\\s+(?:zu|zum|an|of)\\s+[^,]+)?[\\s,;]+)+`, 'iu'), '')
    .replace(new RegExp(`^(?:${connectors})\\s+`, 'iu'), '')
    .replace(/\s*\(\s*or\s+[^)]*\)/iu, '')
    .replace(new RegExp(`${ordinal}${titleSequence}[\\s,;]+(?=(?:von|v\\.?|van|de|in|der|die|das|des|of)\\b)`, 'iu'), ' ')
    .replace(new RegExp(`[\\s,;]+(?:${titles})(?:\\s+(?:zu|zum|an|of)\\s+[^,;]+)?(?:[\\s,;]+(?:${titles})(?:\\s+(?:zu|zum|an|of)\\s+[^,;]+)?)*$`, 'iu'), '')
    .replace(new RegExp(`[\\s,;]+(?:${connectors})[\\s,;]+(?:${particles})\\s+[^,;]+$`, 'iu'), '')
    .replace(/\s*\([^)]*\)$/u, '')
    .trim();
  if (byNameForms.length) {
    const byNamePattern = alternatives(byNameForms);
    routeName = routeName.replace(new RegExp(`\\b(${byNamePattern})[\\s,;]+(?:zu|von|v\\.?|von\\.)[\\s,;]+(Rosenberg)\\b`, 'iu'), '$1 von $2');
  }
  return normalizeRouteName(routeName);
}
