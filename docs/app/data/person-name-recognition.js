// Person-name recognition.
//
// 1. A dictionary is built once per set of data files and places (`dictionaryFor`).
// 2. A span regex finds candidate mentions in free text (`composeSourceSource`).
// 3. Each span is cleaned, scanned into parts (given names, ordinal, by-name,
//    particle, place, titles, designations, birth name) and resolved into a
//    route name plus canonical titles (`analyze`). Rules: specs/person-names.md.

const LETTER_AFTER = '(?![\\p{L}\\p{N}])';
const LETTER_BEFORE = '(?<![\\p{L}\\p{N}])';
const ROMAN = '[IVXLCDM]+';
const WORD = "\\p{L}[\\p{L}'’-]*";
const SAINT_BEFORE = '(?<!(?<![\\p{L}])(?:St|Sankt|Saint|Hl)\\.?\\s)';
const NON_PLACE_WORDS = ['the', 'a', 'an', 'der', 'die', 'das', 'dem', 'den', 'des', 'ein', 'eine', 'einem',
  'einer', 'he', 'she', 'it', 'they', 'we', 'his', 'her', 'their', 'our', 'its', 'this', 'that', 'these',
  'those', 'who', 'whom', 'which', 'what', 'and', 'und', 'or', 'oder', 'in', 'im', 'on', 'at', 'to', 'of',
  'from', 'by', 'with', 'for', 'as', 'is', 'was', 'were', 'be', 'nach', 'von', 'vom', 'zu', 'zum', 'an',
  'bei', 'st', 'sankt', 'saint', 'hl'];
const FALLBACK_PARTICLES = ['von', 'vom', 'v.', 'von.', 'van', 'de', 'in', 'der', 'die', 'das', 'des', 'zu'];
const SECTION_KINDS = {
  'ranks': 'rank', 'territorial titles': 'territorial', 'family titles': 'family', 'route titles': 'route',
};
const ROSENBERG = 'rosenberg';

const lower = (value) => String(value).toLocaleLowerCase();
const escapePattern = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
const alternatives = (values) => [...new Set(values.filter(Boolean))]
  .sort((left, right) => right.length - left.length).map(escapePattern).join('|');
const never = '(?!)';

function dataGroups(text) {
  return String(text ?? '').split(/\r?\n/).map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#') && !line.startsWith('//'))
    .map((line) => line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean))
    .filter((group) => group.length);
}

const variantMap = (groups) => new Map(groups.flatMap(([canonical, ...forms]) =>
  [canonical, ...forms].map((form) => [lower(form), canonical])));

// Name connectors group equivalent forms under `// section` comments; an old
// unsectioned file is a single list of surname connectors.
function parseNameConnectorGroups(markdown = '', section = 'alternate surname connectors') {
  const lines = String(markdown).split(/\r?\n/);
  const hasSections = lines.some((line) => /^\/\/\s*[^/].*$/u.test(line.trim()));
  let active = !hasSections && section === 'alternate surname connectors';
  const groups = [];
  for (const line of lines) {
    const header = line.trim().match(/^\/\/\s*(.*?)\s*$/u);
    if (header) {
      active = lower(header[1]) === section;
      continue;
    }
    if (!active) continue;
    const forms = line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean);
    if (forms.length) groups.push(forms);
  }
  return groups;
}

