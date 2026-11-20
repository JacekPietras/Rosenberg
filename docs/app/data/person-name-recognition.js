function escapePattern(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
}

function alternatives(values) {
  return [...new Set(values.filter(Boolean))]
    .sort((left, right) => right.length - left.length)
    .map(escapePattern)
    .join('|');
}

// name-connectors.md groups equivalent forms under section comments. Older
// callers may still provide a single unsectioned connector list.
function parseNameConnectorGroups(markdown = '', section = 'alternate surname connectors') {
  const lines = String(markdown).split(/\r?\n/);
  const hasSections = lines.some((line) => /^\/\/\s*[^/].*$/u.test(line.trim()));
  let active = !hasSections && section === 'alternate surname connectors';
  const groups = [];
  for (const line of lines) {
    const header = line.trim().match(/^\/\/\s*(.*?)\s*$/u);
    if (header) {
      active = header[1].toLocaleLowerCase() === section;
      continue;
    }
    if (!active) continue;
    const forms = line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean);
    if (forms.length) groups.push(forms);
  }
  return groups;
}

export function personMentionClass(name, connectorText = '', particleText = '') {
  const connectors = alternatives(parseNameConnectorGroups(connectorText).flat());
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

// Split only title forms that are listed in the project's title vocabulary.
// Longest-first matching keeps multiword titles intact.
export function splitPersonNameTitles(value, titleText = '') {
  let name = String(value ?? '').trim();
  const knownTitles = parsePersonNameTitles(titleText)
    .sort((left, right) => right.length - left.length);
  const titles = [];
  let changed = true;
  while (changed) {
    changed = false;
    for (const title of knownTitles) {
      const match = name.match(new RegExp(`(?:\\s+|,\\s*)(${escapePattern(title)})$`, 'iu'));
      if (!match) continue;
      name = name.slice(0, match.index).trim().replace(/[,;\\s]+$/u, '');
      titles.unshift(match[1]);
      changed = true;
      break;
    }
  }
  // A one-word remainder is usually a surname that happens to match an office
  // (for example, Georg Keller), not a title attached to a full name.
  if (titles.length && name.split(/\s+/u).length < 2) return { name: String(value ?? '').trim(), titles: [] };
  return { name, titles };
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
  const sharedTitle = titles ? `(?:[,\\s]+(?<sharedTitle>${titles}|(?:zu|zum)\\s+[\\p{L}][\\p{L}'’.-]*))?` : '';
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
      let route = personRouteName(match[0], titleText, connectorText,
        particleText, namesText, byNamesText, places);
      const placeSuffix = match[0].match(/\s+(?:zu|zum)\s+([^\s,;]+)$/iu);
      const prefix = placeSuffix ? match[0].slice(0, placeSuffix.index).trim() : '';
      const place = placeSuffix && places.flatMap((item) => item.variations || [item.name])
        .find((form) => form.toLocaleLowerCase() === placeSuffix[1].toLocaleLowerCase());
      const hasVonUndZuName = /\bvon\s+(?:und|u\.|and)\s+zu\s+[^\s,;]+$/iu.test(match[0]);
      const prefixHasTitle = prefix && splitPersonNameTitles(prefix, titleText).titles.length > 0;
      const byNameForms = new Set(String(byNamesText).split(/\r?\n/)
        .filter((line) => !line.trim().startsWith('#'))
        .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim().toLocaleLowerCase())));
      const titleGroups = String(titleText).split(/\r?\n/)
        .filter((line) => line.trim() && !line.trim().startsWith('#') && !line.trim().startsWith('//'))
        .map((line) => line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean));
      const canonicalTitles = new Map(titleGroups.flatMap((group) => group
        .filter((form) => !byNameForms.has(form.toLocaleLowerCase()))
        .map((form) => [form.toLocaleLowerCase(), group[0]])));
      const trailingTitle = titleFormsPattern(canonicalTitles).exec(match[0]);
      if (trailingTitle) {
        route = personRouteName(match[0].slice(0, trailingTitle.index).trim(), titleText,
          connectorText, particleText, namesText, byNamesText, places);
      }
      const leadingTitle = new RegExp(`^(${alternatives([...canonicalTitles.keys()])})\\s+`, 'iu').exec(match[0]);
      const givenNamesPattern = alternatives(String(namesText).split(/\r?\n/)
        .filter((line) => !line.trim().startsWith('#'))
        .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
      const leadingTitleLocative = leadingTitle && places.length
        ? new RegExp(`^(${alternatives([...canonicalTitles.keys()])})\\s+((?:${givenNamesPattern})(?:\\s+(?:${givenNamesPattern}))*)\\s+(?:of|zu|zum)\\s+(${alternatives(places.flatMap((item) => item.variations || [item.name]))})$`, 'iu').exec(match[0])
        : null;
      const titlePlace = trailingTitle?.[2] && places.flatMap((item) => item.variations || [item.name])
        .find((form) => form.toLocaleLowerCase() === trailingTitle[2].toLocaleLowerCase());
      const leadingPlaceRecord = leadingTitleLocative && places.find((item) =>
        (item.variations || [item.name]).some((form) => form.toLocaleLowerCase() === leadingTitleLocative[3].toLocaleLowerCase()));
      const leadingPlace = leadingPlaceRecord?.name || leadingPlaceRecord?.variations?.[0];
      const designation = connectorDesignation(match[0], connectorText, particleText, places);
      const titles = designation
        ? [designation]
        : leadingPlace
          ? [`${canonicalTitles.get(leadingTitleLocative[1].toLocaleLowerCase())} zu ${leadingPlace}`]
        : leadingTitle
          ? [canonicalTitles.get(leadingTitle[1].toLocaleLowerCase())]
        : trailingTitle
        ? [`${canonicalTitles.get(trailingTitle[1].toLocaleLowerCase())}${titlePlace ? ` zu ${titlePlace}` : trailingTitle[2] ? ` zu ${trailingTitle[2]}` : ''}`]
        : place && hasVonUndZuName
          ? [`zu ${place}`]
        : place && !prefixHasTitle
          && personRouteName(prefix, titleText, connectorText, particleText, namesText, byNamesText, places) === route
          ? [`zu ${place}`] : [];
      if (leadingTitle && trailingTitle && !leadingPlace) {
        titles.push(`${canonicalTitles.get(trailingTitle[1].toLocaleLowerCase())}${titlePlace ? ` zu ${titlePlace}` : trailingTitle[2] ? ` zu ${trailingTitle[2]}` : ''}`);
      }
      if (leadingPlace) {
        route = personRouteName(leadingTitleLocative[2], titleText, connectorText,
          particleText, namesText, byNamesText, places);
      }
      singles.push({ kind: candidate.kind, text: match[0], start, end, route, titles, people: candidate.people });
    }
    if (lastIndex !== undefined) pattern.lastIndex = lastIndex;
  }
  return { coordinated, singles };
}

