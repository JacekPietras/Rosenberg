const PREFERENCES_KEY = 'rosenberg-viewer-preferences';
const VALID_DISPLAY_MODES = new Set(['english', 'original']);

function normalizeDisplayMode(value) {
  if (VALID_DISPLAY_MODES.has(value)) return value;
  // Migrate preferences from the previous three-state control.
  return value === 'both' || value === 'german' || value === 'latin' ? 'original' : 'english';
}

function loadPreferences() {
  try {
    const preferences = JSON.parse(localStorage.getItem(PREFERENCES_KEY) || '{}');
    return {
      active: typeof preferences.active === 'string' ? preferences.active : null,
      place: typeof preferences.place === 'string' ? preferences.place : null,
      person: typeof preferences.person === 'string' ? preferences.person : null,
      letter: typeof preferences.letter === 'string' ? preferences.letter : null,
      letterLabels: Array.isArray(preferences.letterLabels) ? preferences.letterLabels : [],
      hiddenLetterLabels: Array.isArray(preferences.hiddenLetterLabels) ? preferences.hiddenLetterLabels : null,
      sealNames: Array.isArray(preferences.sealNames) ? preferences.sealNames : [],
      sealType: ['contrepalle', 'swans', 'helm', 'full', 'unknown'].includes(preferences.sealType) ? preferences.sealType : null,
      language: normalizeDisplayMode(preferences.language),
      showFacts: preferences.showFacts !== false,
      darkMode: preferences.darkMode !== false,
    };
  } catch {
    return { active: null, place: null, person: null, letter: null, letterLabels: [], hiddenLetterLabels: null, sealNames: [], sealType: null, language: 'english', showFacts: true, darkMode: true };
  }
}

function savePreferences() {
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ active: state.active, place: state.place, person: state.person, letter: state.letter, letterLabels: state.letterLabels, hiddenLetterLabels: state.hiddenLetterLabels, sealNames: state.sealNames, sealType: state.sealType, language: state.language, showFacts: state.showFacts, darkMode: state.darkMode }));
  } catch {
    // Preferences are optional; rendering should continue if storage is unavailable.
  }
}

const preferences = loadPreferences();
const state = { manifest: null, active: preferences.active, place: preferences.place, person: preferences.person, letter: preferences.letter, letterSource: null, navigationLetter: null, navigationLetterSource: null, letterLabels: preferences.letterLabels, hiddenLetterLabels: preferences.hiddenLetterLabels, sealNames: preferences.sealNames, sealType: preferences.sealType, language: preferences.language, darkMode: preferences.darkMode, documents: new Map(), people: [], personRecords: [], persons: [], places: [], calibrationCities: [], personPattern: null, placePattern: null, snapshot: '', yearHighlightCleanup: null, sealHighlightCleanup: null, sealMarkerCleanup: null, lastRenderedLettersYear: null };
const GREY_LETTER_LABELS = new Set(['hessen', 'schenk', 'mönch']);
const MISSING_LETTER_LABEL = 'missing';
let leafletMap = null;
let mapMode = '1378';

function hasSource(source) {
  if (Array.isArray(source)) return source.some(hasSource);
  return typeof source === 'string' ? source.trim().length > 0 : source !== null && source !== undefined;
}

function letterHasMissingSourceOrUrl(path) {
  return (state.documents.get(path)?.entries || []).some((entry) => !hasSource(entry.source) || !hasSource(entry.url));
}

function clearScreenCaches() {
  state.letter = state.navigationLetter;
  state.letterSource = state.navigationLetterSource;
  state.letterLabels = [];
  state.hiddenLetterLabels = [...GREY_LETTER_LABELS];
  state.sealNames = [];
  state.sealType = null;
  state.lastRenderedLettersYear = null;
}

const $ = (selector) => document.querySelector(selector);
const REFRESH_INTERVAL = 30000;

const navigation = new URLSearchParams(location.search);
if (navigation.get('document') || navigation.get('tab') || navigation.get('letter')) { state.place = null; state.person = null; }
if (navigation.get('tab') === 'letters') state.active = 'letters';
if (navigation.get('tab') === 'books') state.active = 'books';
if (navigation.get('tab') === 'tree') state.active = 'tree';
if (navigation.get('tab') === 'map') state.active = 'map';
if (navigation.get('document')) state.active = navigation.get('document');
if (navigation.get('letter')) {
  state.letter = navigation.get('letter');
  state.navigationLetter = state.letter;
}
if (navigation.get('source')) {
  state.letterSource = navigation.get('source');
  state.navigationLetterSource = state.letterSource;
}
if (navigation.get('place')) { state.place = navigation.get('place'); state.person = null; }
if (navigation.get('person')) { state.person = navigation.get('person'); state.place = null; }
const requestedScreen = navigation.get('tab') || navigation.get('document');
if (requestedScreen && requestedScreen !== preferences.active) clearScreenCaches();

function applyTheme() {
  document.documentElement.dataset.theme = state.darkMode ? 'dark' : 'light';
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', state.darkMode ? '#0d0f11' : '#f5f7fa');
  const themeToggle = $('#theme-toggle');
  if (themeToggle) {
    themeToggle.setAttribute('aria-pressed', String(state.darkMode));
    themeToggle.setAttribute('aria-label', state.darkMode ? 'Switch to light mode' : 'Switch to dark mode');
    themeToggle.setAttribute('title', state.darkMode ? 'Switch to light mode' : 'Switch to dark mode');
  }
}

function updateLanguageControl() {
  const languageToggle = $('#language-toggle');
  if (!languageToggle) return;
  const label = state.language === 'original' ? 'English with original text' : 'English only';
  languageToggle.setAttribute('aria-label', `Language: ${label}`);
  languageToggle.setAttribute('title', `Language: ${label}. Click to change`);
}

function updateFactsControl() {
  const factsToggle = $('#facts-toggle');
  if (!factsToggle) return;
  const label = state.showFacts ? 'Hide facts' : 'Show facts';
  factsToggle.setAttribute('aria-label', label);
  factsToggle.setAttribute('title', label);
  factsToggle.setAttribute('aria-pressed', String(state.showFacts));
}

if (location.hash.startsWith('#year-')) history.replaceState(null, '', `${location.pathname}${location.search}`);

function applyMermaidTheme() {
  if (typeof mermaid === 'undefined') return;
  mermaid.initialize({ startOnLoad: false, theme: state.darkMode ? 'dark' : 'default', themeVariables: state.darkMode ? { background: '#11161c', primaryColor: '#1a1e23', primaryTextColor: '#e8edf2', primaryBorderColor: '#526274', lineColor: '#8eb7ff', secondaryColor: '#15181c', tertiaryColor: '#1b2c47' } : {} });
}

applyTheme();
applyMermaidTheme();

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}

function linkedMarkup(value = '', linkEntities = true) {
  if (!linkEntities) return String(value);
  const tokens = [];
  const token = (markup) => { const key = `\u0000${tokens.length}\u0000`; tokens.push(markup); return key; };
  let text = String(value);
  for (const { pattern, people } of state.personPattern || []) text = text.replace(pattern, (match) => {
    const normalizedMatch = match.replace(/\s*\([^)]*\)(?=\s(?:von|v\.|de|of)\s)/giu, '');
    const person = people.find((item) => item.names.some((name) => name.toLocaleLowerCase() === match.toLocaleLowerCase() || name.toLocaleLowerCase() === normalizedMatch.toLocaleLowerCase()));
    if (!person) return match;
    const query = encodeURIComponent(person.name);
    return token(`<a class="person-link" href="?person=${query}">${match}</a>`);
  });
  if (state.placePattern) text = text.replace(state.placePattern, (match) => {
    const place = state.places.find((item) => item.names.some((name) => name.toLocaleLowerCase() === match.toLocaleLowerCase()));
    if (!place) return match;
    const query = encodeURIComponent(place.name);
    return token(`<a class="place-link" href="?place=${query}">${match}</a>`);
  });
  return text.replace(/\u0000(\d+)\u0000/g, (match, index) => tokens[Number(index)] ?? match);
}

function inlineMarkup(value = '', linkEntities = true) {
  const tokens = [];
  const token = (markup) => { const key = `\u0000${tokens.length}\u0000`; tokens.push(markup); return key; };
  let text = escapeHtml(value).replace(/\[\[([^\]]+)\]\]\((https?:\/\/[^)]+)\)/g, (_, label, url) => token(`<a href="${url}" target="_blank" rel="noreferrer">${linkedMarkup(label, linkEntities)}</a>`));
  text = linkedMarkup(text, linkEntities).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  return text.replace(/\u0000(\d+)\u0000/g, (match, index) => tokens[Number(index)] ?? match);
}

function parsePlaces(json) {
  const places = JSON.parse(json);
  if (!Array.isArray(places)) throw new Error('data/places.json must contain an array');
  return places.map((place) => {
    const variations = Array.isArray(place.variations) ? place.variations.filter((name) => typeof name === 'string' && name.trim()) : [];
    return { ...place, name: variations[0], names: [...new Set(variations)] };
  });
}