// `// section` comments classify groups (territorial, family, route titles);
// `# Younger` / `# Older` mark age titles. Everything else is a plain office.
function parseTitleGroups(text) {
  const groups = [];
  let kind = 'office';
  let age = false;
  for (const raw of String(text ?? '').split(/\r?\n/)) {
    const line = raw.trim();
    const section = line.match(/^\/\/\s*(.*)$/u);
    const marker = line.match(/^#\s*(.*)$/u);
    if (section) {
      kind = SECTION_KINDS[lower(section[1].trim())] ?? 'office';
      age = false;
    } else if (marker) {
      age = /^(?:younger|older)$/iu.test(marker[1].trim());
    } else if (line) {
      const forms = line.split('//')[0].split(',').map((form) => form.trim()).filter(Boolean);
      if (forms.length) groups.push({ forms, canonical: forms[0], kind: age ? 'age' : kind });
    }
  }
  return groups;
}

// ---------------------------------------------------------------- dictionary

// The canonical form of a place is the first variation of its places.json record.
const canonicalPlaceName = (place) => place.variations?.[0] ?? place.name;

const dictionaries = new Map();
const NO_PLACES = [];

function dictionaryFor(titleText, connectorText, particleText, namesText, byNamesText, places) {
  const list = Array.isArray(places) ? places : NO_PLACES;
  const keys = [titleText, connectorText, particleText, namesText, byNamesText].map((text) => String(text ?? ''));
  let node = dictionaries;
  keys.forEach((key, index) => {
    if (!node.has(key)) node.set(key, index === keys.length - 1 ? new WeakMap() : new Map());
    node = node.get(key);
  });
  const cached = node.get(list);
  if (cached && cached.size === list.length) return cached.dictionary;
  const dictionary = buildDictionary(...keys, list);
  node.set(list, { size: list.length, dictionary });
  return dictionary;
}

function givenNameForms(groups) {
  const forms = groups.flat();
  const editorial = forms.filter((form) => /^\p{L}+$/u.test(form)).flatMap((form) =>
    Array.from({ length: form.length - 1 }, (_, index) => [
      `${form.slice(0, index + 1)}(${form.slice(index + 1)})`,
      `${form.slice(0, index + 1)}[${form.slice(index + 1)}]`,
    ]).flat());
  return [...forms, ...editorial];
}

function buildDictionary(titleText, connectorText, particleText, namesText, byNamesText, places) {
  const nameGroups = dataGroups(namesText);
  const byNameGroups = dataGroups(byNamesText);
  const particleForms = dataGroups(particleText).map((group) => group[0]);
  const titleGroups = parseTitleGroups(titleText);
  const connectorGroups = parseNameConnectorGroups(connectorText);
  const birthGroups = parseNameConnectorGroups(connectorText, 'birth-name markers');
  const placeRecords = places.flatMap((place) => {
    const canonical = canonicalPlaceName(place);
    return (place.variations || [place.name]).filter(Boolean).map((form) => [form, canonical]);
  });

  // Seats (sees, territories, realms) arrive as extra sections of the connector text.
  const seatSections = { territorial: ['sees', 'territories'], realm: ['realms'] };
  const seatForm = new Map();
  const seatSet = { territorial: new Set(), realm: new Set() };
  for (const [kind, sections] of Object.entries(seatSections)) {
    for (const group of sections.flatMap((section) => parseNameConnectorGroups(connectorText, section))) {
      seatSet[kind].add(lower(group[0]));
      group.forEach((form) => seatForm.set(lower(form), group[0]));
    }
  }
  const titleForms = (kinds) => titleGroups.filter((group) => kinds.includes(group.kind)).flatMap((group) => group.forms);
  const dictionary = {
    given: variantMap(nameGroups),
    byName: variantMap(byNameGroups),
    titles: new Map(titleGroups.flatMap((group) => group.forms.map((form) => [lower(form), group]))),
    connector: variantMap(connectorGroups),
    place: new Map(placeRecords.map(([form, name]) => [lower(form), name])),
    seatForm,
    seatSet,
    particle: new Map([...particleForms, 'of', 'zum'].map((form) => [lower(form), form])),
    alt: {
      given: alternatives(givenNameForms(nameGroups)),
      byName: alternatives(byNameGroups.flat()),
      particle: alternatives([...particleForms, 'of']),
      title: alternatives(titleGroups.flatMap((group) => group.forms)),
      plainTitle: alternatives(titleForms(['office', 'rank', 'age'])),
      wideTitle: alternatives(titleForms(['territorial', 'family', 'route'])),
      routeTitle: alternatives(titleForms(['territorial', 'route'])),
      realmTitle: alternatives(titleForms(['route'])),
      place: alternatives(placeRecords.map(([form]) => form)),
      connector: alternatives(connectorGroups.flat()),
      birth: alternatives(birthGroups.flat()),
    },
  };
  const parseParticles = particleForms.length ? particleForms : FALLBACK_PARTICLES;
  const sticky = (source) => new RegExp(source || never, 'iuy');
  const { alt } = dictionary;
  const stop = `(?!(?:${NON_PLACE_WORDS.join('|')})${LETTER_AFTER})`;
  dictionary.re = {
    title: sticky(alt.title && `(?:${alt.title})${LETTER_AFTER}`),
    given: sticky(alt.given && `(?:${alt.given})${LETTER_AFTER}`),
    byName: sticky(alt.byName && `(?:${alt.byName})${LETTER_AFTER}`),
    particle: sticky(`(?:${alternatives([...parseParticles, 'of', 'zum'])})${LETTER_AFTER}`),
    place: sticky(alt.place && `(?:${alt.place})${LETTER_AFTER}`),
    connector: sticky(alt.connector && `(?:${alt.connector})${LETTER_AFTER}`),
    birth: sticky(alt.birth && `(?:${alt.birth})${LETTER_AFTER}`),
    ordinal: sticky(`${ROMAN}${LETTER_AFTER}\\.?`),
    word: sticky(WORD),
    unlisted: sticky(`${stop}${WORD}${LETTER_AFTER}`),
    vonUndZu: sticky(`von\\s+(?:und|u\\.|and)\\s+zu${LETTER_AFTER}`),
    locativeZu: sticky('(?:zu|zum|an)\\s+'),
    possessive: sticky("[’']s(?![\\p{L}])"),
    realmConnective: sticky('\\s+(?:of|von)\\s+'),
    plainConnective: sticky('\\s+(?:zu|zum|an|of)\\s+'),
    wideConnective: sticky('\\s+(?:zu|zum|an|of|von|vom)\\s+'),
    birthParen: alt.birth ? new RegExp(`\\(\\s*((?:${alt.birth})${LETTER_AFTER}[^)]*)\\)`, 'giu') : null,
  };
  dictionary.stop = stop;
  return dictionary;
}

// ------------------------------------------------------------ span patterns

function composeSourceSource(d) {
  const { alt } = d;
  const N = LETTER_AFTER;
  const given = `(?:${alt.given})`;
  const names = `${given}(?:\\s+${given})*`;
  const place = `(?:${alt.place})${N}`;
  const placeAny = `(?:${place}|${d.stop}${WORD}${N})`;
  const particle = `(?:${alt.particle})`;
  const clause = (connective, target) => `(?:\\s+${connective}\\s+${target})`;
  const plainConnective = '(?:zu|zum|an|of)';
  const wideConnective = '(?:zu|zum|an|of|von|vom)';
  const titleSpecs = [[alt.plainTitle, plainConnective], [alt.wideTitle, wideConnective]]
    .filter(([forms]) => forms);
  const nextGiven = `(?!\\s+${given}${N})`;
  const titleTail = titleSpecs.length
    ? `(?:${titleSpecs.map(([forms, connective]) => `(?:${forms})${N}${clause(connective, placeAny)}?`).join('|')})${nextGiven}`
    : never;
  const anyTitle = alt.title ? `(?:${alt.title})${N}` : never;
  const hasTitles = Boolean(alt.title);

  const leadingTitles = hasTitles ? `(?:${anyTitle}${clause(wideConnective, place)}?\\s+)*` : '';
  const leadingConnector = alt.connector ? `(?:(?:${alt.connector})\\s+)?` : '';
  const nameNote = '(?:\\s*\\(\\s*or\\s+[^)]*\\))?';
  const ordinal = `\\s+(?:\\(\\s*${ROMAN}\\s*\\)|\\[\\s*${ROMAN}\\s*\\]|${ROMAN}${N}\\.?)`;
  const byNameGuard = alt.byName ? `(?!(?:${alt.byName})\\s+(?:${particle})\\s)` : '';
  const innerTitles = hasTitles ? `(?:[\\s,;]+${byNameGuard}${titleTail})*` : '';
  const trailingTitles = hasTitles ? `(?:[\\s,;]+${titleTail})*` : '';
  const namingConnector = alt.connector ? `(?:\\s+(?:${alt.connector}))?` : '';
  const placeNote = '(?:\\s*\\(-?[\\p{L}\\p{N}]+-?\\))?';
  const placeClause = `${place}(?:\\s+(?:zu|zum|an)\\s+${place})*`;
  const designation = alt.connector
    ? `(?:[\\s,;]+(?:${alt.connector})[\\s,;]+${particle}\\s+${placeClause})?` : '';
  const birth = alt.birth
    ? `[\\s,;]+\\(?\\s*(?:${alt.birth})[\\s,;]+(?:(?:${given}|${alt.byName || never})\\s+)?${particle}\\s+${place}\\s*\\)?`
    : never;
  const byNameSurname = alt.byName
    ? `,?\\s+(?:${alt.byName})${N}(?:\\s+${particle}\\s+${place})?(?:\\s+(?:zu|zum)\\s+${placeAny})?${placeNote}${trailingTitles}`
    : never;
  const familySurname = `[\\s,]+(?:${particle}|von\\s+(?:und|u\\.|and)\\s+zu)\\s+${placeClause}${placeNote}${trailingTitles}${designation}(?:${birth})?`;
  const barePlace = `(?<!\\.)(?:,\\s|\\s)${place}${trailingTitles}(?:${birth})?`;
  const surname = `(?:${byNameSurname}|${familySurname}|${birth}|${barePlace})`;

  const full = `${leadingTitles}${leadingConnector}${names}${nameNote}(?:${ordinal})?${innerTitles}${namingConnector}${surname}${N}`;
  const titleLocative = alt.title
    ? [alt.plainTitle && `(?:${alt.plainTitle})${N}\\s+of`, alt.wideTitle && `(?:${alt.wideTitle})${N}\\s+(?:of|zu|zum|von|vom)`]
      .filter(Boolean).join('|')
    : '';
  const nameWithTitleLocative = titleLocative
    ? `${names}(?:${ordinal})?[\\s,;]+(?:${titleLocative})\\s+${place}${trailingTitles}${N}` : never;
  const titledName = alt.realmTitle
    ? `${leadingTitles}(?:${alt.realmTitle})${N}\\s+${names}(?:${ordinal})?(?:\\s+(?:of|von|zu|zum)\\s+${placeAny})?${N}` : never;
  return `${SAINT_BEFORE}${LETTER_BEFORE}(?:${full}|${nameWithTitleLocative}|${titledName})`;
}

function composeCoordinatedSource(d) {
  const { alt } = d;
  const N = LETTER_AFTER;
  const given = `(?:${alt.given})`;
  const givenItem = `${given}(?:\\s+${given})*`;
  const place = `(?:${alt.place})${N}`;
  const placeAny = `(?:${place}|${d.stop}${WORD}${N})`;
  const nextGiven = `(?!\\s+${given}${N})`;
  const sharedTitle = [
    alt.title && `(?:${alt.title})${N}(?:\\s+(?:zu|zum|an|of|von|vom)\\s+${placeAny})?${nextGiven}`,
    `(?:zu|zum)\\s+${placeAny}`,
  ].filter(Boolean).join('|');
  const surname = `(?<byName>${alt.byName})(?:\\s+(?<byNameParticle>${alt.particle})\\s+(?<byNamePlace>${alt.place}))?|(?<particle>${alt.particle})\\s+(?<place>${alt.place})`;
  return `${LETTER_BEFORE}(?<givenList>${givenItem}(?:\\s*,\\s*${givenItem})*(?:\\s*,?\\s+(?:and|und)\\s+${givenItem}))(?:,?\\s+brothers)?\\s+(?<surname>${surname})(?:[,\\s]+(?<sharedTitle>${sharedTitle}))?${N}`;
}

export function buildSourcePersonPattern(namesText, particlesText, places, titleText = '', connectorText = '', byNamesText = '') {
  const d = dictionaryFor(titleText, connectorText, particlesText, namesText, byNamesText, places);
  if (!d.alt.given || !d.alt.particle || !d.alt.place) return null;
  d.sourceSource ??= composeSourceSource(d);
  return new RegExp(d.sourceSource, 'giu');
}

// -------------------------------------------------------------- scan + resolve

function cleanSpan(raw, d) {
  let text = String(raw ?? '')
    .replace(/\s+/gu, ' ')
    .replace(/(\p{L})\((\p{L}+)\)/gu, '$1$2')
    .replace(/(\p{L})\[(\p{L}+)\]/gu, '$1$2')
    .replace(/\s*\(\s*or\s+[^)]*\)/giu, '')
    .replace(/\(\s*([IVXLCDM]+)\s*\)|\[\s*([IVXLCDM]+)\s*\]/gu, (_, round, square) => round ?? square);
  if (d.re.birthParen) text = text.replace(d.re.birthParen, '$1');
  return text
    .replace(/(\s*)\(-?[\p{L}\p{N}]+-?\)(\s*)/gu, (_, before, after) => (before || after ? ' ' : ''))
    .replace(/\s*\([^)]*\)\s*$/u, '')
    .replace(/\s+([,;])/gu, '$1')
    .trim()
    .replace(/[\s,;.]+$/u, '');
}

