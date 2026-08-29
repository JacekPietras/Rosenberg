import { escapeHtml, urlMarkup } from './rendering/html.js';
import { formatDate, dateSortValue } from './rendering/dates.js';
import { renderPeopleTree } from './screens/tree.js';
import { renderActiveScreen } from './screens/router-view.js';
import { createDocumentRenderer } from './screens/documents.js';
import { parsePlaces, buildPlacePattern, parsePeople, buildPersonPattern } from './data/entities.js';
import { createSealScreen } from './screens/seals.js';
import { createDataLoader } from './data/loader.js';
import { createEntityScreens } from './screens/entities.js';
import { createTabs } from './components/tabs.js';
import { setupControls } from './components/controls.js';
import { setupSealAnnotations as setupImageSealAnnotations, positionSealCrop as positionImageSealCrop } from './components/seal-annotations.js';
import { createMapScreen } from './screens/map.js';
import { setupImageLightbox as setupImageLightboxComponent } from './components/image-lightbox.js';
import { createMarkupRenderer } from './rendering/markup.js';
import { createImageRenderer } from './rendering/images.js';
import { documentTitle, documentYear, bookSortYear } from './rendering/document-meta.js';
import { createLanguageRenderer } from './rendering/languages.js';
import { createCitationIndex } from './data/citations.js';
import { entryAnchor, documentNavigationUrl } from './rendering/navigation.js';
import { hrrBuildWarp as buildMapWarp, hrrBuildInverseWarp as buildInverseMapWarp, hrrCalibrationKeys as mapCalibrationKeys, HRR_MAP_NATIVE_WIDTH as mapNativeWidth, HRR_MAP_NATIVE_HEIGHT as mapNativeHeight } from './map/warp.js';