function buildPlacePattern(places) {
  const names = [...new Set(places.flatMap((place) => place.names))].sort((left, right) => right.length - left.length).map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return names.length ? new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.join('|')})(?![\\p{L}\\p{N}])`, 'giu') : null;
}

function parsePeople(markdown, namesMarkdown, places) {
  const namesByCanonical = new Map(String(namesMarkdown).split('\n').map((line) => line.replace(/\/\/.*$/, '').trim()).filter(Boolean).map((line) => {
    const names = line.split(',').map((name) => name.trim()).filter(Boolean);
    return [names[0].toLocaleLowerCase(), [...new Set(names)]];
  }));
  const allNameVariants = [...new Set([...namesByCanonical.values()].flat())].sort((left, right) => right.length - left.length);
  let peopleLines;
  try {
    const parsed = JSON.parse(markdown);
    peopleLines = Array.isArray(parsed)
      ? parsed.map((person) => typeof person === 'string' ? person : person?.name).filter(Boolean)
      : null;
  } catch {
    peopleLines = null;
  }
  if (!peopleLines) peopleLines = String(markdown).split('\n');
  return peopleLines.map((line) => String(line).replace(/\/\/.*$/, '').trim()).filter(Boolean).map((line) => {
    const separatorMatch = [...line.matchAll(/ (?:von|v\.|de|of) /gi)].pop();
    const name = separatorMatch ? line.slice(0, separatorMatch.index) : line;
    const placeName = separatorMatch ? line.slice(separatorMatch.index + separatorMatch[0].length) : '';
    const baseName = allNameVariants.find((candidate) => name.toLocaleLowerCase() === candidate.toLocaleLowerCase() || name.toLocaleLowerCase().startsWith(`${candidate.toLocaleLowerCase()} `));
    const nameAddition = baseName ? name.slice(baseName.length) : '';
    const nameAdditions = /^ d\. ?Ä\.$/i.test(nameAddition)
      ? [' d. Ä.', ' d.Ä.']
      : nameAddition
        ? [nameAddition]
        : ['', ' d. Ä.', ' d.Ä.', ' the Elder', ' der Ältere'];
    const nameVariants = (namesByCanonical.get(baseName?.toLocaleLowerCase()) || [baseName || name]).flatMap((nameVariant) => nameAdditions.map((addition) => `${nameVariant}${addition}`));
    const place = places.find((item) => item.names.some((candidate) => placeName.toLocaleLowerCase() === candidate.toLocaleLowerCase() || placeName.toLocaleLowerCase().startsWith(`${candidate.toLocaleLowerCase()} `)));
    const placeBase = place?.names.find((candidate) => placeName.toLocaleLowerCase() === candidate.toLocaleLowerCase() || placeName.toLocaleLowerCase().startsWith(`${candidate.toLocaleLowerCase()} `));
    const fallbackPlaceBase = allNameVariants.find((candidate) => placeName.toLocaleLowerCase() === candidate.toLocaleLowerCase() || placeName.toLocaleLowerCase().startsWith(`${candidate.toLocaleLowerCase()} `));
    const placeAddition = (placeBase || fallbackPlaceBase) ? placeName.slice((placeBase || fallbackPlaceBase).length) : '';
    const placeAdditions = /^ d\. ?Ä\.$/i.test(placeAddition)
      ? [' d. Ä.', ' d.Ä.']
      : /^, (?:Knight|Ritter)$/i.test(placeAddition)
        ? [', Knight', ', Ritter']
        : placeAddition
          ? [placeAddition]
          : ['', ' d. Ä.', ' d.Ä.', ', Knight', ', Ritter', ' the Elder', ' der Ältere'];
    const placeVariants = place ? place.names.flatMap((placeVariant) => placeAdditions.map((addition) => `${placeVariant}${addition}`)) : (namesByCanonical.get((fallbackPlaceBase || placeName).toLocaleLowerCase()) || [fallbackPlaceBase || placeName]).flatMap((placeVariant) => placeAdditions.map((addition) => `${placeVariant}${addition}`));
    const names = [...new Set(nameVariants.flatMap((nameVariant) => placeVariants.flatMap((placeVariant) => ['von', 'v.', 'de', 'of'].map((connector) => `${nameVariant} ${connector} ${placeVariant}`))))];
    return { name: line, names };
  });
}

function buildPersonPattern(people) {
  const expressions = people.flatMap((person) => [...new Set(person.names)].sort((left, right) => right.length - left.length).map((name) => {
      const connector = name.match(/\s(?:von|v\.|de|of)\s/i);
      if (!connector) return { expression: name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), person };
      const left = name.slice(0, connector.index).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const right = name.slice(connector.index).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      return { expression: `${left}(?:\\s\\([^)]*\\))?${right}`, person };
    }));
  const chunks = [];
  let chunk = [];
  let length = 0;
  expressions.forEach((item) => {
    if (chunk.length && length + item.expression.length > 12000) {
      chunks.push(chunk);
      chunk = [];
      length = 0;
    }
    chunk.push(item);
    length += item.expression.length;
  });
  if (chunk.length) chunks.push(chunk);
  return chunks.map((items) => ({
    pattern: new RegExp(`(?<![\\p{L}\\p{N}])(?:${items.map((item) => item.expression).join('|')})(?![\\p{L}\\p{N}])`, 'giu'),
    people: [...new Set(items.map((item) => item.person))],
  }));
}

function markdownMarkup(value = '', linkEntities = true) {
  const lines = String(value).split('\n');
  const output = [];
  let listDepth = 0;
  let lastIndent = -1;
  let itemOpen = false;

  const closeLists = () => {
    if (itemOpen) { output.push('</li>'); itemOpen = false; }
    while (listDepth > 0) { output.push('</ul>'); listDepth -= 1; }
    lastIndent = -1;
  };

  lines.forEach((line) => {
    const match = line.match(/^(\s*)[*+-]\s+(.+)$/);
    if (!match) {
      closeLists();
      if (line.trim()) output.push(`<p>${inlineMarkup(line.trim(), linkEntities)}</p>`);
      return;
    }

    const indent = match[1].replace(/\t/g, '  ').length;
    if (!listDepth) {
      output.push('<ul class="source-list">');
      listDepth = 1;
    } else if (indent > lastIndent) {
      output.push('<ul>');
      listDepth += 1;
    } else if (indent === lastIndent) {
      if (itemOpen) output.push('</li>');
    } else {
      if (itemOpen) output.push('</li>');
      while (listDepth > 1 && indent < lastIndent) {
        output.push('</ul></li>');
        listDepth -= 1;
        lastIndent = Math.max(0, lastIndent - 2);
      }
    }
    output.push(`<li>${inlineMarkup(match[2], linkEntities)}`);
    itemOpen = true;
    lastIndent = indent;
  });

  closeLists();
  return output.join('');
}

function markdownLinks(value = '') {
  if (!Array.isArray(value)) return inlineMarkup(value);
  return value.map((item) => `<span class="source-line">${inlineMarkup(item)}</span>`).join('');
}

function letterForSource(source) {
  if (!state.manifest?.letters || !source) return null;
  const sourceValues = Array.isArray(source) ? source : [source];
  const sources = sourceValues.flatMap((value) => [value, ...String(value).split(/\s*;\s*/)])
    .filter((value, index, values) => value && values.indexOf(value) === index);
  return sources.reduce((match, citation) => match || state.manifest.letters.reduce((found, path) => {
    if (found) return found;
    const entries = state.documents.get(path)?.entries || [];
    const entryIndex = entries.findIndex((item) => Array.isArray(item.source) ? item.source.includes(citation) : item.source === citation);
    return entryIndex >= 0 ? { path, entry: entries[entryIndex], entryIndex } : null;
  }, null), null);
}

function sourceCitations(source) {
  const values = Array.isArray(source) ? source : [source];
  return values.flatMap((value) => String(value || '').split(/\s*;\s*/)).map((value) => value.trim()).filter(Boolean);
}

function entryHasSource(entry, source) {
  return sourceCitations(entry?.source).includes(String(source || '').trim());
}

function letterHasSource(path, source) {
  return (state.documents.get(path)?.entries || []).some((entry) => entryHasSource(entry, source));
}

function diagramMarkup(value = '') {
  const source = String(value).replace(/^\s*```mermaid\s*\n?/, '').replace(/\n?\s*```\s*$/, '').trim();
  return source ? `<div class="diagram mermaid">${escapeHtml(source)}</div>` : '';
}

function peopleTreeMarkup(people = []) {
  const records = Array.isArray(people) ? people.filter((person) => person && person.id && person.name) : [];
  if (!records.length) return '<div class="people-tree"><p class="status">No people found.</p></div>';

  const nodeWidth = 220;
  const nodeHeight = 72;
  const horizontalGap = 36;
  const verticalGap = 88;
  const padding = 28;
  const byId = new Map(records.map((person) => [person.id, person]));
  const groupParent = new Map(records.map((person) => [person.id, person.id]));
  const groupFor = (id) => {
    let root = groupParent.get(id);
    while (root && groupParent.get(root) !== root) root = groupParent.get(root);
    if (root) groupParent.set(id, root);
    return root;
  };
  const joinGroups = (left, right) => {
    const leftRoot = groupFor(left);
    const rightRoot = groupFor(right);
    if (leftRoot && rightRoot && leftRoot !== rightRoot) groupParent.set(rightRoot, leftRoot);
  };
  records.forEach((person) => {
    if (byId.has(person.wife)) joinGroups(person.id, person.wife);
  });
  const groupParents = new Map();
  records.forEach((person) => {
    const parentGroup = groupFor(person.id);
    (Array.isArray(person.children) ? person.children : []).forEach((childId) => {
      if (!byId.has(childId)) return;
      const childGroup = groupFor(childId);
      if (parentGroup !== childGroup) {
        if (!groupParents.has(childGroup)) groupParents.set(childGroup, new Set());
        groupParents.get(childGroup).add(parentGroup);
      }
    });
  });
  const groupDepths = new Map();
  const depthForGroup = (group, visiting = new Set()) => {
    if (groupDepths.has(group)) return groupDepths.get(group);
    if (visiting.has(group)) return 0;
    visiting.add(group);
    const parents = groupParents.get(group) || [];
    const depth = parents.size ? Math.max(...[...parents].map((parent) => depthForGroup(parent, new Set(visiting)))) + 1 : 0;
    groupDepths.set(group, depth);
    return depth;
  };
  records.forEach((person) => depthForGroup(groupFor(person.id)));
  const depths = new Map(records.map((person) => [person.id, groupDepths.get(groupFor(person.id)) || 0]));

  const layers = new Map();
  records.forEach((person) => {
    const depth = depths.get(person.id) || 0;
    if (!layers.has(depth)) layers.set(depth, []);
    layers.get(depth).push(person);
  });
  [...layers.values()].forEach((layer) => layer.sort((left, right) => left.name.localeCompare(right.name)));
  const maxDepth = Math.max(...layers.keys());
  const maxLayerSize = Math.max(...[...layers.values()].map((layer) => layer.length));
  const width = Math.max(2 * padding + nodeWidth, 2 * padding + maxLayerSize * nodeWidth + (maxLayerSize - 1) * horizontalGap);
  const height = 2 * padding + (maxDepth + 1) * nodeHeight + maxDepth * verticalGap;
  const positions = new Map();
  layers.forEach((layer, depth) => {
    const layerWidth = layer.length * nodeWidth + (layer.length - 1) * horizontalGap;
    const startX = (width - layerWidth) / 2;
    layer.forEach((person, index) => positions.set(person.id, {
      x: startX + index * (nodeWidth + horizontalGap),
      y: padding + depth * (nodeHeight + verticalGap),
    }));
  });
  const svgEscape = (value) => String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const personLines = (person) => [
    person.name,
    Array.isArray(person.titles) && person.titles.length ? person.titles.join(', ') : '',
    person.born || person.died ? `${person.born || '?'}–${person.died || '?'}` : '',
  ].filter(Boolean);
  const edges = [];
  records.forEach((person) => {
    const from = positions.get(person.id);
    if (!from) return;
    const wife = positions.get(person.wife);
    if (wife && person.id.localeCompare(person.wife) < 0) {
      const left = from.x < wife.x ? from : wife;
      const right = from.x < wife.x ? wife : from;
      edges.push(`<line class="people-tree-spouse" x1="${left.x + nodeWidth}" y1="${left.y + nodeHeight / 2}" x2="${right.x}" y2="${right.y + nodeHeight / 2}"/><text class="people-tree-edge-label" x="${(left.x + nodeWidth + right.x) / 2}" y="${left.y + nodeHeight / 2 - 8}">wife</text>`);
    }
    (Array.isArray(person.children) ? person.children : []).forEach((childId) => {
      const child = positions.get(childId);
      if (!child) return;
      edges.push(`<line class="people-tree-parent" x1="${from.x + nodeWidth / 2}" y1="${from.y + nodeHeight}" x2="${child.x + nodeWidth / 2}" y2="${child.y}"/>`);
    });
  });
  const nodes = records.map((person) => {
    const position = positions.get(person.id);
    const lines = personLines(person);
    const text = lines.map((line, index) => `<tspan class="${index ? 'people-tree-detail' : 'people-tree-name'}" x="${position.x + nodeWidth / 2}" dy="${index ? 18 : 0}">${svgEscape(line)}</tspan>`).join('');
    return `<g class="people-tree-node"><rect x="${position.x}" y="${position.y}" width="${nodeWidth}" height="${nodeHeight}" rx="8"/><text x="${position.x + nodeWidth / 2}" y="${position.y + 25}" text-anchor="middle">${text}</text></g>`;
  }).join('');
  return `<div class="people-tree"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Family tree">${edges.join('')}${nodes}</svg></div>`;
}

// Historical maps: shown as their own canvas (Leaflet CRS.Simple, plain image pixels), never
// draped as a translucent layer over the live OSM map — an earlier attempt at that drifted out of
// alignment while panning/zooming, since these hand-drawn maps aren't Mercator-georeferenced.
//
// Each map gets its own calibration, keyed by place.calibrated_x_<id>/calibrated_y_<id> (set by
// dragging a marker in that map's mode). A single global affine formula (one px-per-degree scale
// for the whole map) forced a trade-off on the 1400 map: fitting it to the towns nearest the real
// content (Stuttgart/Würzburg) drifted up to ~390px near the map's edges, while fitting it evenly
// cost those towns ~20-30px each — these maps are hand-drawn, not projected, so no single affine
// formula fits one everywhere. hrrBuildWarp fits a thin-plate spline instead once a map has 3+
// calibrated points: it passes exactly through every one and interpolates smoothly between them,
// so local and distant accuracy are no longer in tension. With fewer points it falls back to a
// plain affine fit (2 points) or a rough guess seeded from the 1400 map's original calibration,
// scaled to the new image's pixel size (0-1 points, e.g. a map nobody has calibrated yet) — just
// enough to place markers somewhere sane to start dragging from.
const HRR_MAP_NATIVE_WIDTH = 3715;
const HRR_MAP_NATIVE_HEIGHT = 3966;
const HRR_MAP_CALIBRATION_SEED = { x0: 1637.1, y0: 1961.6, lon0: 11.3322, lat0: 49.4340, pxPerDegreeLon: 182.0, pxPerDegreeLat: -302.9 };
const HRR_1400_CREDIT_HTML = 'Historical base map: <a href="https://commons.wikimedia.org/wiki/File:HRR_1400.png" target="_blank" rel="noreferrer">Das Heilige Römische Reich um 1400</a> by Ziegelbrenner, <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noreferrer">CC BY-SA 3.0</a>, via Wikimedia Commons. Place positions are approximate.';
const HRR_1378_CREDIT_HTML = 'Historical base map: "Germany at the death of Emperor Charles IV, 1378," revised by Karl Wolf, from H.F. Helmolt\'s <a href="https://pl.wikipedia.org/wiki/Plik:Germany_1378_map.jpg" target="_blank" rel="noreferrer">History of the World</a>, Vol. VII (Dodd Mead, 1902). Public domain in the United States. Place positions are approximate.';
const HRR_MAPS = [
  { id: '1378', label: '1378', image: 'assets/Germany_1378_map.jpg', width: 3215, height: 2514, credit: HRR_1378_CREDIT_HTML },
  { id: '1400', label: '1400', image: 'assets/Germany_1400_map.jpg', width: HRR_MAP_NATIVE_WIDTH, height: HRR_MAP_NATIVE_HEIGHT, credit: HRR_1400_CREDIT_HTML },
];
const HRR_MAPS_BY_ID = new Map(HRR_MAPS.map((map) => [map.id, map]));

function hrrCalibrationKeys(mapDef) {
  return { x: `calibrated_x_${mapDef.id}`, y: `calibrated_y_${mapDef.id}` };
}

// Rough starting guess for a map with fewer than 2 calibrated points: assumes it covers roughly
// the same real-world extent as the original 1400-map calibration, uniformly rescaled to this
// map's own pixel dimensions. Just enough to place markers somewhere sane to drag into place.
function hrrGuessPixelForLatLon(lat, lon, mapDef) {
  const scaleX = mapDef.width / HRR_MAP_NATIVE_WIDTH;
  const scaleY = mapDef.height / HRR_MAP_NATIVE_HEIGHT;
  const { x0, y0, lon0, lat0, pxPerDegreeLon, pxPerDegreeLat } = HRR_MAP_CALIBRATION_SEED;
  return { x: (x0 + (lon - lon0) * pxPerDegreeLon) * scaleX, y: (y0 + (lat - lat0) * pxPerDegreeLat) * scaleY };
}

// Only used to carry the viewport across a live<->historical mode switch (see renderMapLayer):
// an approximation is fine there since it's just "stay looking at roughly the same area", not a
// marker placement. There's no inverse of the TPS/2-point warps (only ever fit lat/lon -> pixel).
function hrrGuessLatLonForPixel(x, y, mapDef) {
  const scaleX = mapDef.width / HRR_MAP_NATIVE_WIDTH;
  const scaleY = mapDef.height / HRR_MAP_NATIVE_HEIGHT;
  const { x0, y0, lon0, lat0, pxPerDegreeLon, pxPerDegreeLat } = HRR_MAP_CALIBRATION_SEED;
  return { lat: lat0 + (y / scaleY - y0) / pxPerDegreeLat, lon: lon0 + (x / scaleX - x0) / pxPerDegreeLon };
}