function titleFormsPattern(canonicalTitles) {
  const titles = [...canonicalTitles.keys()].sort((left, right) => right.length - left.length);
  return new RegExp(`(?:^|[,;]\\s*|\\s+)(${alternatives(titles)})(?:\\s+(?:zu|zum|an|of)\\s+([\\p{L}][\\p{L}'’.-]*))?$`, 'iu');
}

function connectorDesignation(text, connectorText, particleText, places) {
  const groups = parseNameConnectorGroups(connectorText);
  const canonical = new Map(groups.flatMap((group) => group.map((form) => [form.toLocaleLowerCase(), group[0]])));
  const connectors = alternatives([...canonical.keys()]);
  const particleGroups = String(particleText).split(/\r?\n/)
    .filter((line) => line.trim() && !line.trim().startsWith('#'))
    .map((line) => line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean));
  const particleCanonical = new Map(particleGroups.flatMap((group) => group.map((form) => [form.toLocaleLowerCase(), group[0]])));
  const particles = alternatives([...particleCanonical.keys()]);
  const placeForms = [...new Set(places.flatMap((place) => place.variations || [place.name]).filter(Boolean))];
  if (!connectors || !particles || !placeForms.length) return null;
  const pattern = new RegExp(`[,;]\\s*(${connectors})\\s+(${particles})\\s+(${alternatives(placeForms)})$`, 'iu');
  const match = String(text).match(pattern);
  if (!match) return null;
  const place = placeForms.find((form) => form.toLocaleLowerCase() === match[3].toLocaleLowerCase());
  const particle = particleCanonical.get(match[2].toLocaleLowerCase()) || match[2];
  const canonicalParticle = ['v.', 'von.'].includes(particle.toLocaleLowerCase()) ? 'von' : particle;
  return `${canonical.get(match[1].toLocaleLowerCase())} ${canonicalParticle} ${place}`;
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
      Array.from({ length: name.length - 1 }, (_, index) => [
        `${escapePattern(name.slice(0, index + 1))}\\(${escapePattern(name.slice(index + 1))}\\)`,
        `${escapePattern(name.slice(0, index + 1))}\\[${escapePattern(name.slice(index + 1))}\\]`,
      ]).flat())
  ])].sort((left, right) => right.length - left.length).join('|');
  const particles = alternatives(String(particlesText || '').split(/\r?\n/).map((line) => line.split('//')[0].trim()));
  const placeNames = alternatives(places.flatMap((place) => place.variations || [place.name]));
  const titles = alternatives(parsePersonNameTitles(titleText));
  const routeTitles = alternatives([...parsePersonNameRouteTitles(titleText)]);
  const connectors = alternatives(parseNameConnectorGroups(connectorText).flat());
  const byNames = alternatives(String(byNamesText).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim())));
  if (!names || !particles || !placeNames) return null;
  const romanOrdinal = '(?:\\s+(?:\\(\\s*[IVXLCDM]+\\s*\\)|\\[\\s*[IVXLCDM]+\\s*\\]|[IVXLCDM]+\\.?))?';
  const titlePlace = `(?:${placeNames}|[\\p{L}][\\p{L}'’.-]*)`;
  const titleMatch = titles ? `(?:${titles})(?:\\s+(?:zu|zum|an|of)\\s+${titlePlace})?` : '(?!)';
  const titleSuffixMatch = titles ? `(?:${titleMatch})(?!\\s+(?:${names})\\b)` : '(?!)';
  const byNameBeforeParticle = byNames ? `(?!(?:${byNames})\\s+(?:${particles}|of)\\s)` : '';
  const titleSequence = titles ? `(?:[\\s,;]+${byNameBeforeParticle}${titleSuffixMatch})*` : '';
  const leadingTitles = titles ? `(?:${titleMatch}\\s+)*` : '';
  const particle = `(?:${particles}|of)`;
  const familyParticle = `(?:${particle}|von\\s+(?:und|u\\.|and)\\s+zu)`;
  const placeClause = `(?:${placeNames})(?:\\s+(?:zu|zum|an)\\s+(?:${placeNames}))?`;
  const suffixTitles = `(?:[\\s,;]+${titleSuffixMatch})*`;
  const placeNote = '(?:\\s*\\(-?[\\p{L}\\p{N}]+-?\\))?';
  const nameNote = '(?:\\s*\\(\\s*or\\s+[^)]*\\))?';
  const leadingConnector = connectors ? `(?:(?:${connectors})\\s+)?` : '';
  const namingConnector = connectors ? `(?:\\s+(?:${connectors}))?` : '';
  const alternateDesignation = connectors ? `(?:[\\s,;]+(?:${connectors})[\\s,;]+${particle}\\s+${placeClause})?` : '';
  const birthMarkers = alternatives(parseNameConnectorGroups(connectorText, 'birth-name markers').flat());
  const birthSurname = birthMarkers ? `[\\s,;]+\\(?\\s*(?:${birthMarkers})[\\s,;]+(?:(?:${names}|${byNames})\\s+)?(?:von|v\\.?|van|de|in|der|die|das|des|of|zu)\\s+(?:${placeNames})\\s*\\)?` : '(?!)';
  const byNameSurname = byNames ? `[\\s,]+(?:${byNames})(?:\\s+(?:${particle})\\s+(?:${placeNames}))?(?:\\s+(?:zu|zum)\\s+${titlePlace})?${placeNote}${suffixTitles}` : '(?!)';
  const surname = `(?:${byNameSurname}|[\\s,]+${familyParticle}\\s+${placeClause}${placeNote}${suffixTitles}${alternateDesignation}(?:${birthSurname})?|${birthSurname}|[\\s,]+(?:${placeNames})${birthSurname}|[\\s,]+(?:${placeNames}))`;
  const titledGivenName = routeTitles ? `(?:${routeTitles})\\s+(?:${names})(?![\\p{L}\\p{N}])` : '(?!)';
  // Some English catalogues give a person only by their given name and office,
  // e.g. "Eberhard, Bishop of Rosenberg". Keep this form restricted to a
  // listed title and place so it does not turn ordinary prose into people.
  const titleOnlyLocative = titles
    ? `[\\s,;]+(${titles})\\s+of\\s+(${placeNames})`
    : '(?!)';
  return new RegExp(`(?<![\\p{L}\\p{N}])(?:${leadingTitles}${leadingConnector}(?:${names})(?:\\s+(?:${names}))*${nameNote}${romanOrdinal}${titleSequence}${namingConnector}${surname}(?![\\p{L}\\p{N}])|(?:${names})${titleOnlyLocative}(?![\\p{L}\\p{N}])|${titledGivenName})`, 'giu');
}