export function startViewer({ store, repository, preferences, savePreferences: persistPreferences }) {
function savePreferences() {
  persistPreferences({
    active: state.active,
    place: state.place,
    person: state.person,
    letter: state.letter,
    letterLabels: state.letterLabels,
    hiddenLetterLabels: state.hiddenLetterLabels,
    sealNames: state.sealNames,
    sealType: state.sealType,
    language: state.language,
    showFacts: state.showFacts,
    darkMode: state.darkMode,
  });
}
const state = { manifest: null, active: preferences.active, place: preferences.place, person: preferences.person, letter: preferences.letter, letterSource: null, navigationLetter: null, navigationLetterSource: null, letterLabels: preferences.letterLabels, hiddenLetterLabels: preferences.hiddenLetterLabels, sealNames: preferences.sealNames, sealType: preferences.sealType, language: preferences.language, showFacts: preferences.showFacts, darkMode: preferences.darkMode, documents: new Map(), people: [], personRecords: [], places: [], calibrationCities: [], personPattern: null, placePattern: null, snapshot: '', yearHighlightCleanup: null, sealHighlightCleanup: null, sealMarkerCleanup: null, lastRenderedLettersYear: null };
const route = store?.getState?.().route || { active: 'books' };
store?.setState(state);
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

if (route.document || route.tab || route.letter) { state.place = null; state.person = null; }
if (route.active) state.active = route.active;
if (route.letter) {
  state.letter = route.letter;
  state.navigationLetter = state.letter;
}
if (route.source) {
  state.letterSource = route.source;
  state.navigationLetterSource = state.letterSource;
}
if (route.place) { state.place = route.place; state.person = null; }
if (route.person) { state.person = route.person; state.place = null; }
const requestedScreen = route.tab || route.document;
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

function linkedMarkup(value = '', linkEntities = true) {
  if (!linkEntities) return String(value);
  const tokens = [];
  const token = (markup) => { const key = `\u0000${tokens.length}\u0000`; tokens.push(markup); return key; };
  let text = String(value);
  for (const { pattern, people } of state.personPattern || []) text = text.replace(pattern, (match) => {
    const person = people.find((item) => item.name.toLocaleLowerCase() === match.toLocaleLowerCase());
    if (!person) return match;
    const query = encodeURIComponent(person.name);
    return token(`<a class="person-link" href="?person=${query}">${match}</a>`);
  });
  if (state.placePattern) text = text.replace(state.placePattern, (match) => {
    const place = state.places.find((item) => item.name.toLocaleLowerCase() === match.toLocaleLowerCase());
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

function diagramMarkup(value = '') {
  const source = String(value).replace(/^\s*```mermaid\s*\n?/, '').replace(/\n?\s*```\s*$/, '').trim();
  return source ? `<div class="diagram mermaid">${escapeHtml(source)}</div>` : '';
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
  { id: '1400', label: '1400', image: 'assets/Germany_1400_map.jpg', width: mapNativeWidth, height: mapNativeHeight, credit: HRR_1400_CREDIT_HTML },
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
      const { x: keyX, y: keyY } = mapCalibrationKeys(mapDef);
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
      await repository.saveDocument('docs/assets/calibration-cities.json', calibrationCitiesForSave());
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
  const inverse = buildInverseMapWarp(calibrationCities, mapDef);
  return corners.map(({ lat, lng }) => inverse.latLonForPixel(lng, mapDef.height - lat));
}

function hrrLatLonCornersToView(corners, mode, calibrationCities) {
  if (mode === 'live') {
    const lats = corners.map((p) => p.lat), lons = corners.map((p) => p.lon);
    return [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
  }
  const mapDef = HRR_MAPS_BY_ID.get(mode);
  const warp = buildMapWarp(calibrationCities, mapDef);
  const pixels = corners.map(({ lat, lon }) => warp.pixelForLatLon(lat, lon));
  const xs = pixels.map((p) => p.x), ys = pixels.map((p) => p.y);
  return [[mapDef.height - Math.max(...ys), Math.min(...xs)], [mapDef.height - Math.min(...ys), Math.max(...xs)]];
}

// Small circular "point" marker (not the usual pin) for calibration reference cities, so they
// read as reference data rather than genealogy content. Uses a real L.marker (not L.circleMarker)
// specifically so Leaflet's built-in drag support is available when MAP_CALIBRATION_EDITABLE
// flips on — Leaflet's Path-based circle markers can't be made draggable.
const HRR_CALIBRATION_POINT_ICON = L.divIcon({ className: 'calibration-point-icon', iconSize: [10, 10] });

const PLACE_MARKER_ICONS = {
  castle: '<path d="M4 27V11h4V7h4v4h4V7h4v4h4v16H4Zm4-4h3v-5H8v5Zm5 0h3v-5h-3v5Zm5 0h3v-5h-3v5ZM3 29h22v2H3v-2Z"/><path d="M13 2h2v5h-2V2Zm-3 2h8v2h-8V4Z"/>',
  church: '<path d="M13 2h2v5h-2V2Zm-3 2h8v2h-8V4Zm-2 7h12l-2 3v15H8V14l-2-3h2Zm2 5v8h3v-8h-3Zm6 0v8h2v-8h-2Z"/><path d="M4 29h16v2H4v-2Z"/>',
  city: '<path d="M4 6h7v5h9v20H4V6Zm3 3v4h2V9H7Zm0 8v3h2v-3H7Zm0 7v3h2v-3H7Zm5-10v3h5v-3h-5Zm0 7v3h5v-3h-5Zm0 7v3h5v-3h-5Z"/>'
};

function placeMarkerIcon(place) {
  const category = typeof place.category === 'string' ? place.category.toLocaleLowerCase() : '';
  const path = PLACE_MARKER_ICONS[category];
  if (!path) return undefined;
  return L.divIcon({
    className: `place-marker-icon place-marker-icon-${category}`,
    html: `<svg viewBox="0 0 28 34" aria-hidden="true"><path class="place-marker-shadow" d="M14 33C14 33 3 21 3 13a11 11 0 1 1 22 0c0 8-11 20-11 20Z"/><g class="place-marker-glyph">${path}</g></svg>`,
    iconSize: [28, 34],
    iconAnchor: [14, 33],
    popupAnchor: [0, -33],
  });
}

function placeMarkerOptions(place) {
  const icon = placeMarkerIcon(place);
  return icon ? { icon } : {};
}

function renderMapLayer(container, places, calibrationCities, previousView) {
  if (leafletMap) { leafletMap.remove(); leafletMap = null; }
  const carriedCorners = previousView ? hrrViewCornersToLatLon(previousView.mode, previousView.bounds, calibrationCities) : null;

  const mapDef = HRR_MAPS_BY_ID.get(mapMode);
  if (mapDef) {
    const bounds = [[0, 0], [mapDef.height, mapDef.width]];
    leafletMap = L.map(container, { crs: L.CRS.Simple, scrollWheelZoom: true, minZoom: -10, maxZoom: 10, zoomSnap: 1 });
    L.imageOverlay(mapDef.image, bounds).addTo(leafletMap);
    leafletMap.setMaxBounds(L.latLngBounds(bounds).pad(0.5));
    const warp = buildMapWarp(calibrationCities, mapDef);
    places.forEach((place) => {
      const { x, y } = warp.pixelForLatLon(place.lat, place.lon);
      const marker = L.marker([mapDef.height - y, x], placeMarkerOptions(place)).addTo(leafletMap);
      const query = encodeURIComponent(place.name);
      marker.bindPopup(`<a class="place-link" href="?place=${query}">${escapeHtml(place.name)}</a>`);
    });
    if (MAP_CALIBRATION_EDITABLE) {
      const { x: keyX, y: keyY } = mapCalibrationKeys(mapDef);
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
    const marker = L.marker([place.lat, place.lon], placeMarkerOptions(place)).addTo(leafletMap);
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

document.addEventListener('error', (event) => {
  const image = event.target;
  if (!(image instanceof HTMLImageElement)) return;
  const fallback = image.dataset.fallbackSrc;
  if (!fallback || image.src === fallback) return;
  image.removeAttribute('data-fallback-src');
  image.src = fallback;
}, true);

function setupImageLightboxLegacy() {
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
      positionImageSealCrop(sealPreviewImage, sealPreviewCrop, x, y, size, width, wideningRotation, rotation);
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
        await repository.saveDocument(context.path, state.documents.get(context.path));
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
  return repository.getJson(path);
}

async function getRepositoryFiles() {
  return repository.getRepositoryFiles();
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

const tabs = createTabs({
  state,
  escapeHtml,
  clearScreenCaches,
  savePreferences,
  rerender: renderActive,
});

function renderTabs() {
  tabs.render();
}

function letterLabelForPath(path) {
  return String(state.documents.get(path)?.label || '').trim().toLocaleLowerCase();
}

function visibleLetterPaths(paths) {
  const selected = new Set(state.letterLabels);
  const hidden = new Set(state.hiddenLetterLabels || []);
  return paths.filter((path) => {
    if (state.letterSource && !citationIndex.letterHasSource(path, state.letterSource)) return false;
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

const markupRenderer = createMarkupRenderer({ state });
const citationIndex = createCitationIndex({ state });
const imageRenderer = createImageRenderer();
const languageRenderer = createLanguageRenderer({ state, markdownMarkup: markupRenderer.markdownMarkup });
const documentRenderer = createDocumentRenderer({
  state,
  formatDate,
  escapeHtml,
  markdownLinks: markupRenderer.markdownLinks,
  inlineMarkup: markupRenderer.inlineMarkup,
  urlMarkup,
  languageMarkup: languageRenderer.languageMarkup,
  imageMarkup: imageRenderer,
  diagramMarkup: markupRenderer.diagramMarkup,
  entryAnchor,
  entryHasSource: citationIndex.entryHasSource,
  documentTitle,
  documentYear,
});

const sealScreen = createSealScreen({
  state,
  formatDate,
  escapeHtml,
  urlMarkup,
  markdownLinks: markupRenderer.markdownLinks,
  imageMarkup: imageRenderer,
  letterForSource: citationIndex.letterForSource,
  sourceCitations: citationIndex.sourceCitations,
  entryAnchor,
  getDocuments: () => state.documents,
  savePreferences,
  rerender: renderActive,
});

const entityScreens = createEntityScreens({
  state,
  getDocuments: () => state.documents,
  getPlaces: () => state.places,
  getPeople: () => state.people,
  buildPlacePattern,
  buildPersonPattern,
  escapeHtml,
  inlineMarkup: markupRenderer.inlineMarkup,
  markdownLinks: markupRenderer.markdownLinks,
  formatDate,
  dateSortValue,
  documentTitle,
  documentNavigationUrl,
  displayedLanguagesFor: languageRenderer.displayedLanguagesFor,
});

const mapScreen = createMapScreen({
  state,
  escapeHtml,
  getMap: () => leafletMap,
  setMap: (map) => { leafletMap = map; },
  saveCalibrationCities,
});

async function renderActive() {
  return renderActiveScreen({
    state,
    content: $('#content'),
    status: $('#status'),
    leafletMap,
    destroyMap: () => { leafletMap?.remove(); leafletMap = null; },
    renderPersonPage: entityScreens.renderPersonPage,
    renderPlacePage: entityScreens.renderPlacePage,
    renderSealsPage: sealScreen.renderSealsPage,
    letterSealEntries: sealScreen.letterSealEntries,
    sealSortYear: sealScreen.sealSortYear,
    sealMatchesSelected: sealScreen.sealMatchesSelected,
    sealMatchesType: sealScreen.sealMatchesType,
    renderPeopleTree,
    renderMapPage: mapScreen.renderMapPage,
    setupMap: mapScreen.setupMap,
    visibleLetterPaths,
    documentYear,
    renderYearSidebar,
    renderDocument: documentRenderer.renderDocument,
    setupSealAnnotations: () => setupImageSealAnnotations({ state }),
    setupSealHighlight: sealScreen.setupSealHighlight,
    restoreLetter,
    setupYearHighlight,
    scrollToEntryHash,
    setupMentionNavigation,
    mermaid: typeof mermaid === 'undefined' ? null : mermaid,
  });
}

async function loadAllLegacy() {
  const files = await getRepositoryFiles();
  const paths = files.map((file) => typeof file === 'string' ? file : file.path);
  const snapshot = JSON.stringify(files);
  const [placesText, calibrationCitiesText, peopleText, documents] = await Promise.all([
    getText('data/places.json'),
    getText('docs/assets/calibration-cities.json'),
    getText('data/people.json'),
    new Map(await Promise.all(paths.map(async (path) => [path, await getJson(path)]))),
  ]);
  state.places = parsePlaces(placesText);
  state.calibrationCities = parsePlaces(calibrationCitiesText);
  state.personRecords = JSON.parse(peopleText);
  state.people = parsePeople(peopleText);
  state.personPattern = buildPersonPattern(state.people);
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

const dataLoader = createDataLoader({
  repository,
  state,
  parsePlaces,
  parsePeople,
  buildPlacePattern,
  buildPersonPattern,
  bookSortYear,
  letterHasMissingSourceOrUrl,
  missingLetterLabel: MISSING_LETTER_LABEL,
  greyLetterLabels: GREY_LETTER_LABELS,
  savePreferences,
  renderTabs,
  renderActive,
});

async function loadAll() {
  return dataLoader.loadAll();
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

setupControls({ state, updateLanguageControl, updateFactsControl, applyTheme, applyMermaidTheme, savePreferences, rerender: renderActive });

setupImageLightboxComponent({ state, repository, rerender: renderActive });

async function getText(path) {
  return repository.getText(path);
}
loadAll().catch((error) => {
  $('#status').textContent = `Could not load data: ${error.message}`;
  $('#status').classList.add('error');
});

setInterval(refreshIfChanged, REFRESH_INTERVAL);
}