// Ordinary least-squares line y = intercept + slope*x (exact fit when there are only 2 points).
function hrrLinearFit(xs, ys) {
  const n = xs.length;
  const meanX = xs.reduce((a, b) => a + b, 0) / n;
  const meanY = ys.reduce((a, b) => a + b, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) { num += (xs[i] - meanX) * (ys[i] - meanY); den += (xs[i] - meanX) ** 2; }
  const slope = den === 0 ? 0 : num / den;
  return { slope, intercept: meanY - slope * meanX };
}

// Solves the (n+3)x(n+3) linear system via Gaussian elimination with partial pivoting.
function hrrSolveLinearSystem(matrix, rhs) {
  const n = rhs.length;
  const rows = matrix.map((row, i) => [...row, rhs[i]]);
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) if (Math.abs(rows[r][col]) > Math.abs(rows[pivot][col])) pivot = r;
    [rows[col], rows[pivot]] = [rows[pivot], rows[col]];
    const pivotValue = rows[col][col];
    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const factor = rows[r][col] / pivotValue;
      for (let c = col; c <= n; c++) rows[r][c] -= factor * rows[col][c];
    }
  }
  return rows.map((row, i) => row[n] / row[i]);
}

// Thin-plate-spline kernel: U(r) = r^2*ln(r), the unique radial basis that minimizes bending
// energy for a 2D interpolating surface. Fits values (scalars) at 2D control points exactly.
function hrrFitTps(points, values) {
  const n = points.length;
  const size = n + 3;
  const matrix = Array.from({ length: size }, () => new Array(size).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const r = Math.hypot(points[i].x - points[j].x, points[i].y - points[j].y);
      matrix[i][j] = r <= 1e-9 ? 0 : r * r * Math.log(r);
    }
    matrix[i][n] = 1; matrix[i][n + 1] = points[i].x; matrix[i][n + 2] = points[i].y;
    matrix[n][i] = 1; matrix[n + 1][i] = points[i].x; matrix[n + 2][i] = points[i].y;
  }
  const solution = hrrSolveLinearSystem(matrix, [...values, 0, 0, 0]);
  const weights = solution.slice(0, n);
  const [a0, a1, a2] = solution.slice(n);
  return (x, y) => {
    let sum = a0 + a1 * x + a2 * y;
    for (let i = 0; i < n; i++) {
      const r = Math.hypot(x - points[i].x, y - points[i].y);
      if (r > 1e-9) sum += weights[i] * r * r * Math.log(r);
    }
    return sum;
  };
}

// Builds the lat/lon -> image-pixel warp for one historical map, from every place with a saved
// calibration point for that map. See the fallback chain explained above HRR_MAPS.
function hrrBuildWarp(places, mapDef) {
  const { x: keyX, y: keyY } = hrrCalibrationKeys(mapDef);
  const controls = places
    .filter((place) => Number.isFinite(place[keyX]) && Number.isFinite(place[keyY]))
    .map((place) => ({ lat: place.lat, lon: place.lon, x: place[keyX], y: place[keyY] }));
  if (controls.length >= 3) {
    const realCoords = controls.map((control) => ({ x: control.lon, y: control.lat }));
    const pixelX = hrrFitTps(realCoords, controls.map((control) => control.x));
    const pixelY = hrrFitTps(realCoords, controls.map((control) => control.y));
    return { pixelForLatLon: (lat, lon) => ({ x: pixelX(lon, lat), y: pixelY(lon, lat) }) };
  }
  if (controls.length === 2) {
    const fitX = hrrLinearFit(controls.map((control) => control.lon), controls.map((control) => control.x));
    const fitY = hrrLinearFit(controls.map((control) => control.lat), controls.map((control) => control.y));
    return { pixelForLatLon: (lat, lon) => ({ x: fitX.intercept + fitX.slope * lon, y: fitY.intercept + fitY.slope * lat }) };
  }
  return { pixelForLatLon: (lat, lon) => hrrGuessPixelForLatLon(lat, lon, mapDef) };
}

// Solves the 2x2 linear system [[a,b],[c,d]] * [x,y]^T = [e,f]^T.
function hrrSolve2x2(a, b, c, d, e, f) {
  const det = a * d - b * c;
  if (Math.abs(det) < 1e-9) return null;
  return { x: (e * d - b * f) / det, y: (a * f - e * c) / det };
}

// Inverts `pixelForLatLon` at (targetX, targetY) via Newton's method with a numeric Jacobian,
// starting from the rough scaled-seed guess and refining. This makes the inverse consistent with
// THIS SPECIFIC forward warp by construction — an earlier version fit a separate reverse TPS
// (from the same control points, but independently), which only approximately agreed with the
// forward warp and compounded error on every live<->historical round trip, drifting the viewport
// out on repeated mode switches. Newton's method against the actual forward function can't drift:
// inverting then re-applying the same forward warp returns (approximately) the original point.
function hrrInvertPixelForLatLon(pixelForLatLon, targetX, targetY, mapDef) {
  const seed = hrrGuessLatLonForPixel(targetX, targetY, mapDef);
  let lat = seed.lat, lon = seed.lon;
  const eps = 0.02;
  for (let iter = 0; iter < 25; iter++) {
    const p = pixelForLatLon(lat, lon);
    const rx = p.x - targetX, ry = p.y - targetY;
    if (Math.abs(rx) < 0.05 && Math.abs(ry) < 0.05) break;
    const pLat = pixelForLatLon(lat + eps, lon);
    const pLon = pixelForLatLon(lat, lon + eps);
    const delta = hrrSolve2x2((pLat.x - p.x) / eps, (pLon.x - p.x) / eps, (pLat.y - p.y) / eps, (pLon.y - p.y) / eps, -rx, -ry);
    if (!delta) break;
    lat += delta.x; lon += delta.y;
  }
  return { lat, lon };
}

// Inverse of hrrBuildWarp (image pixel -> lat/lon) — only used to carry the viewport across a
// mode switch (see hrrViewCornersToLatLon below), where this is fine since it's just "stay
// looking at roughly the same area", not a marker placement.
function hrrBuildInverseWarp(places, mapDef) {
  const warp = hrrBuildWarp(places, mapDef);
  return { latLonForPixel: (x, y) => hrrInvertPixelForLatLon(warp.pixelForLatLon, x, y, mapDef) };
}

// Editing (dragging calibration points, saving to docs/assets/calibration-cities.json) only
// works against the local dev server (docs/serve.py) that /api/save-document writes through; the
// published GitHub Pages viewer is read-only and has nowhere to persist a drag to. Real places
// (data/places.json, the actual letter/genealogy content) are never draggable — only the
// dedicated calibration-city reference points are, and only when BOTH flags below are true.
// MAP_CALIBRATION_EDITABLE also gates whether the reference points are shown at all: they're a
// working aid for calibrating the map, not something a regular viewer needs to see, so leave it
// false to hide them entirely; flip it to true to show them and re-open dragging for editing.
const MAP_EDITABLE = !location.hostname.endsWith('github.io');
const MAP_CALIBRATION_EDITABLE = false;
let calibrationCitiesSaveQueue = Promise.resolve();

function calibrationCitiesForSave() {
  return state.calibrationCities.map((city) => {
    const raw = { variations: city.variations, lat: city.lat, lon: city.lon };
    for (const mapDef of HRR_MAPS) {
      const { x: keyX, y: keyY } = hrrCalibrationKeys(mapDef);
      if (Number.isFinite(city[keyX])) raw[keyX] = city[keyX];
      if (Number.isFinite(city[keyY])) raw[keyY] = city[keyY];
    }
    return raw;
  });
}