export function personRouteName(name, titleText = '', connectorText = '', particleText = '', namesText = '', byNamesText = '', places = []) {
  const titles = alternatives(parsePersonNameTitles(titleText));
  const connectors = alternatives(parseNameConnectorGroups(connectorText).flat());
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
    (place.variations || [place.name]).filter(Boolean).map((form) => [
      form.toLocaleLowerCase(), place.name || place.variations?.[0] || form,
    ])));
  const placeForms = [...canonicalPlaces.keys()].sort((left, right) => right.length - left.length);
  const locativePlaceSuffix = (value) => placeForms.find((form) =>
    /^(?:zu|zum)\s/u.test(form)
      && String(value).trim().toLocaleLowerCase().endsWith(` ${form}`));
  const canonicalizePlaces = (value) => placeForms.length
    ? String(value).replace(new RegExp(`(?<![\\p{L}\\p{N}])(?:${alternatives(placeForms)})(?![\\p{L}\\p{N}])`, 'giu'),
      (form) => canonicalPlaces.get(form.toLocaleLowerCase()) || form)
    : String(value);
  const particleForms = String(particleText).split(/\r?\n/).map((line) => line.split('//')[0].trim()).filter(Boolean);
  const normalizeRouteName = (value) => {
    const namedPlace = locativePlaceSuffix(value);
    if (namedPlace) {
      const placeStart = String(value).trim().length - namedPlace.length;
      const personName = String(value).trim().slice(0, placeStart).trim()
        .replace(/[\p{L}’'-]+/gu, (form) => canonicalGiven.get(form.toLocaleLowerCase()) || form);
      return `${personName} ${canonicalPlaces.get(namedPlace) || namedPlace}`;
    }
    let parts = String(value).trim().split(/\s+/);
    if (!parts.length) return '';
    const vonUndZuIndex = parts.findIndex((part, index) => index > 0
      && part.toLocaleLowerCase() === 'von'
      && ['und', 'u.', 'and'].includes(parts[index + 1]?.toLocaleLowerCase())
      && parts[index + 2]?.toLocaleLowerCase() === 'zu');
    if (vonUndZuIndex >= 0) parts.splice(vonUndZuIndex + 1, 2);
    const englishPlaceParticleIndex = parts.findIndex((part, index) => index > 0
      && part.toLocaleLowerCase() === 'of'
      && canonicalPlaces.has(parts[index + 1]?.toLocaleLowerCase()));
    if (englishPlaceParticleIndex >= 0) parts[englishPlaceParticleIndex] = 'zu';
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
  const birthMarkers = alternatives(parseNameConnectorGroups(connectorText, 'birth-name markers').flat());
  const birthName = birthMarkers && String(name).match(new RegExp(`^(.*?)[\\s,;]+\\(?\\s*(?:${birthMarkers})[\\s,;]+(.+?)\\s*\\)?$`, 'iu'));
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
  const byNameKeys = new Set(canonicalByName.keys());
  const middleTitles = alternatives(parsePersonNameTitles(titleText).filter((form) => !byNameKeys.has(form.toLocaleLowerCase())));
  const titleSequence = middleTitles ? `(?:[\\s,]+(?:${middleTitles}))*` : '';
  const byNameSurname = givenNameForms && byNameKeys.size
    ? new RegExp(`^(?:${givenNameForms})(?:\\s+(?:${givenNameForms}))*\\s+(?:${alternatives([...byNameKeys])})${placeForms.length ? `(?:\\s+(?:von|v\\.|von\\.|vom|van|de|zu|zum)\\s+(?:${alternatives(placeForms)}))?` : ''}$`, 'iu').test(String(name).trim())
    : false;
  const preserveLocativePlaceName = locativePlaceSuffix(name) !== undefined;
  const byNameForms = [];
  String(byNamesText).split(/\r?\n/).filter((line) => !line.trim().startsWith('#'))
    .forEach((line) => line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean).forEach((form) => byNameForms.push(form)));
  let routeName = String(name)
    .replace(birthMarkers ? new RegExp(`[\\s,;]+(?:${birthMarkers})[\\s,;]+`, 'iu') : /$^/u, ' ')
    .replace(new RegExp(`^(?:${titles})[\\s,;]+(?:${connectors})[\\s,;]+`, 'iu'), '')
    .replace(new RegExp(`^(?:(?:${titles})(?:\\s+(?:zu|zum|an|of)\\s+[^,]+)?[\\s,;]+)+`, 'iu'), '')
    .replace(new RegExp(`^(?:${connectors})\\s+`, 'iu'), '')
    .replace(/\s*\(\s*or\s+[^)]*\)/iu, '')
    .replace(new RegExp(`${ordinal}${titleSequence}[\\s,;]+(?=(?:von|v\\.?|van|de|in|der|die|das|des|of)\\b)`, 'iu'), ' ')
    .replace(preserveLocativePlaceName || byNameSurname ? /$^/u : new RegExp(`[\\s,;]+(?:${titles})(?:\\s+(?:zu|zum|an|of)\\s+[^,;]+)?(?:[\\s,;]+(?:${titles})(?:\\s+(?:zu|zum|an|of)\\s+[^,;]+)?)*$`, 'iu'), '')
    .replace(new RegExp(`[\\s,;]+(?:${connectors})[\\s,;]+(?:${particles})\\s+[^,;]+$`, 'iu'), '')
    .replace(/\s*\([^)]*\)$/u, '')
    // Historical names sometimes spell an uncertain ending in parentheses or
    // square brackets (for example, Eber(hard) / Eber[hard]). These delimiters
    // are editorial; the enclosed letters belong to the canonical name.
    .replace(/([\p{L}])\(([\p{L}]+)\)/gu, '$1$2')
    .replace(/([\p{L}])\[([\p{L}]+)\]/gu, '$1$2')
    .trim();
  if (byNameForms.length) {
    const byNamePattern = alternatives(byNameForms);
    routeName = routeName.replace(new RegExp(`\\b(${byNamePattern})[\\s,;]+(?:zu|von|v\\.?|von\\.)[\\s,;]+(Rosenberg)\\b`, 'iu'), '$1 von $2');
  }
  return normalizeRouteName(routeName);
}