function scan(text, d) {
  const { re } = d;
  const state = { given: [], ordinal: '', family: null, birth: null, parts: [], rest: '' };
  let position = 0;
  const peek = (regex) => {
    regex.lastIndex = position;
    const match = regex.exec(text);
    return match ? match[0] : null;
  };
  const eat = (regex) => {
    const value = peek(regex);
    if (value !== null) position += value.length;
    return value;
  };
  const skipSpace = () => { while (text[position] === ' ') position += 1; };
  const skipSeparators = () => {
    let seen = false;
    for (;;) {
      skipSpace();
      if (text[position] !== ',' && text[position] !== ';') return seen;
      seen = true;
      position += 1;
    }
  };
  const canonicalPlace = (place) => d.place.get(lower(place)) ?? d.seatForm.get(lower(place)) ?? place;
  const isCapitalized = (word) => /^\p{Lu}/u.test(word);
  const eatCapitalized = (regex) => {
    const mark = position;
    const word = eat(regex);
    if (word === null || isCapitalized(word)) return word;
    position = mark;
    return null;
  };
  const capitalWord = () => eatCapitalized(re.word);
  let placeClean = false;
  const eatPlace = () => {
    const listed = eat(re.place);
    const place = listed ?? eatCapitalized(re.unlisted);
    if (place === null) return null;
    placeClean = eat(re.possessive) === null;
    return canonicalPlace(place);
  };
  const normalizeParticle = (word) => {
    const form = lower(word);
    if (form === 'v.' || form === 'von.') return 'von';
    return form === 'zum' ? 'zu' : d.particle.get(form) ?? form;
  };

  function eatTitle() {
    const start = position;
    const form = eat(re.title);
    if (!form) return null;
    const group = d.titles.get(lower(form));
    const entry = { type: 'title', group, kind: group.kind, form, clause: null, start };
    const mark = position;
    const connectives = { route: re.realmConnective, territorial: re.wideConnective, family: re.wideConnective };
    const connective = eat(connectives[group.kind] ?? re.plainConnective);
    if (connective) {
      const place = eatPlace();
      if (place && (group.kind !== 'route' || placeClean && d.seatSet.realm.has(lower(place)))) entry.clause = { connective: lower(connective.trim()), place };
      else position = mark;
    }
    return entry;
  }

  function eatFamilyPart() {
    const mark = position;
    let particle;
    let vonUndZu = false;
    if (eat(re.vonUndZu)) {
      particle = 'von';
      vonUndZu = true;
    } else {
      const word = eat(re.particle);
      if (!word) return null;
      particle = normalizeParticle(word);
    }
    skipSpace();
    const place = eatPlace();
    if (!place) {
      position = mark;
      return null;
    }
    return { particle, place, vonUndZu, clean: placeClean, text: `${particle} ${place}` };
  }

  const designation = (text) => state.parts.push({ type: 'designation', text });
  const markFamily = (family) => {
    state.family = family;
    state.parts.push({ type: 'family' });
  };
  const nameAhead = () => [re.given, re.connector, re.title].some((regex) => peek(regex) !== null) || /^\p{Lu}/u.test(peek(re.word) ?? '');

  // Leading titles and connectors ("Knight called Eberhard").
  for (;;) {
    skipSpace();
    const start = position;
    if (eat(re.connector)) {
      skipSpace();
      if (nameAhead()) continue;
      position = start;
      break;
    }
    const title = eatTitle();
    if (!title) break;
    skipSeparators();
    if (!nameAhead() || peek(re.particle) !== null) {
      position = start;
      break;
    }
    title.position = 'leading';
    state.parts.push(title);
  }

  // Given names: listed forms, or any first word when the dictionary lacks it.
  for (;;) {
    skipSpace();
    if (state.given.length && peek(re.byName) !== null) break;
    const known = eat(re.given);
    if (known) {
      state.given.push(d.given.get(lower(known)) ?? known);
      continue;
    }
    const unknownFirst = !state.given.length && [re.particle, re.birth, re.connector].every((regex) => peek(regex) === null)
      ? eat(re.word) : null;
    if (unknownFirst) {
      state.given.push(unknownFirst);
      continue;
    }
    break;
  }
  if (!state.given.length) return state;

  for (;;) {
    const separated = skipSeparators();
    if (position >= text.length) break;
    const mark = position;

    if (eat(re.possessive)) continue;
    const ordinal = /^[IVXLCDM]+\.?$/u.test(peek(re.ordinal) ?? '') ? eat(re.ordinal) : null;
    if (ordinal) {
      if (!state.ordinal) state.ordinal = ordinal.replace(/\.$/u, '');
      continue;
    }

    const connector = peek(re.connector);
    if (connector) {
      position += connector.length;
      skipSpace();
      const byName = eat(re.byName);
      skipSpace();
      const part = eatFamilyPart();
      if (!part && !byName) {
        position = mark;
        state.rest = text.slice(mark);
        break;
      }
      const alias = [byName && d.byName.get(lower(byName)), part?.text].filter(Boolean).join(' ');
      designation(`${d.connector.get(lower(connector))} ${alias}`.replace(/ vom /u, ' von '));
      continue;
    }

    if (peek(re.birth) !== null) {
      position += peek(re.birth).length;
      skipSeparators();
      const lead = eat(re.byName) ?? eat(re.given) ?? (peek(re.particle) ?? peek(re.place) ? null : capitalWord());
      skipSpace();
      const part = eatFamilyPart();
      const place = part ? null : eatPlace();
      if (!part && !place) {
        position = mark;
        state.rest = text.slice(mark);
        break;
      }
      const leadName = lead ? d.byName.get(lower(lead)) ?? d.given.get(lower(lead)) ?? lead : '';
      state.birth = [leadName, part ? part.text : place].filter(Boolean).join(' ');
      state.parts.push({ type: 'birth' });
      continue;
    }

    if (!state.family && peek(re.byName) !== null) {
      const byName = d.byName.get(lower(eat(re.byName)));
      const family = { kind: 'byName', byName };
      markFamily(family);
      skipSpace();
      const afterName = position;
      const locative = eat(re.locativeZu);
      if (locative) {
        const place = eatPlace();
        if (place && lower(place) === ROSENBERG) Object.assign(family, { particle: 'von', place });
        else if (place) designation(`zu ${place}`);
        else position = afterName;
      } else {
        const part = peek(re.title) === null ? eatFamilyPart() : null;
        if (part) {
          Object.assign(family, { particle: part.particle, place: part.place });
          if (part.vonUndZu) designation(`zu ${part.place}`);
        }
      }
      continue;
    }

    const title = eatTitle();
    if (title) {
      const afterTitle = position;
      skipSpace();
      if (peek(re.given) !== null) {
        position = mark;
        break;
      }
      position = afterTitle;
      // "Georg Keller": a lone title word after a single given name is a surname.
      const surnameLike = !state.family && state.given.length === 1 && !separated && !title.clause
        && title.kind !== 'age' && !/\s/u.test(title.form);
      if (surnameLike) {
        const mark2 = position;
        skipSpace();
        const particleFollows = peek(re.particle) !== null;
        position = mark2;
        if (!particleFollows) {
          markFamily({ kind: 'word', text: title.form });
          continue;
        }
      }
      title.position = state.family ? 'trailing' : 'inner';
      state.parts.push(title);
      continue;
    }

    if (!state.family) {
      const placeText = peek(re.place);
      if (placeText && /^(?:zu|zum|von|vom|v\.|de|van|an|in|der|die|das|des|of)\s/iu.test(placeText)) {
        position += placeText.length;
        markFamily({ kind: 'place', place: canonicalPlace(placeText) });
        continue;
      }
      const part = eatFamilyPart();
      if (part) {
        markFamily({ kind: 'particle', particle: part.particle, place: part.place, clean: part.clean });
        if (part.vonUndZu) designation(`zu ${part.place}`);
        continue;
      }
      if (placeText) {
        position += placeText.length;
        markFamily({ kind: 'place', place: canonicalPlace(placeText) });
        continue;
      }
      const word = capitalWord();
      if (word) {
        markFamily({ kind: 'word', text: word });
        continue;
      }
    } else {
      const locative = eat(re.locativeZu);
      if (locative) {
        const place = eatPlace();
        if (place) {
          designation(`${lower(locative.trim()) === 'an' ? 'an' : 'zu'} ${place}`);
          continue;
        }
        position = mark;
      }
    }
    state.rest = text.slice(mark);
    break;
  }
  return state;
}