function saveCalibrationCities() {
  const operation = calibrationCitiesSaveQueue.then(async () => {
    const status = $('#map-save-status');
    try {
      if (status) { status.textContent = 'Saving…'; status.classList.remove('error'); }
      const response = await fetch('/api/save-document', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: 'docs/assets/calibration-cities.json', document: calibrationCitiesForSave() }) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Save failed (${response.status})`);
      if (status) status.textContent = 'Saved calibration point.';
    } catch (error) {
      if (status) { status.textContent = error.message; status.classList.add('error'); }
    }
  });
  calibrationCitiesSaveQueue = operation.catch(() => {});
  return operation;
}

function renderMapPage() {
  const buttons = [{ id: 'live', label: 'Current' }, ...HRR_MAPS.map((map) => ({ id: map.id, label: map.label }))]
    .map(({ id, label }) => `<button type="button" class="map-mode-button" data-map-mode="${id}" aria-pressed="${mapMode === id}">${escapeHtml(label)}</button>`)
    .join('');
  const credit = HRR_MAPS_BY_ID.get(mapMode)?.credit || '';
  return `<div class="map-wrap"><div id="map-container" class="map-container" role="application" aria-label="Map of places"></div><div id="map-mode-switch" class="map-mode-switch" role="group" aria-label="Map version">${buttons}</div><span id="map-save-status" class="map-save-status status" aria-live="polite"></span></div><p id="map-credit" class="map-credit">${credit}</p>`;
}

// None of the modes (live lat/lon, or any historical map's own image-pixel CRS.Simple space)
// share a coordinate system with each other, so "same zoom level" isn't a portable number between
// any pair of them. Instead we carry the *viewport bounds* across a mode switch by routing them
// through real-world lat/lon as a common intermediate — out of the previous mode via its inverse
// warp (identity if it was already "live"), back into the new mode via its forward warp (also
// identity for "live") — and let fitBounds pick the equivalent zoom in the new mode. This works
// for every mode pair uniformly, including switching directly between two historical maps.
function hrrViewCornersToLatLon(mode, bounds, calibrationCities) {
  const corners = [bounds.getSouthWest(), bounds.getNorthEast(), bounds.getNorthWest(), bounds.getSouthEast()];
  if (mode === 'live') return corners.map(({ lat, lng }) => ({ lat, lon: lng }));
  const mapDef = HRR_MAPS_BY_ID.get(mode);
  const inverse = hrrBuildInverseWarp(calibrationCities, mapDef);
  return corners.map(({ lat, lng }) => inverse.latLonForPixel(lng, mapDef.height - lat));
}

function hrrLatLonCornersToView(corners, mode, calibrationCities) {
  if (mode === 'live') {
    const lats = corners.map((p) => p.lat), lons = corners.map((p) => p.lon);
    return [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
  }
  const mapDef = HRR_MAPS_BY_ID.get(mode);
  const warp = hrrBuildWarp(calibrationCities, mapDef);
  const pixels = corners.map(({ lat, lon }) => warp.pixelForLatLon(lat, lon));
  const xs = pixels.map((p) => p.x), ys = pixels.map((p) => p.y);
  return [[mapDef.height - Math.max(...ys), Math.min(...xs)], [mapDef.height - Math.min(...ys), Math.max(...xs)]];
}

// Small circular "point" marker (not the usual pin) for calibration reference cities, so they
// read as reference data rather than genealogy content. Uses a real L.marker (not L.circleMarker)
// specifically so Leaflet's built-in drag support is available when MAP_CALIBRATION_EDITABLE
// flips on — Leaflet's Path-based circle markers can't be made draggable.
const HRR_CALIBRATION_POINT_ICON = L.divIcon({ className: 'calibration-point-icon', iconSize: [10, 10] });

function renderMapLayer(container, places, calibrationCities, previousView) {
  if (leafletMap) { leafletMap.remove(); leafletMap = null; }
  const carriedCorners = previousView ? hrrViewCornersToLatLon(previousView.mode, previousView.bounds, calibrationCities) : null;

  const mapDef = HRR_MAPS_BY_ID.get(mapMode);
  if (mapDef) {
    const bounds = [[0, 0], [mapDef.height, mapDef.width]];
    leafletMap = L.map(container, { crs: L.CRS.Simple, scrollWheelZoom: true, minZoom: -10, maxZoom: 10, zoomSnap: 0 });
    L.imageOverlay(mapDef.image, bounds).addTo(leafletMap);
    leafletMap.setMaxBounds(L.latLngBounds(bounds).pad(0.5));
    const warp = hrrBuildWarp(calibrationCities, mapDef);
    places.forEach((place) => {
      const { x, y } = warp.pixelForLatLon(place.lat, place.lon);
      const marker = L.marker([mapDef.height - y, x]).addTo(leafletMap);
      const query = encodeURIComponent(place.name);
      marker.bindPopup(`<a class="place-link" href="?place=${query}">${escapeHtml(place.name)}</a>`);
    });
    if (MAP_CALIBRATION_EDITABLE) {
      const { x: keyX, y: keyY } = hrrCalibrationKeys(mapDef);
      const pointsEditable = MAP_EDITABLE && MAP_CALIBRATION_EDITABLE;
      calibrationCities.forEach((city) => {
        const { x, y } = warp.pixelForLatLon(city.lat, city.lon);
        const marker = L.marker([mapDef.height - y, x], { icon: HRR_CALIBRATION_POINT_ICON, draggable: pointsEditable }).addTo(leafletMap);
        marker.bindPopup(escapeHtml(city.name));
        if (pointsEditable) {
          marker.on('dragend', () => {
            const { lat, lng } = marker.getLatLng();
            city[keyX] = lng;
            city[keyY] = mapDef.height - lat;
            saveCalibrationCities();
          });
        }
      });
    }
    leafletMap.fitBounds(carriedCorners ? hrrLatLonCornersToView(carriedCorners, mapMode, calibrationCities) : bounds);
    return;
  }

  leafletMap = L.map(container, { scrollWheelZoom: true });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors',
    maxZoom: 18,
  }).addTo(leafletMap);
  const markers = places.map((place) => {
    const marker = L.marker([place.lat, place.lon]).addTo(leafletMap);
    const query = encodeURIComponent(place.name);
    marker.bindPopup(`<a class="place-link" href="?place=${query}">${escapeHtml(place.name)}</a>`);
    return marker;
  });
  leafletMap.fitBounds(carriedCorners ? hrrLatLonCornersToView(carriedCorners, 'live', calibrationCities) : L.featureGroup(markers).getBounds(), carriedCorners ? undefined : { padding: [40, 40] });
}

function setupMap() {
  const container = $('#map-container');
  const places = state.places.filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lon));
  const calibrationCities = state.calibrationCities.filter((city) => Number.isFinite(city.lat) && Number.isFinite(city.lon));
  const modeSwitch = $('#map-mode-switch');
  modeSwitch?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-map-mode]');
    if (!button || button.dataset.mapMode === mapMode) return;
    const previousView = leafletMap ? { mode: mapMode, bounds: leafletMap.getBounds() } : null;
    mapMode = button.dataset.mapMode;
    modeSwitch.querySelectorAll('[data-map-mode]').forEach((other) => other.setAttribute('aria-pressed', String(other.dataset.mapMode === mapMode)));
    const credit = $('#map-credit');
    if (credit) credit.innerHTML = HRR_MAPS_BY_ID.get(mapMode)?.credit || '';
    if (container && places.length) renderMapLayer(container, places, calibrationCities, previousView);
  });
  if (!container || typeof L === 'undefined' || !places.length) return;
  renderMapLayer(container, places, calibrationCities);
}

function sealAnnotationMarkup(seals = []) {
  if (!Array.isArray(seals)) return '';
  return seals.map((seal) => {
    const x = Number(seal?.position?.split?.(',')?.[0]);
    const y = Number(seal?.position?.split?.(',')?.[1]);
    const size = Number(seal?.size);
    const width = Number.isFinite(Number(seal?.width)) ? Math.max(0, Math.min(1, Number(seal.width))) : 0;
    const wideningRotation = Number.isFinite(Number(seal?.wideningRotation)) ? Number(seal.wideningRotation) : 0;
    const rotation = Number.isFinite(Number(seal?.rotation)) ? Number(seal.rotation) : 0;
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(size) || x < 0 || x > 1 || y < 0 || y > 1 || size <= 0 || !String(seal?.person || '').trim()) return '';
    const person = escapeHtml(seal.person);
    return `<span class="seal-marker" data-size="${size}" data-width="${width}" data-widening-rotation="${wideningRotation}" data-rotation="${rotation}" style="left:${x * 100}%;top:${y * 100}%" role="img" aria-label="Seal of ${person}" title="${person}"><span class="seal-marker-label">${person}</span></span>`;
  }).join('');
}

function localImageName(fileName) {
  if (!/^https?:\/\//i.test(fileName)) return fileName;
  try {
    const url = new URL(fileName);
    const original = url.searchParams.get('originalBilddatei');
    return (original || url.pathname).split('/').filter(Boolean).pop() || '';
  } catch {
    return '';
  }
}

function imageRootForPath(path) {
  const match = String(path || '').match(/^data\/(books|letters|notes)\//);
  return match ? `data/${match[1]}` : 'data';
}

function imageMarkup(value = '', legacySeals = [], context = {}) {
  const imageNodes = Array.isArray(value) ? value : [value];
  const pathParts = location.pathname.split('/').filter(Boolean);
  const repository = pathParts[0];
  const owner = location.hostname.split('.')[0];
  const images = imageNodes.map((node, imageIndex) => {
    if (node && typeof node === 'object' && node.deleted === 'true') return '';
    const file = typeof node === 'object' && node !== null ? node.src : node;
    const seals = typeof node === 'object' && node !== null ? node.seals : imageIndex === 0 ? legacySeals : [];
    const fileName = String(file || '').trim();
    if (!fileName) return '';
    let source;
    let fallback = '';
    if (/^https?:\/\//i.test(fileName)) {
      fallback = fileName;
      const localName = localImageName(fileName);
      const isImage = /\.(?:svg|png|jpe?g|gif|webp)$/i.test(localName);
      if (!isImage) return '';
      const imagePath = `${imageRootForPath(context.path)}/img/${localName}`;
      const encodedPath = imagePath.split('/').map((part) => encodeURIComponent(part)).join('/');
      source = location.hostname.endsWith('github.io')
        ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${encodedPath}`
        : `../${encodedPath}`;
    } else {
      const parts = fileName.split('/');
      if (fileName.includes('\\') || parts.some((part) => !part || part === '.' || part === '..') || !/\.(?:svg|png|jpe?g|gif|webp)$/i.test(fileName)) return '';
      const imagePath = `${imageRootForPath(context.path)}/${fileName}`;
      const encodedPath = imagePath.split('/').map((part) => encodeURIComponent(part)).join('/');
      source = location.hostname.endsWith('github.io')
        ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${encodedPath}`
        : `../${encodedPath}`;
    }
    const annotations = context.sealScreen ? '' : sealAnnotationMarkup(seals);
    const fallbackAttribute = fallback ? ` data-fallback-src="${escapeHtml(fallback)}"` : '';
    const image = `<img src="${escapeHtml(source)}" alt="${escapeHtml(fileName)}" loading="lazy"${fallbackAttribute}>`;
    const editAttributes = context.path && context.index !== null && context.index !== undefined
      ? ` data-document-path="${escapeHtml(context.path)}" data-entry-index="${context.index}" data-image-index="${context.imageIndex ?? imageIndex}"`
      : '';
    const imageLink = `<a class="image-link" href="${escapeHtml(source)}" aria-label="Open image" data-image-src="${escapeHtml(source)}" data-image-fallback="${escapeHtml(fallback)}"${editAttributes}>${image}</a>`;
    const annotatedImage = context.crop
      ? `<span class="seal-crop is-loading" data-seal-x="${context.crop.x}" data-seal-y="${context.crop.y}" data-seal-size="${context.crop.size}" data-seal-width="${context.crop.width ?? 0}" data-seal-widening-rotation="${context.crop.wideningRotation || 0}" data-seal-rotation="${context.crop.rotation || 0}">${imageLink}</span>`
      : annotations ? `<span class="annotated-image">${imageLink}${annotations}</span>` : imageLink;
    return `<figure class="entry-image">${annotatedImage}</figure>`;
  }).filter(Boolean).join('');
  return images ? `<div class="entry-images">${images}</div>` : '';
}

function setupSealAnnotations() {
  state.sealMarkerCleanup?.();
  state.sealMarkerCleanup = null;
  const annotatedImages = [...document.querySelectorAll('.annotated-image img')];
  const cropImages = [...document.querySelectorAll('.seal-crop img')];
  if (!annotatedImages.length && !cropImages.length) return;
  const cropReveals = new Map();
  const update = () => {
    annotatedImages.forEach((image) => {
      const height = image.clientHeight;
      image.closest('.annotated-image')?.querySelectorAll('.seal-marker').forEach((marker) => {
        marker.style.setProperty('--seal-diameter', `${height * Number(marker.dataset.size)}px`);
        marker.style.setProperty('--seal-width', Number(marker.dataset.width) || 0);
        marker.style.setProperty('--seal-widening-rotation', `${Number(marker.dataset.wideningRotation) || 0}deg`);
        marker.style.setProperty('--seal-rotation', `${Number(marker.dataset.rotation) || 0}deg`);
      });
    });
    cropImages.forEach((image) => {
      if (!image.naturalWidth || !image.naturalHeight) return;
      const crop = image.closest('.seal-crop');
      if (!crop) return;
      const x = Number(crop.dataset.sealX);
      const y = Number(crop.dataset.sealY);
      const size = Number(crop.dataset.sealSize);
      const width = Number(crop.dataset.sealWidth) || 0;
      const wideningRotation = Number(crop.dataset.sealWideningRotation) || 0;
      const rotation = Number(crop.dataset.sealRotation) || 0;
      if (![x, y, size, width, wideningRotation, rotation].every(Number.isFinite) || size <= 0 || !crop.clientWidth || !crop.clientHeight) return;
      positionSealCrop(image, crop, x, y, size, width, wideningRotation, rotation);
    });
  };
  annotatedImages.forEach((image) => image.addEventListener('load', update));
  cropImages.forEach((image) => {
    const reveal = () => {
      update();
      image.closest('.seal-crop')?.classList.remove('is-loading');
    };
    cropReveals.set(image, reveal);
    image.addEventListener('load', reveal);
    if (image.complete && image.naturalWidth && image.naturalHeight) reveal();
  });
  window.addEventListener('resize', update, { passive: true });
  state.sealMarkerCleanup = () => {
    annotatedImages.forEach((image) => image.removeEventListener('load', update));
    cropImages.forEach((image) => image.removeEventListener('load', cropReveals.get(image)));
    window.removeEventListener('resize', update);
  };
  update();
}

function positionSealCrop(image, crop, x, y, size, sealWidth = 0, wideningRotation = 0, rotation = 0) {
  const cropSize = image.naturalHeight * Math.max(size, 0.035);
  const scale = crop.clientHeight / cropSize;
  const imageWidth = image.naturalWidth * scale;
  const height = image.naturalHeight * scale;
  image.style.width = `${imageWidth}px`;
  image.style.height = `${height}px`;
  image.style.left = `${crop.clientWidth / 2 - x * imageWidth}px`;
  image.style.top = `${crop.clientHeight / 2 - y * height}px`;
  image.style.transformOrigin = `${x * imageWidth}px ${y * height}px`;
  image.style.transform = `rotate(${rotation}deg) rotate(${-wideningRotation}deg) scaleX(${1 + sealWidth}) rotate(${wideningRotation}deg)`;
}

document.addEventListener('error', (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement)) return;
  const fallback = image.dataset.fallbackSrc;
  if (!fallback || image.src === fallback) return;
  image.removeAttribute('data-fallback-src');
  image.src = fallback;
}, true);

function setupImageLightbox() {
  const lightbox = $('#image-lightbox');
  const lightboxImage = $('#image-lightbox-image');
  const lightboxStage = $('#image-lightbox-stage');
  const lightboxAnnotations = $('#image-lightbox-annotations');
  const sealPreview = $('#image-lightbox-seal-preview');
  const sealPreviewCrop = sealPreview?.querySelector('.seal-crop');
  const sealPreviewImage = sealPreview?.querySelector('img');
  const sealPreviewName = sealPreview?.querySelector('.image-lightbox-seal-preview-name');
  const closeButton = $('#image-lightbox-close');
  const editor = $('#image-lightbox-editor');
  const addSealButton = $('#image-lightbox-add-seal');
  const removeImageButton = $('#image-lightbox-remove-image');
  const removeSealButton = $('#image-lightbox-remove-seal');
  const selectedSealControls = $('#image-lightbox-seal-selected-controls');
  const sealWidthControl = $('#image-lightbox-seal-width');
  const sealWideningRotationControl = $('#image-lightbox-seal-widening-rotation');
  const sealRotationControl = $('#image-lightbox-seal-rotation');
  const sealTypeControls = [...document.querySelectorAll('input[name="image-lightbox-seal-type"]')];
  const saveStatus = $('#image-lightbox-save-status');
  if (!lightbox || !lightboxImage || !lightboxStage || !lightboxAnnotations || !closeButton) return;
  const editable = !location.hostname.endsWith('github.io');
  let editingContext = null;
  let selectedIndex = null;
  let drag = null;
  let magnifierPoint = null;
  let saveQueue = Promise.resolve();
  const SEAL_SIZE_STEP = 0.0005;
  const MAGNIFIER_SIZE = 0.12;
  const MAGNIFIER_SIZE_STEP = 0.01;
  let magnifierSize = MAGNIFIER_SIZE;
  if (editor) editor.hidden = !editable;

  const currentSeals = () => editingContext?.node?.seals || [];
  const magnifierMaximumSize = () => {
    const imageHeight = lightboxAnnotations.clientHeight;
    const previewHeight = sealPreviewCrop?.clientHeight;
    return imageHeight && previewHeight ? Math.max(0.03, Math.min(0.5, previewHeight / imageHeight)) : MAGNIFIER_SIZE;
  };
  const updateSealPreview = () => {
    const seal = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
    if (!sealPreview || !sealPreviewCrop || !sealPreviewImage) return;
    let x;
    let y;
    let size;
    let width = 0;
    let wideningRotation = 0;
    let rotation = 0;
    if (seal) {
      [x, y] = String(seal.position || '').split(',').map(Number);
      size = Number(seal.size);
      width = Number(seal.width) || 0;
      wideningRotation = Number(seal.wideningRotation) || 0;
      rotation = Number(seal.rotation) || 0;
      sealPreview.classList.remove('is-magnifier');
      sealPreview.classList.add('is-seal-preview');
      sealPreviewName.hidden = false;
      sealPreviewName.value = seal.person || '';
    } else if (magnifierPoint) {
      ({ x, y } = magnifierPoint);
      magnifierSize = Math.min(magnifierMaximumSize(), Math.max(0.03, magnifierSize));
      size = magnifierSize;
      sealPreview.classList.add('is-magnifier');
      sealPreview.classList.remove('is-seal-preview');
      sealPreviewName.hidden = true;
      if (magnifierSize >= magnifierMaximumSize() - 0.0001) {
        sealPreview.hidden = true;
        return;
      }
    } else {
      sealPreview.hidden = true;
      return;
    }
    if (![x, y, size].every(Number.isFinite) || size <= 0) {
      if (sealPreview) sealPreview.hidden = true;
      return;
    }
    sealPreview.hidden = false;
    if (seal) {
      const imageRect = lightboxAnnotations.getBoundingClientRect();
      const lightboxRect = lightbox.getBoundingClientRect();
      sealPreview.style.left = `${imageRect.left + x * imageRect.width - lightboxRect.left}px`;
      sealPreview.style.top = `${imageRect.top + y * imageRect.height - lightboxRect.top}px`;
    }
    sealPreviewCrop.dataset.sealX = x;
    sealPreviewCrop.dataset.sealY = y;
    sealPreviewCrop.dataset.sealSize = size;
    sealPreviewCrop.dataset.sealWidth = width;
    sealPreviewCrop.dataset.sealWideningRotation = wideningRotation;
    sealPreviewCrop.dataset.sealRotation = rotation;
    if (sealPreviewImage.src !== lightboxImage.src) sealPreviewImage.src = lightboxImage.src;
    if (sealPreviewImage.naturalWidth && sealPreviewImage.naturalHeight) {
      positionSealCrop(sealPreviewImage, sealPreviewCrop, x, y, size, width, wideningRotation, rotation);
      sealPreviewCrop.classList.remove('is-loading');
    }
  };
  sealPreviewImage?.addEventListener('load', updateSealPreview);
  sealPreviewName?.addEventListener('input', () => {
    const seal = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
    if (!seal) return;
    seal.person = sealPreviewName.value;
  });
  const updateEditorControls = () => {
    const selected = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
    if (selectedSealControls) selectedSealControls.hidden = !selected;
    if (removeSealButton) removeSealButton.hidden = !selected;
    if (sealWidthControl) {
      sealWidthControl.disabled = !selected;
      sealWidthControl.value = String(Number(selected?.width) || 0);
    }
    if (sealRotationControl) {
      sealRotationControl.disabled = !selected;
      sealRotationControl.value = String(Number(selected?.rotation) || 0);
    }
    if (sealWideningRotationControl) {
      sealWideningRotationControl.disabled = !selected;
      sealWideningRotationControl.value = String(Number(selected?.wideningRotation) || 0);
    }
    sealTypeControls.forEach((control) => {
      control.disabled = !selected;
      control.checked = Boolean(selected && sealTypeForSeal(selected) === control.value);
    });
  };
  const updateSelectedModifier = (property, value) => {
    const seal = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
    if (!seal) return;
    seal[property] = Number(value);
    renderLightboxSeals();
  };
  const resizeSeal = (index, amount) => {
    const seal = currentSeals()[index];
    if (!seal) return;
    seal.size = Math.max(0.01, Math.min(0.5, Number(seal.size) + amount));
    renderLightboxSeals();
  };
  const renderLightboxSeals = () => {
    const seals = currentSeals();
    let sealIndex = 0;
    lightboxAnnotations.innerHTML = sealAnnotationMarkup(seals).replace(/class="seal-marker"/g, (match) => {
      const index = sealIndex++;
      return `${match} data-seal-index="${index}"${index === selectedIndex ? ' data-selected="true"' : ''}`;
    });
    lightboxAnnotations.querySelectorAll('.seal-marker').forEach((marker) => {
      if (Number(marker.dataset.sealIndex) === selectedIndex) marker.classList.add('selected');
    });
    updateLightboxAnnotations();
    updateSealPreview();
    updateEditorControls();
  };
  const setSaveStatus = (message, error = false) => {
    if (!saveStatus) return;
    saveStatus.textContent = message;
    saveStatus.classList.toggle('error', error);
  };
  const saveDocument = () => {
    if (!editingContext) return Promise.resolve(true);
    const operation = saveQueue.then(async () => {
      const context = editingContext;
      const entry = state.documents.get(context.path)?.entries?.[Number(context.entryIndex)];
      if (entry) {
        const images = Array.isArray(entry.img) ? entry.img : [entry.img];
        images.forEach((image) => {
          if (image && typeof image === 'object' && Array.isArray(image.seals) && image.seals.length === 0) delete image.seals;
        });
      }
      try {
        setSaveStatus('Saving…');
        const response = await fetch('/api/save-document', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: context.path, document: state.documents.get(context.path) }) });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `Save failed (${response.status})`);
        state.snapshot = '';
        return true;
      } catch (error) {
        setSaveStatus(error.message, true);
        return false;
      }
    });
    saveQueue = operation.catch(() => {});
    return operation;
  };
  const closeLightbox = () => {
    lightbox.close();
  };
  const saveAndCloseLightbox = async () => {
    if (editingContext && !await saveDocument()) return;
    closeLightbox();
  };
  const imagePoint = (event) => {
    const rect = lightboxAnnotations.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)) };
  };
  const startSealDrag = (event, index, target) => {
    const seal = currentSeals()[index];
    if (!seal) return;
    selectedIndex = index;
    const point = imagePoint(event);
    const [sealX, sealY] = String(seal.position || '').split(',').map(Number);
    drag = { index, pointerId: event.pointerId, offsetX: sealX - point.x, offsetY: sealY - point.y };
    lightboxAnnotations.querySelectorAll('.seal-marker').forEach((item) => item.classList.toggle('selected', Number(item.dataset.sealIndex) === index));
    updateEditorControls();
    target.setPointerCapture?.(event.pointerId);
    event.preventDefault();
  };
  const moveSealDrag = (event) => {
    if (!drag || (drag.pointerId !== undefined && event.pointerId !== drag.pointerId)) return;
    const point = imagePoint(event);
    const seal = currentSeals()[drag.index];
    if (!seal) return;
    const x = Math.max(0, Math.min(1, point.x + Number(drag.offsetX)));
    const y = Math.max(0, Math.min(1, point.y + Number(drag.offsetY)));
    seal.position = `${x.toFixed(4)},${y.toFixed(4)}`;
    const marker = lightboxAnnotations.querySelector(`.seal-marker[data-seal-index="${drag.index}"]`);
    if (marker) {
      marker.style.left = `${x * 100}%`;
      marker.style.top = `${y * 100}%`;
    }
    updateSealPreview();
  };
  const updateLightboxAnnotations = () => {
    if (!lightboxImage.naturalWidth || !lightboxImage.naturalHeight) return;
    const stageWidth = lightboxStage.clientWidth;
    const stageHeight = lightboxStage.clientHeight;
    const scale = Math.min(stageWidth / lightboxImage.naturalWidth, stageHeight / lightboxImage.naturalHeight);
    const imageWidth = lightboxImage.naturalWidth * scale;
    const imageHeight = lightboxImage.naturalHeight * scale;
    lightboxAnnotations.style.left = `${(stageWidth - imageWidth) / 2}px`;
    lightboxAnnotations.style.top = `${(stageHeight - imageHeight) / 2}px`;
    lightboxAnnotations.style.width = `${imageWidth}px`;
    lightboxAnnotations.style.height = `${imageHeight}px`;
    lightboxAnnotations.querySelectorAll('.seal-marker').forEach((marker) => {
      marker.style.setProperty('--seal-diameter', `${imageHeight * Number(marker.dataset.size)}px`);
      marker.style.setProperty('--seal-width', Number(marker.dataset.width) || 0);
      marker.style.setProperty('--seal-widening-rotation', `${Number(marker.dataset.wideningRotation) || 0}deg`);
      marker.style.setProperty('--seal-rotation', `${Number(marker.dataset.rotation) || 0}deg`);
    });
  };
  $('#content').addEventListener('click', (event) => {
    const link = event.target.closest('.image-link');
    if (!link) return;
    event.preventDefault();
    const image = link.querySelector('img');
    const path = link.dataset.documentPath;
    const entryIndex = Number(link.dataset.entryIndex);
    const imageIndex = Number(link.dataset.imageIndex);
    const entry = path ? state.documents.get(path)?.entries?.[entryIndex] : null;
    let node = entry && (Array.isArray(entry.img) ? entry.img[imageIndex] : entry.img);
    if (node && typeof node !== 'object') {
      if (entry && !Array.isArray(entry.img)) {
        entry.img = { src: node };
      } else if (entry) entry.img[imageIndex] = { src: node };
      node = entry && (Array.isArray(entry.img) ? entry.img[imageIndex] : entry.img);
    }
    editingContext = editable && entry && node && typeof node === 'object' ? { path, node, entryIndex, imageIndex } : null;
    if (editingContext) {
      if (!Array.isArray(node.seals)) node.seals = [];
    }
    selectedIndex = null;
    lightbox.classList.toggle('is-editable', Boolean(editingContext));
    renderLightboxSeals();
    lightboxImage.onerror = () => {
      const fallback = link.dataset.imageFallback;
      if (fallback && lightboxImage.src !== fallback) lightboxImage.src = fallback;
    };
    lightboxImage.src = image?.currentSrc || link.dataset.imageSrc;
    lightboxImage.alt = image?.alt || '';
    lightboxImage.addEventListener('load', updateLightboxAnnotations, { once: true });
    lightboxImage.addEventListener('load', updateSealPreview, { once: true });
    lightbox.showModal();
    updateLightboxAnnotations();
  });
  window.addEventListener('resize', updateLightboxAnnotations, { passive: true });
  window.addEventListener('resize', updateSealPreview, { passive: true });
  closeButton.addEventListener('click', saveAndCloseLightbox);
  sealWidthControl?.addEventListener('input', () => updateSelectedModifier('width', sealWidthControl.value));
  sealWideningRotationControl?.addEventListener('input', () => updateSelectedModifier('wideningRotation', sealWideningRotationControl.value));
  sealRotationControl?.addEventListener('input', () => updateSelectedModifier('rotation', sealRotationControl.value));
  sealTypeControls.forEach((control) => {
    control.addEventListener('change', () => {
      const seal = selectedIndex !== null ? currentSeals()[selectedIndex] : null;
      if (seal && control.checked) seal.type = control.value;
    });
  });
  lightboxAnnotations.addEventListener('pointerdown', (event) => {
    if (!editingContext) return;
    const marker = event.target.closest('.seal-marker');
    if (!marker) return;
    startSealDrag(event, Number(marker.dataset.sealIndex), marker);
  });
  lightboxAnnotations.addEventListener('pointermove', moveSealDrag);
  lightboxAnnotations.addEventListener('pointerup', () => { drag = null; });
  lightboxAnnotations.addEventListener('pointercancel', () => { drag = null; });
  sealPreview?.addEventListener('pointerdown', (event) => {
    if (!editingContext || selectedIndex === null || !sealPreview.classList.contains('is-seal-preview') || !event.target.closest('.seal-crop')) return;
    startSealDrag(event, selectedIndex, sealPreview);
  });
  sealPreview?.addEventListener('pointermove', moveSealDrag);
  sealPreview?.addEventListener('pointerup', () => { drag = null; });
  sealPreview?.addEventListener('pointercancel', () => { drag = null; });
  lightboxStage.addEventListener('click', async (event) => {
    if (!editingContext) return;
    const marker = event.target.closest?.('.seal-marker');
    if (marker) {
      magnifierPoint = null;
      selectedIndex = Number(marker.dataset.sealIndex);
      renderLightboxSeals();
      return;
    }
    const deselectedIndex = selectedIndex;
    selectedIndex = null;
    renderLightboxSeals();
    const savingMarker = deselectedIndex === null
      ? null
      : lightboxAnnotations.querySelector(`.seal-marker[data-seal-index="${deselectedIndex}"]`);
    savingMarker?.classList.add('saving');
    try {
      await saveDocument();
    } finally {
      savingMarker?.classList.remove('saving');
    }
  });
  lightboxStage.addEventListener('pointermove', (event) => {
    if (!editingContext || selectedIndex !== null) return;
    const rect = lightboxAnnotations.getBoundingClientRect();
    if (!rect.width || !rect.height || event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) {
      magnifierPoint = null;
      updateSealPreview();
      return;
    }
    const wasInactive = !magnifierPoint;
    magnifierPoint = {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
    if (wasInactive) magnifierSize = magnifierMaximumSize();
    updateSealPreview();
    const lightboxRect = lightbox.getBoundingClientRect();
    sealPreview.style.left = `${event.clientX - lightboxRect.left}px`;
    sealPreview.style.top = `${event.clientY - lightboxRect.top}px`;
  });
  lightboxStage.addEventListener('pointerleave', () => {
    if (selectedIndex !== null) return;
    magnifierPoint = null;
    updateSealPreview();
  });
  lightbox.addEventListener('wheel', (event) => {
    // A modal should own the wheel while it is open; otherwise the page can
    // scroll underneath it. The marker, when present, is the resize target.
    event.preventDefault();
    if (!editingContext) return;
    if (selectedIndex === null && magnifierPoint) {
      const maximum = magnifierMaximumSize();
      magnifierSize = Math.max(0.03, Math.min(maximum, magnifierSize + (event.deltaY < 0 ? -MAGNIFIER_SIZE_STEP : MAGNIFIER_SIZE_STEP)));
      updateSealPreview();
      return;
    }
    const marker = event.target.closest('.seal-marker');
    const previewCrop = event.target.closest('.image-lightbox-seal-preview .seal-crop');
    const index = marker ? Number(marker.dataset.sealIndex) : previewCrop && sealPreview.classList.contains('is-seal-preview') ? selectedIndex : null;
    if (index === null) return;
    if (index !== selectedIndex) return;
    // deltaMode differs between mouse wheels, trackpads, and browsers. Use
    // the direction only so one gesture has predictable precision everywhere.
    resizeSeal(index, event.deltaY < 0 ? SEAL_SIZE_STEP : -SEAL_SIZE_STEP);
  }, { passive: false });
  addSealButton?.addEventListener('click', () => {
    if (!editingContext) return;
    const person = window.prompt('Person shown by this seal:');
    if (!person?.trim()) return;
    editingContext.node.seals.push({ person: person.trim(), position: '0.5,0.5', size: 0.08, width: 0, wideningRotation: 0, rotation: 0, type: 'full' });
    selectedIndex = editingContext.node.seals.length - 1;
    renderLightboxSeals();
  });
  removeImageButton?.addEventListener('click', async () => {
    if (!editingContext || !window.confirm('Remove this image from the document?')) return;
    const entry = state.documents.get(editingContext.path)?.entries?.[Number(editingContext.entryIndex)];
    if (!entry) return;
    if (Array.isArray(entry.img)) {
      const image = entry.img[Number(editingContext.imageIndex)];
      if (image && typeof image === 'object') image.deleted = 'true';
      else entry.img[Number(editingContext.imageIndex)] = { src: image, deleted: 'true' };
    } else {
      if (entry.img && typeof entry.img === 'object') entry.img.deleted = 'true';
      else entry.img = { src: entry.img, deleted: 'true' };
    }
    if (!await saveDocument()) return;
    lightbox.close();
    await renderActive();
  });
  removeSealButton?.addEventListener('click', () => {
    if (selectedIndex === null) return;
    currentSeals().splice(selectedIndex, 1);
    selectedIndex = null;
    renderLightboxSeals();
  });
  lightbox.addEventListener('click', (event) => {
    if (event.target === lightbox) saveAndCloseLightbox();
  });
  lightbox.addEventListener('cancel', (event) => {
    event.preventDefault();
    saveAndCloseLightbox();
  });
  lightbox.addEventListener('close', () => {
    lightboxImage.removeAttribute('src');
    lightboxAnnotations.replaceChildren();
    if (sealPreview) sealPreview.hidden = true;
    magnifierPoint = null;
    sealPreviewImage?.removeAttribute('src');
    editingContext = null;
    selectedIndex = null;
    drag = null;
    lightbox.classList.remove('is-editable');
    setSaveStatus('');
  });
}

async function getJson(path) {
  const parts = location.pathname.split('/').filter(Boolean);
  const owner = location.hostname.split('.')[0];
  const repository = parts[0];
  const dataPath = location.hostname.endsWith('github.io')
    ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${path}`
    : `../${path}`;
  const response = await fetch(`${dataPath}?v=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

async function getRepositoryFiles() {
  if (!location.hostname.endsWith('github.io')) {
    const response = await fetch(`/api/files?v=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Local file list: ${response.status}`);
    return response.json();
  }
  const parts = location.pathname.split('/').filter(Boolean);
  const owner = location.hostname.split('.')[0];
  const repository = parts[0];
  if (!owner || !repository) throw new Error('The viewer must be opened from a GitHub Pages project URL.');
  const response = await fetch(`https://api.github.com/repos/${owner}/${repository}/git/trees/HEAD?recursive=1`);
  if (!response.ok) throw new Error(`GitHub repository tree: ${response.status}`);
  const tree = await response.json();
  return tree.tree
    .filter((item) => item.type === 'blob' && /^data\/(books|letters|notes)\/.*\.json$/.test(item.path))
    .map((item) => ({ path: item.path, version: item.sha }))
    .sort((left, right) => left.path.localeCompare(right.path));
}

function formatDate(date) {
  const range = String(date || '').split('/');
  if (range.length === 2) {
    const start = formatDate(range[0]);
    const end = formatDate(range[1]);
    return start !== range[0] && end !== range[1] ? `${start} – ${end}` : date;
  }

  const match = String(date || '').match(/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/);
  if (!match) return date;

  const [, year, month, day] = match;
  if (!month) return year;
  const value = new Date(Date.UTC(Number(year), Number(month) - 1, day ? Number(day) : 1));
  const monthName = new Intl.DateTimeFormat('en-US', { month: 'long', timeZone: 'UTC' }).format(value);
  return day ? `${year}, ${monthName} ${Number(day)}` : `${year}, ${monthName}`;
}

function documentTitle(doc, path) { return doc.book || formatDate(doc.date) || path.split('/').pop().replace(/\.json$/, ''); }

function documentYear(doc) {
  const match = String(doc?.date || '').match(/^(\d{4})/);
  return match ? match[1] : null;
}

function bookSortYear(doc, path) {
  const match = String(doc?.book || path || '').match(/\d{4}/);
  return match ? Number(match[0]) : -Infinity;
}

function sealSortYear(entry) {
  const years = String(entry?.date || '').match(/\d{4}/g);
  return years?.length ? Math.min(...years.map(Number)) : Infinity;
}

const SEAL_TYPES = new Set(['contrepalle', 'swans', 'helm', 'full']);

function sealTypeForSeal(seal) {
  if (SEAL_TYPES.has(seal?.type)) return seal.type;
  return null;
}

function letterSealEntries() {
  const sealEntries = [];
  state.manifest.letters.forEach((path) => {
    const document = state.documents.get(path);
    (document?.entries || []).forEach((entry, entryIndex) => {
      const imageNodes = Array.isArray(entry.img) ? entry.img : [entry.img];
      imageNodes.forEach((node, imageIndex) => {
        if (node && typeof node === 'object' && node.deleted === 'true') return;
        const seals = node && typeof node === 'object' ? node.seals : imageIndex === 0 ? entry.seals : [];
        if (!Array.isArray(seals) || !seals.length || !node) return;
        seals.forEach((seal) => {
          const person = String(seal?.person || '').trim();
          const position = String(seal?.position || '').split(',').map(Number);
          const size = Number(seal?.size);
          const width = Number(seal?.width) || 0;
          const wideningRotation = Number(seal?.wideningRotation) || 0;
          const rotation = Number(seal?.rotation) || 0;
          if (!person || position.length !== 2 || !position.every(Number.isFinite) || !Number.isFinite(size) || size <= 0) return;
          sealEntries.push({
            title: person,
            source: entry.source,
            date: entry.date || document.date,
            url: entry.url || document.url,
            img: [node],
            seals,
            crop: { x: position[0], y: position[1], size, width, wideningRotation, rotation },
            sourcePath: path,
            sourceIndex: entryIndex,
            sourceImageIndex: imageIndex,
            type: sealTypeForSeal(seal),
          });
        });
      });
    });
  });
  return sealEntries;
}

const sealTypeFilters = [
  ['contrepalle', 'contrepalle'],
  ['swans', 'swans'],
  ['helm', 'helm'],
  ['full', 'full'],
  ['unknown', 'unknown'],
];

function sealMatchesType(entry, selected) {
  return !selected || (selected === 'unknown' ? !entry.type : entry.type === selected);
}

function sealTypeYearSpan(entries, type) {
  const years = entries
    .filter((entry) => entry.type === type)
    .flatMap((entry) => String(entry.date || '').match(/\d{4}/g) || [])
    .map(Number);
  if (!years.length) return '';
  const first = Math.min(...years);
  const last = Math.max(...years);
  return first === last ? String(first) : `${first}-${last}`;
}

function normalizeSealFilter(value) {
  const label = String(value || '').trim();
  return label.includes('?') ? 'unknown' : label.toLocaleLowerCase();
}

function sealMatchesSelected(title, selected) {
  const label = String(title || '').trim();
  const normalized = label.toLocaleLowerCase();
  if (selected.has('unknown') && label.includes('?')) return true;
  return [...selected].some((key) => {
    if (key === 'unknown') return false;
    if (normalized === key) return true;
    if (key.includes(' ')) return false;
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const namePattern = new RegExp(`(?:^|[+\\/\\s])${escaped}\\??(?=$|[+\\/\\s])`, 'iu');
    const vonPattern = new RegExp(`(?:^|[+\\/\\s])${escaped}\\??\\s+von(?:\\s|$)`, 'iu');
    return namePattern.test(label) && !vonPattern.test(label);
  });
}

function sealSourceMarkup(source) {
  const match = letterForSource(source);
  if (!match) return markdownLinks(source);
  const params = new URLSearchParams({ tab: 'letters', letter: match.path, source: sourceCitations(source)[0] });
  const hash = `#${entryAnchor(match.path, match.entryIndex)}`;
  return `<a href="?${params.toString()}${hash}">${markdownLinks(source)}</a>`;
}

function sealLetterUrlMarkup(source) {
  const match = letterForSource(source);
  if (!match) return '';
  const url = match.entry.url || state.documents.get(match.path)?.url;
  return url ? urlMarkup(url) : '';
}

function renderSealSidebar(entries) {
  const labels = new Map();
  entries.forEach((entry, index) => {
    const label = String(entry.title || '').trim();
    if (/[+/]/.test(label) || /\szu\s/i.test(label) || /\s(?:elder|knight|nobleman)$/i.test(label)) return;
    const key = label.includes('?') ? 'unknown' : label.toLocaleLowerCase();
    if (label && !labels.has(key)) labels.set(key, { label, index });
  });
  const links = [...labels.values()]
    .map((item) => item.label.includes('?') ? { ...item, label: 'unknown', key: 'unknown' } : { ...item, key: item.label.toLocaleLowerCase() })
    .sort((left, right) => left.key === 'unknown' ? -1 : right.key === 'unknown' ? 1 : left.label.localeCompare(right.label, undefined, { sensitivity: 'base' }))
    .map(({ label, key }) => {
      return `<a href="#" class="${state.sealNames.includes(key) ? 'selected' : ''}" data-seal-name="${escapeHtml(key)}">${escapeHtml(label)}</a>`;
    })
    .join('');
  const hasUnknownTypes = entries.some((entry) => !entry.type);
  const typeLinks = sealTypeFilters.filter(([type]) => type !== 'unknown' || hasUnknownTypes).map(([type, label]) => {
    const detail = type === 'unknown'
      ? `(${entries.filter((entry) => !entry.type).length})`
      : sealTypeYearSpan(entries, type);
    return `<a href="#" class="${state.sealType === type ? 'selected' : ''}" data-seal-type="${type}"><span>${label}</span>${detail ? `<small>${detail}</small>` : ''}</a>`;
  }).join('');
  const nameSidebar = links ? `<aside class="seal-sidebar seal-name-sidebar" aria-label="Seals by name"><nav>${links}</nav></aside>` : '';
  const typeSidebar = typeLinks ? `<aside class="seal-sidebar seal-type-sidebar" aria-label="Seals by type"><nav>${typeLinks}</nav></aside>` : '';
  return `${nameSidebar}${typeSidebar}`;
}

function renderSealsPage() {
  const allEntries = letterSealEntries().sort((left, right) => sealSortYear(left) - sealSortYear(right) || left.title.localeCompare(right.title));
  const selected = new Set(state.sealNames);
  const entries = allEntries.filter((entry) => (!selected.size || sealMatchesSelected(entry.title, selected)) && sealMatchesType(entry, state.sealType));
  const content = entries.map((entry, index) => {
    const titleMarkup = entry.title ? `<h3>${escapeHtml(entry.title)}</h3>` : '';
    const dateMarkup = entry.date ? `<small>${escapeHtml(formatDate(entry.date))}</small>` : '';
    const sourceMarkup = entry.source ? `<p class="source">${sealSourceMarkup(entry.source)}</p>` : '';
    const urlMarkupForLetter = entry.source ? sealLetterUrlMarkup(entry.source) || urlMarkup(entry.url) : urlMarkup(entry.url);
    const imageContext = { path: entry.sourcePath, index: entry.sourceIndex, imageIndex: entry.sourceImageIndex, crop: entry.crop, sealScreen: true };
    return `<article class="entry seal-entry" id="seal-${index}"><div class="seal-entry-meta">${titleMarkup}${dateMarkup}${sourceMarkup}${urlMarkupForLetter}</div><div class="seal-entry-media">${imageMarkup(entry.img, entry.seals, imageContext)}</div></article>`;
  }).join('');
  if (!allEntries.length) return '<article class="document"><h2>Seals</h2><p class="status">No named seals are recorded in the letter images.</p></article>';
  if (!entries.length) return `<div class="seals-layout">${renderSealSidebar(allEntries)}<article class="document seals-document"><p class="status">No seals match the selected filters.</p></article></div>`;
  return `<div class="seals-layout">${renderSealSidebar(allEntries)}<article class="document seals-document">${content}</article></div>`;
}

function setupSealHighlight(entries) {
  state.sealHighlightCleanup?.();
  state.sealHighlightCleanup = null;
  const links = [...document.querySelectorAll('.seal-sidebar a')];
  const nameLinks = links.filter((link) => link.dataset.sealName);
  const targets = entries.map((_, index) => document.querySelector(`#seal-${index}`)).filter(Boolean);
  if (!links.length || !targets.length) return;
  links.forEach((link) => link.addEventListener('click', (event) => {
    event.preventDefault();
    if (link.dataset.sealType) {
      state.sealType = state.sealType === link.dataset.sealType ? null : link.dataset.sealType;
    } else {
      const name = link.dataset.sealName;
      const index = state.sealNames.indexOf(name);
      if (index >= 0) state.sealNames.splice(index, 1);
      else state.sealNames.push(name);
    }
    savePreferences();
    renderActive();
  }));
  const update = () => {
    const marker = window.scrollY + 160;
    let current = 0;
    targets.forEach((target, index) => {
      if (target.getBoundingClientRect().top + window.scrollY <= marker) current = index;
    });
    const currentTitle = entries[current]?.title?.trim() || '';
    const name = currentTitle.includes('?') ? 'unknown' : currentTitle.toLocaleLowerCase();
    nameLinks.forEach((link) => {
      const active = link.dataset.sealName === name;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
  };
  window.addEventListener('scroll', update, { passive: true });
  state.sealHighlightCleanup = () => window.removeEventListener('scroll', update);
  update();
}

function urlLabel(value) {
  try {
    const hostname = new URL(value).hostname.replace(/^www\./i, '');
    return hostname.split('.').slice(-2).join('.');
  } catch {
    return value;
  }
}

function urlMarkup(value) {
  const links = (Array.isArray(value) ? value : [value])
    .filter((url) => /^https?:\/\//i.test(String(url || '')))
    .map((url) => `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(urlLabel(url))}</a>`);
  return links.length ? `<p class="document-url">${links.join(' · ')}</p>` : '';
}

function findEntityByName(entities, name) {
  return entities.find((entity) => entity.names.some((candidate) => candidate.toLocaleLowerCase() === String(name).toLocaleLowerCase()));
}

function placeForName(name) {
  return findEntityByName(state.places, name);
}

function placeMentions(place) {
  const pattern = buildPlacePattern([place]);
  const mentions = [];
  state.documents.forEach((doc, path) => (doc.entries || []).forEach((entry, index) => {
    const fields = ['title', 'source', 'german', 'latin', 'english', 'facts'];
    const documentPlace = String(doc.place || '');
    if (documentPlace.match(pattern) || fields.some((field) => (Array.isArray(entry[field]) ? entry[field].join('\n') : String(entry[field] || '')).match(pattern))) {
      mentions.push({ doc, path, entry, index });
    }
  }));
  return mentions;
}

function displayedLanguagesFor(entry) {
  const available = ['english', 'german', 'latin'].filter((language) => String(entry[language] || '').trim());
  if (!available.length) return [];
  const original = ['german', 'latin'].find((language) => available.includes(language));
  const languages = state.language === 'original'
    ? ['english', original].filter(Boolean).filter((language) => available.includes(language))
    : ['english'].filter((language) => available.includes(language));
  return languages.length ? languages : available.slice(0, 1);
}

function entityExcerpt(value, pattern, linkEntities = true) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  const sentences = text.split(/(?<=[.!?。！？])\s+/).filter((sentence) => { pattern.lastIndex = 0; return pattern.test(sentence); });
  let excerpt = sentences.slice(0, 2).join(' ');
  if (!excerpt) excerpt = text;
  let source = excerpt;
  pattern.lastIndex = 0;
  let match = pattern.exec(source);
  if (!match) {
    source = text;
    pattern.lastIndex = 0;
    match = pattern.exec(source);
  }
  if (match && source.length > 420) {
    const limit = 360;
    const maxStart = Math.max(0, source.length - limit);
    let start = Math.min(Math.max(0, match.index - 170), maxStart);
    if (match.index + match[0].length > start + limit) start = Math.min(match.index, maxStart);
    excerpt = `${start ? '…' : ''}${source.slice(start, start + limit)}${start + limit < source.length ? '…' : ''}`;
  }
  return inlineMarkup(excerpt, linkEntities);
}

function entityLanguageMarkup(entry, pattern) {
  const displayedLanguages = displayedLanguagesFor(entry);
  if (!displayedLanguages.length) return '';
  return `<div class="text-grid ${displayedLanguages.length === 1 ? 'single' : ''}">${displayedLanguages.map((language) => `<div class="language"><div class="text"><p>${entityExcerpt(entry[language], pattern, language === 'english')}</p></div></div>`).join('')}</div>`;
}

function entryAnchor(path, index) {
  return `entry-${path.replace(/[^a-z0-9]+/gi, '-')}-${index}`;
}

function documentNavigationUrl(path, index) {
  const params = new URLSearchParams();
  if (path.startsWith('data/letters/')) {
    params.set('tab', 'letters');
    params.set('letter', path);
  } else {
    params.set('document', path);
  }
  return `?${params.toString()}#${entryAnchor(path, index)}`;
}

function factDate(fact, doc, entry) {
  if (fact && typeof fact === 'object' && fact.date) return fact.date;
  return entry.date || doc.date || '';
}

function factText(fact) {
  return fact && typeof fact === 'object' ? fact.text : fact;
}

function dateSortValue(date) {
  const match = String(date || '').match(/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?/);
  if (!match) return Infinity;
  return Number(`${match[1]}${match[2] || '01'}${match[3] || '01'}`);
}

function entityFactRecords(mentions) {
  return mentions.flatMap(({ doc, path, entry, index }, mentionIndex) => (Array.isArray(entry.facts) ? entry.facts : [])
    .map((fact, factIndex) => ({ date: factDate(fact, doc, entry), text: factText(fact), doc, path, entry, index, mentionIndex, factIndex }))
    .filter((fact) => String(fact.text || '').trim())
  ).sort((left, right) => dateSortValue(left.date) - dateSortValue(right.date)
    || left.mentionIndex - right.mentionIndex
    || left.factIndex - right.factIndex);
}

function entityMentionDate({ doc, entry }) {
  if (entry.date || doc.date) return entry.date || doc.date;
  const dates = (Array.isArray(entry.facts) ? entry.facts : [])
    .map((fact) => factDate(fact, doc, entry))
    .filter(Boolean);
  return dates.sort((left, right) => dateSortValue(left) - dateSortValue(right))[0] || '';
}

function renderEntityFacts(mentions) {
  const facts = entityFactRecords(mentions);
  if (!facts.length) return '';
  const items = facts.map((fact, factIndex) => {
    const showDate = factIndex === 0 || fact.date !== facts[factIndex - 1].date;
    const date = showDate && fact.date
      ? `<time class="entity-fact-date" datetime="${escapeHtml(fact.date)}">${escapeHtml(formatDate(fact.date))}</time>`
      : showDate ? '<span class="entity-fact-date">Undated</span>' : '<span class="entity-fact-date" aria-hidden="true"></span>';
    return `<li>${date}<span class="entity-fact-text">${inlineMarkup(fact.text)}</span></li>`;
  }).join('');
  return `<section class="entity-facts"><h3>Facts</h3><ul class="facts">${items}</ul></section>`;
}

function renderEntityMentionsPage(entity, mentions, { kind, notFoundMessage, languageMarkup, extraMarkup } = {}) {
  if (!entity) return `<article class="document"><h2>${kind === 'place' ? 'Place' : 'Person'} not found</h2><p class="status">${notFoundMessage}</p></article>`;
  const heading = `<article class="document ${kind}-document-heading"><div class="document-heading"><div><h2>${escapeHtml(entity.name)}</h2></div><small>${mentions.length} mention${mentions.length === 1 ? '' : 's'}</small></div></article>`;
  const sortedMentions = [...mentions].sort((left, right) => dateSortValue(entityMentionDate(left)) - dateSortValue(entityMentionDate(right)) || left.index - right.index);
  const content = sortedMentions.map(({ doc, path, entry, index }) => {
    const date = entityMentionDate({ doc, entry });
    return `<article class="document ${kind}-mention" role="link" tabindex="0" data-document-href="${escapeHtml(documentNavigationUrl(path, index))}"><p class="entry-title">${markdownLinks(entry.title || documentTitle(doc, path))}</p>${date ? `<p class="entry-date">${escapeHtml(formatDate(date))}</p>` : ''}${entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry) : ''}${extraMarkup ? extraMarkup(doc, entry) : ''}</article>`;
  }).join('');
  return `${heading}${renderEntityFacts(mentions)}${content ? `<h3 class="entity-section-title">Direct quotations</h3>${content}` : '<article class="document"><p class="status">No mentions found.</p></article>'}`;
}

function renderPlacePage() {
  const place = placeForName(state.place) || state.places.find((item) => item.name.toLocaleLowerCase() === String(state.place || '').toLocaleLowerCase());
  return renderEntityMentionsPage(place, place ? placeMentions(place) : [], {
    kind: 'place',
    notFoundMessage: `No place named “${escapeHtml(state.place || '')}” is listed in data/places.json.`,
    languageMarkup: (entry) => entityLanguageMarkup(entry, buildPlacePattern([place])),
    extraMarkup: (doc, entry) => doc.place && !entry.german && !entry.latin && !entry.english ? `<p class="place-record">Document place: ${inlineMarkup(doc.place)}</p>` : '',
  });
}

function setupMentionNavigation(mentionClass, excludeSelector) {
  document.querySelectorAll(`.${mentionClass}[data-document-href]`).forEach((frame) => {
    const navigate = () => { window.location.href = frame.dataset.documentHref; };
    frame.addEventListener('click', (event) => {
      if (event.target.closest(excludeSelector)) return;
      navigate();
    });
    frame.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); navigate(); }
    });
  });
}

function personForName(name) {
  return findEntityByName(state.persons, name);
}

function personMentions(person) {
  const patterns = buildPersonPattern([person]);
  const mentions = [];
  state.documents.forEach((doc, path) => (doc.entries || []).forEach((entry, index) => {
    const fields = ['title', 'source', 'german', 'latin', 'english', 'facts'];
    if (fields.some((field) => patterns.some(({ pattern }) => (Array.isArray(entry[field]) ? entry[field].join('\n') : String(entry[field] || '')).match(pattern)))) {
      mentions.push({ doc, path, entry, index });
    }
  }));
  return mentions;
}

function renderPersonPage() {
  const person = personForName(state.person) || state.persons.find((item) => item.name.toLocaleLowerCase() === String(state.person || '').toLocaleLowerCase());
  return renderEntityMentionsPage(person, person ? personMentions(person) : [], {
    kind: 'person',
    notFoundMessage: `No person matching “${escapeHtml(state.person || '')}” is generated from data/names.md and data/places.json.`,
    languageMarkup: (entry) => entityLanguageMarkup(entry, buildPersonPattern([person])[0].pattern),
  });
}

function renderTabs() {
  const tabs = [{ path: 'books', label: 'Books' }, ...(state.manifest.notes ? [{ path: 'data/notes/notes.json', label: 'Notes' }] : []), { path: 'letters', label: 'Letters' }, { path: 'seals', label: 'Seals' }, { path: 'map', label: 'Map' }, { path: 'tree', label: 'Tree' }];
  const bookIsActive = state.active === 'books' || state.manifest.books.some((book) => book.path === state.active);
  $('#tabs').innerHTML = tabs.map((tab) => `<button class="tab ${(tab.path === 'books' ? bookIsActive : state.active === tab.path) ? 'active' : ''}" data-path="${escapeHtml(tab.path)}">${escapeHtml(tab.label)}</button>`).join('');
  $('#book-tabs').innerHTML = bookIsActive
    ? state.manifest.books.map((book) => `<button class="subtab ${state.active === book.path ? 'active' : ''}" data-path="${escapeHtml(book.path)}">${escapeHtml(book.label)}</button>`).join('')
    : '';
  document.querySelectorAll('.tab, .subtab').forEach((button) => button.addEventListener('click', () => {
    const requestedPath = button.dataset.path;
    const nextActive = requestedPath === 'books'
      ? (state.manifest.books.some((book) => book.path === state.active) ? state.active : state.manifest.books[0]?.path || 'letters')
      : requestedPath;
    if (nextActive !== state.active) {
      clearScreenCaches();
    }
    if (nextActive !== 'letters') {
      state.letterSource = null;
      state.navigationLetterSource = null;
    }
    const nextUrl = new URL(location.href);
    nextUrl.search = '';
    nextUrl.hash = '';
    if (requestedPath === 'books' || ['letters', 'seals', 'map', 'tree'].includes(nextActive)) nextUrl.searchParams.set('tab', requestedPath === 'books' ? 'books' : nextActive);
    else nextUrl.searchParams.set('document', nextActive);
    history.replaceState(null, '', `${nextUrl.pathname}${nextUrl.search}`);
    state.active = nextActive;
    state.place = null;
    state.person = null;
    savePreferences();
    renderTabs();
    renderActive();
  }));
}

function languageMarkup(entry) {
  const displayedLanguages = displayedLanguagesFor(entry);
  if (!displayedLanguages.length) return '';
  return `<div class="text-grid ${displayedLanguages.length === 1 ? 'single' : ''}">${displayedLanguages.map((language) => `<div class="language"><div class="text">${markdownMarkup(entry[language], language === 'english')}</div></div>`).join('')}</div>`;
}

function renderEntry(entry, { title = true, date = true, source = true, path = '', index = null } = {}) {
  const entryDate = date && entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : '';
  const anchor = path && index !== null ? ` id="${entryAnchor(path, index)}"` : '';
  return `<article class="entry"${anchor}>${title && entry.title ? `<p class="entry-title">${markdownLinks(entry.title)}</p>` : ''}${entryDate}${source && entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.url ? urlMarkup(entry.url) : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry) : ''}${entry.img ? imageMarkup(entry.img, [], { path, index }) : ''}${entry.diagram ? diagramMarkup(entry.diagram) : ''}${state.showFacts && entry.facts?.length ? `<ul class="facts">${entry.facts.map((fact) => `<li>${inlineMarkup(fact)}</li>`).join('')}</ul>` : ''}</article>`;
}

function bookSections(entries) {
  return entries.reduce((sections, entry) => {
    if (entry.title || !sections.length) sections.push({ title: entry.title || '', entries: [] });
    sections[sections.length - 1].entries.push(entry);
    return sections;
  }, []);
}

function renderDocument(doc, path, index) {
  const allEntries = doc.entries || [];
  const entries = state.active === 'letters' && state.letterSource
    ? allEntries.filter((entry) => entryHasSource(entry, state.letterSource))
    : allEntries;
  const title = documentTitle(doc, path);
  const date = doc.date && formatDate(doc.date) !== title ? `<small>${escapeHtml(formatDate(doc.date))}</small>` : '';
  const label = String(doc.label || '').trim();
  const headingAside = label || date ? `<div class="document-heading-aside">${label ? `<span class="letter-label">${escapeHtml(label)}</span>` : ''}${date}</div>` : '';
  const url = doc.url ? urlMarkup(doc.url) : '';
  const year = documentYear(doc);
  const anchor = year ? ` id="year-${year}-${index}"` : '';
  if (path.startsWith('data/books/') || path.startsWith('data/notes/')) {
    return bookSections(entries).map((section, sectionIndex) => {
      const sectionTitle = section.title || (sectionIndex === 0 ? title : 'Untitled section');
      const sectionContent = section.entries.map((entry) => renderEntry(entry, { title: false, path, index: entries.indexOf(entry) })).join('');
      return `<article class="document book-document"><div class="document-heading"><div><h2>${markdownLinks(sectionTitle)}</h2>${sectionIndex === 0 ? url : ''}</div>${sectionIndex === 0 ? date : ''}</div>${sectionContent}</article>`;
    }).join('');
  }
  const content = entries.map((entry) => renderEntry(entry, { path, index: allEntries.indexOf(entry) })).join('');
  const important = label.toLocaleLowerCase() === 'important' ? ' important' : '';
  const dimmed = ['hessen', 'schenk', 'mönch'].includes(label.toLocaleLowerCase()) ? ' dimmed' : '';
  return `<article class="document${important}${dimmed}"${anchor}><div class="document-heading"><div><h2>${inlineMarkup(title)}</h2>${url}</div>${headingAside}</div>${content}</article>`;
}

function letterLabelForPath(path) {
  return String(state.documents.get(path)?.label || '').trim().toLocaleLowerCase();
}

function visibleLetterPaths(paths) {
  const selected = new Set(state.letterLabels);
  const hidden = new Set(state.hiddenLetterLabels || []);
  return paths.filter((path) => {
    if (state.letterSource && !letterHasSource(path, state.letterSource)) return false;
    if (path === state.navigationLetter) return true;
    const label = letterLabelForPath(path);
    const missing = selected.has(MISSING_LETTER_LABEL) && letterHasMissingSourceOrUrl(path);
    if (hidden.has(label) && !missing) return false;
    return !selected.size || selected.has(label) || missing;
  });
}

function renderYearSidebar(paths, labelPaths = paths) {
  const years = [...new Set(paths.map((path) => documentYear(state.documents.get(path))).filter(Boolean))]
    .sort((left, right) => Number(left) - Number(right));
  const yearLinks = years.map((year) => {
    const index = paths.findIndex((path) => documentYear(state.documents.get(path)) === year);
    return `<a href="#" data-sidebar-type="year" data-path="${escapeHtml(paths[index])}">${year}</a>`;
  }).join('');
  const labels = new Map();
  labelPaths.forEach((path) => {
    const label = String(state.documents.get(path)?.label || '').trim();
    if (label && !labels.has(label.toLocaleLowerCase())) labels.set(label.toLocaleLowerCase(), { label, path });
  });
  const missingPath = labelPaths.find((path) => letterHasMissingSourceOrUrl(path));
  if (missingPath && !labels.has(MISSING_LETTER_LABEL)) labels.set(MISSING_LETTER_LABEL, { label: MISSING_LETTER_LABEL, path: missingPath });
  const labelLinks = [...labels.values()]
    .sort((left, right) => left.label.localeCompare(right.label, undefined, { sensitivity: 'base' }))
    .map(({ label, path }) => {
      const key = label.toLocaleLowerCase();
      const selected = GREY_LETTER_LABELS.has(key) ? state.hiddenLetterLabels.includes(key) : state.letterLabels.includes(key);
      return `<a href="#" class="${selected ? 'selected' : ''}" data-sidebar-type="label" data-label="${escapeHtml(key)}" data-path="${escapeHtml(path)}">${escapeHtml(label)}</a>`;
    })
    .join('');
  if (!yearLinks && !labelLinks) return '';
  return `${yearLinks ? `<aside class="year-sidebar" aria-label="Letters by year"><nav>${yearLinks}</nav></aside>` : ''}${labelLinks ? `<aside class="label-sidebar" aria-label="Letters by label"><nav>${labelLinks}</nav></aside>` : ''}`;
}

function setupYearHighlight(paths) {
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  const links = [...document.querySelectorAll('.year-sidebar a, .label-sidebar a')];
  const targets = paths
    .map((path, index) => ({ path, element: document.querySelector(`#year-${documentYear(state.documents.get(path))}-${index}`) }))
    .filter(({ element }) => element);
  if (!links.length || !targets.length) return;
  let selectedLink = null;

  links.forEach((link) => link.addEventListener('click', (event) => {
    event.preventDefault();
    if (link.dataset.sidebarType === 'label') {
      const label = link.dataset.label;
      const values = GREY_LETTER_LABELS.has(label) ? state.hiddenLetterLabels : state.letterLabels;
      const index = values.indexOf(label);
      if (index >= 0) values.splice(index, 1);
      else values.push(label);
      savePreferences();
      renderActive();
      return;
    }
    const target = targets.find((item) => item.path === link.dataset.path);
    if (!target) return;
    state.letter = target.path;
    savePreferences();
    window.scrollTo(0, target.element.getBoundingClientRect().top + window.scrollY - 104);
  }));

  const update = () => {
    const marker = window.scrollY + 160;
    let current = targets[0];
    targets.forEach((target) => {
      if (target.element.getBoundingClientRect().top + window.scrollY <= marker) current = target;
    });
    state.letter = current.path;
    savePreferences();
    const year = current.element.id.match(/^year-(\d{4})-/)?.[1];
    const currentLabel = String(state.documents.get(current.path)?.label || '').trim().toLocaleLowerCase();
    links.forEach((link) => {
      const active = link.dataset.sidebarType === 'year'
        ? link.textContent === year
        : link.dataset.label === currentLabel || (link.dataset.label === MISSING_LETTER_LABEL && letterHasMissingSourceOrUrl(current.path));
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
      if (active && link !== selectedLink) {
        link.scrollIntoView({ block: 'nearest' });
        selectedLink = link;
      }
    });
  };

  window.addEventListener('scroll', update, { passive: true });
  state.yearHighlightCleanup = () => window.removeEventListener('scroll', update);
  update();
}

function restoreLetter(paths) {
  const index = paths.indexOf(state.letter);
  if (index < 0) return;
  const target = document.querySelector(`#year-${documentYear(state.documents.get(state.letter))}-${index}`);
  if (target) window.scrollTo(0, target.getBoundingClientRect().top + window.scrollY - 104);
}

function scrollToEntryHash() {
  const hash = decodeURIComponent(location.hash.slice(1));
  if (!hash) return;
  const target = document.getElementById(hash);
  if (target) target.scrollIntoView({ block: 'start' });
}

async function renderActive() {
  $('#status').textContent = '';
  $('#status').classList.remove('error');
  state.sealMarkerCleanup?.();
  state.sealMarkerCleanup = null;
  if (leafletMap && state.active !== 'map') { leafletMap.remove(); leafletMap = null; }
  if (state.person) {
    $('#content').innerHTML = renderPersonPage();
    setupMentionNavigation('person-mention', 'a.place-link, a.person-link');
    return;
  }
  if (state.place) {
    $('#content').innerHTML = renderPlacePage();
    setupMentionNavigation('place-mention', 'a.place-link');
    return;
  }
  state.sealHighlightCleanup?.();
  state.sealHighlightCleanup = null;
  if (state.active === 'seals') {
    $('#status').textContent = '';
    $('#content').innerHTML = renderSealsPage();
    const allEntries = letterSealEntries().sort((left, right) => sealSortYear(left) - sealSortYear(right) || left.title.localeCompare(right.title));
    const selectedNames = new Set(state.sealNames);
    const entries = allEntries.filter((entry) => (!selectedNames.size || sealMatchesSelected(entry.title, selectedNames)) && sealMatchesType(entry, state.sealType));
    setupSealHighlight(entries);
    setupSealAnnotations();
    return;
  }
  if (state.active === 'tree') {
    $('#content').innerHTML = peopleTreeMarkup(state.personRecords);
    return;
  }
  if (state.active === 'map') {
    $('#content').innerHTML = renderMapPage();
    setupMap();
    return;
  }
  const allLetterPaths = state.manifest.letters;
  const paths = state.active === 'letters' ? visibleLetterPaths(allLetterPaths) : [state.active];
  const selectedYear = documentYear(state.documents.get(state.letter));
  const shouldRestoreLetter = state.active === 'letters'
    && selectedYear
    && (state.lastRenderedLettersYear === null || selectedYear !== state.lastRenderedLettersYear);
  $('#status').textContent = '';
  state.yearHighlightCleanup?.();
  state.yearHighlightCleanup = null;
  if (state.active === 'letters') {
    $('#content').innerHTML = `<div class="letters-layout">${renderYearSidebar(paths, state.letterSource ? paths : allLetterPaths)}<div class="letters-list">${paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('')}</div></div>`;
  } else {
    $('#content').innerHTML = paths.map((path, index) => renderDocument(state.documents.get(path), path, index)).join('');
  }
  setupSealAnnotations();
  const diagrams = $('#content').querySelectorAll('.mermaid');
  if (diagrams.length && typeof mermaid !== 'undefined') await mermaid.run({ nodes: diagrams });
  if (state.active === 'letters') {
    if (shouldRestoreLetter) restoreLetter(paths);
    setupYearHighlight(paths);
    state.lastRenderedLettersYear = documentYear(state.documents.get(state.letter));
  }
  scrollToEntryHash();
}

async function loadAll() {
  const files = await getRepositoryFiles();
  const paths = files.map((file) => typeof file === 'string' ? file : file.path);
  const snapshot = JSON.stringify(files);
  const [placesText, calibrationCitiesText, peopleText, namesText, documents] = await Promise.all([
    getText('data/places.json'),
    getText('docs/assets/calibration-cities.json'),
    getText('data/people.json'),
    getText('data/names.md'),
    new Map(await Promise.all(paths.map(async (path) => [path, await getJson(path)]))),
  ]);
  state.places = parsePlaces(placesText);
  state.calibrationCities = parsePlaces(calibrationCitiesText);
  state.personRecords = JSON.parse(peopleText);
  state.people = parsePeople(peopleText, namesText, state.places);
  state.persons = state.people;
  state.personPattern = buildPersonPattern(state.persons);
  state.placePattern = buildPlacePattern(state.places);
  const bookPaths = paths
    .filter((path) => path.startsWith('data/books/'))
    .sort((left, right) => bookSortYear(documents.get(right), right) - bookSortYear(documents.get(left), left) || left.localeCompare(right));
  const letterPaths = paths.filter((path) => path.startsWith('data/letters/'));
  const manifest = {
    books: bookPaths.map((path) => ({ path, label: documents.get(path)?.book || path })),
    notes: paths.includes('data/notes/notes.json'),
    letters: letterPaths,
  };
  state.manifest = manifest; state.documents = documents; state.snapshot = snapshot;
  if (!letterPaths.some((path) => letterHasMissingSourceOrUrl(path))) state.letterLabels = state.letterLabels.filter((label) => label !== MISSING_LETTER_LABEL);
  if (!Array.isArray(state.hiddenLetterLabels)) state.hiddenLetterLabels = [...GREY_LETTER_LABELS];
  state.sealNames = [...new Set(state.sealNames.map(normalizeSealFilter).filter(Boolean))];
  if (state.active === 'books') state.active = manifest.books[0]?.path || 'letters';
  if (state.active !== 'letters' && state.active !== 'seals' && state.active !== 'tree' && state.active !== 'map' && !paths.includes(state.active)) state.active = manifest.books[0]?.path || 'letters';
  savePreferences();
  renderTabs(); await renderActive();
}

async function refreshIfChanged() {
  if ($('#image-lightbox')?.open) return;
  try {
    const files = await getRepositoryFiles();
    if ($('#image-lightbox')?.open) return;
    if (JSON.stringify(files) !== state.snapshot) await loadAll();
  } catch (error) {
    // A temporary network failure should not interrupt the next refresh attempt.
    console.warn('Could not check for data updates:', error);
  }
}

const languageToggle = $('#language-toggle');
updateLanguageControl();
updateFactsControl();
languageToggle.addEventListener('click', () => {
  state.language = state.language === 'english' ? 'original' : 'english';
  updateLanguageControl();
  savePreferences();
  renderActive();
});
const factsToggle = $('#facts-toggle');
factsToggle.addEventListener('click', () => {
  state.showFacts = !state.showFacts;
  updateFactsControl();
  savePreferences();
  renderActive();
});
const themeToggle = $('#theme-toggle');
themeToggle.addEventListener('click', () => {
  state.darkMode = !state.darkMode;
  applyTheme();
  applyMermaidTheme();
  savePreferences();
  renderActive();
});

setupImageLightbox();

async function getText(path) {
  const parts = location.pathname.split('/').filter(Boolean);
  const owner = location.hostname.split('.')[0];
  const repository = parts[0];
  const dataPath = location.hostname.endsWith('github.io')
    ? `https://raw.githubusercontent.com/${owner}/${repository}/main/${path}`
    : `../${path}`;
  const response = await fetch(`${dataPath}?v=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.text();
}
loadAll().catch((error) => {
  $('#status').textContent = `Could not load data: ${error.message}`;
  $('#status').classList.add('error');
});

setInterval(refreshIfChanged, REFRESH_INTERVAL);