function familyText(family) {
  if (!family) return '';
  if (family.kind === 'word') return family.text;
  if (family.kind === 'place') return family.place;
  const place = family.particle ? ` ${family.particle} ${family.place}` : '';
  return family.kind === 'byName' ? `${family.byName}${place}` : `${family.particle} ${family.place}`;
}

function titleConnective(title) {
  const { connective } = title.clause;
  if (connective === 'zum') return 'zu';
  if (connective === 'vom') return 'von';
  if (connective === 'of') return title.kind === 'family' || title.kind === 'route' ? 'von' : 'zu';
  return connective;
}

// Moves a place between a title and the family name according to the title kind.
function resolve(state, d) {
  const titles = state.parts.filter((part) => part.type === 'title');
  // `titles` is read again below, so dropped realm titles are filtered there.
  const married = state.family;
  let { family } = state;
  let attached = false;
  if (family?.kind === 'particle') {
    for (const title of [...titles].reverse()) {
      if (title.clause) continue;
      if (title.kind === 'family') {
        if (title.position !== 'leading') continue;
        title.clause = { connective: family.particle, place: family.place };
        family.particle = titleConnective(title);
        break;
      }
      const place = lower(family.place);
      const locative = ['of', 'zu'].includes(family.particle);
      if (title.kind === 'route') {
        if (['of', 'von', 'vom'].includes(family.particle) && family.clean && d.seatSet.realm.has(place)) {
          title.clause = { connective: family.particle, place: family.place };
          family = null;
        } else if (family.particle === 'of') {
          family = null;
        } else if (title.position === 'leading') {
          title.dropped = true;
        }
        break;
      }
      if (title.kind === 'territorial' && (title.position === 'leading'
        ? locative || d.seatSet.territorial.has(place) : locative)) {
        title.clause = { connective: family.particle, place: family.place };
        attached = true;
        family = null;
        break;
      }
    }
  }
  if (!family) {
    const familyTitle = titles.find((title) => title.kind === 'family' && title.clause);
    if (familyTitle) {
      family = { kind: 'particle', particle: titleConnective(familyTitle), place: familyTitle.clause.place };
    }
  }

  const out = [];
  for (const part of state.parts) {
    if (part.type === 'designation') out.push(part.text);
    else if (part.type === 'family') {
      if (state.birth && married) out.push(familyText(married));
    } else if (part.type === 'title' && !part.dropped) {
      const { canonical } = part.group;
      if (!part.clause) out.push(canonical);
      else if (part.kind === 'age' || part.kind === 'rank') out.push(canonical, `${titleConnective(part) === 'an' ? 'an' : 'zu'} ${part.clause.place}`);
      else out.push(`${canonical} ${titleConnective(part)} ${part.clause.place}`);
    }
  }
  const surname = state.birth ?? familyText(family);
  const routeTitlePriority = ['König', 'Papst', 'Erzbischof', 'Fürstbischof', 'Bischof'];
  const promotableRoute = !state.birth && (!family || (family.kind === 'byName' && !family.particle));
  const promotedTitle = (promotableRoute ? routeTitlePriority : [])
    .map((canonical) => titles.find((title) => !title.dropped && title.group.canonical === canonical))
    .find(Boolean);
  const routeTitle = promotedTitle?.group.canonical
    ?? (!surname ? titles.find((title) => title.kind === 'route' && !title.dropped)?.group.canonical : '');
  const route = [routeTitle, state.given.join(' '), surname, state.rest]
    .filter(Boolean).join(' ');
  return { route, titles: [...new Set(out)], attached, rest: state.rest };
}

function analyze(raw, d) {
  const state = scan(cleanSpan(raw, d), d);
  if (!state.given.length) return { route: String(raw ?? '').trim(), titles: [], attached: false, rest: '' };
  return resolve(state, d);
}

// ------------------------------------------------------------------ exports

const classCache = new Map();

export function personMentionClass(name, connectorText = '', particleText = '') {
  const key = `${connectorText}\u0000${particleText}`;
  if (!classCache.has(key)) {
    const connectors = alternatives(parseNameConnectorGroups(connectorText).flat());
    const particles = alternatives(String(particleText).split(/\r?\n/).map((line) => line.split('//')[0].trim()));
    classCache.set(key, connectors && particles
      ? new RegExp(`[\\s,;]+(?:${connectors})[\\s,;]+(?:${particles})\\s+[^,;]+$`, 'iu') : null);
  }
  const designation = classCache.get(key);
  const personName = designation ? String(name).replace(designation, '') : String(name);
  return /\b(?:Rosenberg|Uissigheim)\b/iu.test(personName) ? 'person-mention-blue' : 'person-mention';
}

export function parsePersonNameTitles(markdown = '') {
  return String(markdown).split(/\r?\n/)
    .filter((line) => !line.trim().startsWith('#'))
    .flatMap((line) => line.split('//')[0].split(',').map((form) => form.trim()))
    .filter(Boolean);
}

const titleSplitters = new Map();

// Split only title forms that are listed in the project's title vocabulary.
// Longest-first matching keeps multiword titles intact.
export function splitPersonNameTitles(value, titleText = '') {
  if (!titleSplitters.has(titleText)) {
    titleSplitters.set(titleText, parsePersonNameTitles(titleText)
      .sort((left, right) => right.length - left.length)
      .map((title) => new RegExp(`(?:\\s+|,\\s*)(${escapePattern(title)})$`, 'iu')));
  }
  let name = String(value ?? '').trim();
  const titles = [];
  let changed = true;
  while (changed) {
    changed = false;
    for (const pattern of titleSplitters.get(titleText)) {
      const match = name.match(pattern);
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

export function personRouteName(name, titleText = '', connectorText = '', particleText = '', namesText = '', byNamesText = '', places = []) {
  return analyze(name, dictionaryFor(titleText, connectorText, particleText, namesText, byNamesText, places)).route;
}

function titlesBefore(text, end, d) {
  if (!d.alt.title) return '';
  d.leadingTitlesPattern ??= new RegExp(`${LETTER_BEFORE}(?:(?:${d.alt.title})${LETTER_AFTER}(?:\\s+(?:zu|zum|an|of|von|vom)\\s+(?:${d.alt.place})${LETTER_AFTER})?\\s+)+$`, 'iu');
  return d.leadingTitlesPattern.exec(text.slice(Math.max(0, end - 120), end))?.[0] ?? '';
}

export function coordinatedByNameMatches(text, titleText = '', connectorText = '', particleText = '', namesText = '', byNamesText = '', places = []) {
  const d = dictionaryFor(titleText, connectorText, particleText, namesText, byNamesText, places);
  if (!d.alt.given || !d.alt.byName || !d.alt.place) return [];
  d.coordinatedSource ??= composeCoordinatedSource(d);
  d.contextSource ??= `(?<byName>${d.alt.byName})\\s+(?<particle>${d.alt.particle})\\s+(?<place>${d.alt.place})`;
  const value = String(text);
  const contextPattern = new RegExp(d.contextSource, 'giu');
  const splitGiven = (list) => list.split(/\s*,\s*(?:(?:and|und)\s+)?|\s+(?:and|und)\s+/iu).map((name) => name.trim());
  const matches = [];
  for (const match of value.matchAll(new RegExp(d.coordinatedSource, 'giu'))) {
    const { givenList, sharedTitle = '' } = match.groups;
    let surnameText = match.groups.surname;
    if (match.groups.byName && !match.groups.byNameParticle) {
      const prior = [...value.slice(0, match.index).matchAll(contextPattern)].at(-1);
      if (prior && d.byName.get(lower(prior.groups.byName)) === d.byName.get(lower(match.groups.byName))) {
        surnameText += ` ${prior.groups.particle} ${prior.groups.place}`;
      }
    }
    const givenNames = splitGiven(givenList);
    const shared = sharedTitle ? `, ${sharedTitle}` : '';
    const lead = titlesBefore(value, match.index, d);
    const last = analyze(`${givenNames.at(-1)} ${surnameText}${shared}`, d);
    // A realm or office title before the first name keeps that person apart from the shared surname.
    if (lead && !last.attached && d.alt.routeTitle && new RegExp(`(?:${d.alt.routeTitle})${LETTER_AFTER}`, 'iu').test(lead)) continue;
    const members = givenNames.map((given, index) => {
      const leading = index === 0 ? lead : '';
      if (index === givenNames.length - 1 && !leading) return { route: last.route, titles: last.titles };
      const own = last.attached ? given : `${given} ${surnameText}${shared}`;
      const { route, titles } = analyze(`${leading}${own}`, d);
      return { route, titles };
    });
    const givenListStart = match.index + match[0].indexOf(givenList);
    const givenListEnd = givenListStart + givenList.length;
    matches.push({
      text: match[0],
      start: match.index,
      end: match.index + match[0].length,
      givenList,
      givenListEnd,
      brothersAfterList: /\bbrothers\b/iu.test(match[0].slice(givenList.length + (givenListStart - match.index))),
      givenNames,
      surnameText,
      surnameSurface: match.groups.surname,
      titles: sharedTitle ? analyze(`Hans von Xx${shared}`, d).titles : [],
      residenceSurface: /^(?:zu|zum)\s/iu.test(sharedTitle) ? sharedTitle : '',
      routes: members.map((member) => member.route),
      members,
    });
  }
  return matches;
}

export function coordinatedByNameRouteNames(...args) {
  return coordinatedByNameMatches(...args).flatMap((match) => match.routes);
}

// The span regex is looser than the scanner (for example it cannot test capitalization),
// so the span is shortened until the scanner understands all of it.
function fitSpan(raw, d) {
  let text = raw.replace(/\s+$/u, '');
  let analysis = analyze(text, d);
  while (analysis.rest) {
    const shorter = text.replace(/[\s,;]*\S+\s*$/u, '');
    if (!shorter.trim() || shorter === text) return { text: raw.replace(/\s+$/u, ''), analysis: analyze(raw, d) };
    text = shorter;
    analysis = analyze(text, d);
  }
  return { text, analysis };
}

export function findPersonNameMentions(text, titleText = '', connectorText = '', particleText = '', namesText = '', byNamesText = '', places = [], sourcePattern = null, personPatterns = []) {
  const value = String(text);
  const d = dictionaryFor(titleText, connectorText, particleText, namesText, byNamesText, places);
  const coordinated = coordinatedByNameMatches(value, titleText, connectorText, particleText, namesText, byNamesText, places);
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
      const fitted = fitSpan(match[0], d);
      const end = start + fitted.text.length;
      if (coordinated.some((group) => group.start < end && start < group.end)) continue;
      if (explicitIds.some(([idStart, idEnd]) => idStart < end && start < idEnd)) continue;
      if (singles.some((item) => item.start <= start && end <= item.end)) continue;
      const possessive = /^[’']s(?![\p{L}])/u.exec(value.slice(end))?.[0] ?? '';
      const { route, titles } = possessive ? analyze(`${fitted.text}${possessive}`, d) : fitted.analysis;
      singles.push({ kind: candidate.kind, text: fitted.text, start, end, route, titles, people: candidate.people });
    }
    if (lastIndex !== undefined) pattern.lastIndex = lastIndex;
  }
  return { coordinated, singles };
}
