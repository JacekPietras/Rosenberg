import {
  HRR_MAP_NATIVE_WIDTH,
  HRR_MAP_NATIVE_HEIGHT,
  hrrCalibrationKeys,
  hrrBuildWarp,
  hrrBuildInverseWarp,
} from '../map/warp.js';

const HRR_MAPS = [
  { id: '1378', label: '1378', image: 'assets/Germany_1378_map.jpg', width: 3215, height: 2514, credit: 'Historical base map: "Germany at the death of Emperor Charles IV, 1378," revised by Karl Wolf, from H.F. Helmolt\'s <a href="https://pl.wikipedia.org/wiki/Plik:Germany_1378_map.jpg" target="_blank" rel="noreferrer">History of the World</a>, Vol. VII (Dodd Mead, 1902). Public domain in the United States. Place positions are approximate.' },
  { id: '1400', label: '1400', image: 'assets/Germany_1400_map.jpg', width: HRR_MAP_NATIVE_WIDTH, height: HRR_MAP_NATIVE_HEIGHT, credit: 'Historical base map: <a href="https://commons.wikimedia.org/wiki/File:HRR_1400.png" target="_blank" rel="noreferrer">Das Heilige Römische Reich um 1400</a> by Ziegelbrenner, <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noreferrer">CC BY-SA 3.0</a>, via Wikimedia Commons. Place positions are approximate.' },
];

const PLACE_ICONS = new Set(['castle', 'church', 'city', 'village']);

function normalize(value) {
  return String(value || '').replace(/[ßſ]/g, (character) => character === 'ß' ? 'ss' : 's')
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/[^a-z0-9]+/g, '');
}

function yearRange(value) {
  const years = String(value || '').match(/\d{4}/g)?.map(Number) || [];
  return years.length ? [Math.min(...years), Math.max(...years)] : null;
}

function factsForPlace(documents, place) {
  const variants = (place.variations || [place.name]).map((name) => (String(name).match(/[\p{L}\p{N}]+/gu) || []).map(normalize)).filter((tokens) => tokens.length);
  const dates = [];
  const visit = (value, inheritedDate = '') => {
    if (Array.isArray(value)) { value.forEach((child) => visit(child, inheritedDate)); return; }
    if (!value || typeof value !== 'object') return;
    const date = value.date || inheritedDate;
    const metadata = ['place', 'title', 'name', 'label'].map((key) => value[key]).join(' ');
    const metadataTokens = metadata.match(/[\p{L}\p{N}]+/gu) || [];
    const facts = Array.isArray(value.facts) ? value.facts : [];
    for (const fact of facts) {
      const text = typeof fact === 'string' ? fact : fact?.text || '';
      const tokens = text.match(/[\p{L}\p{N}]+/gu) || [];
      const available = new Set([...tokens, ...metadataTokens].map(normalize));
      const matches = variants.some((variant) => variant.every((token) => available.has(token)));
      const range = yearRange(typeof fact === 'object' && fact?.date ? fact.date : date);
      if (matches && range) dates.push(range);
    }
    for (const [key, child] of Object.entries(value)) {
      if (key !== 'facts' && child && typeof child === 'object') visit(child, date);
    }
  };
  documents.forEach((document) => visit(document));
  return dates;
}

function placeMatchesYears(place, years, from, to) {
  return place._factYears.some(([start, end]) => start <= to && end >= from);
}

export function createMapScreen({ state, escapeHtml, getMap, setMap, saveCalibrationCities }) {
  let mapMode = '1378';
  let selectedFrom = null;
  let selectedTo = null;
  let yearBounds = { min: 1200, max: 1700 };
  const mapEditable = !location.hostname.endsWith('github.io');
  const calibrationEditable = false;
  const mapById = new Map(HRR_MAPS.map((map) => [map.id, map]));
  const calibrationIcon = typeof L === 'undefined' ? null : L.divIcon({ className: 'calibration-point-icon', iconSize: [10, 10] });

  function renderMapPage() {
    const buttons = [{ id: 'live', label: 'Current' }, ...HRR_MAPS.map((map) => ({ id: map.id, label: map.label }))]
      .map(({ id, label }) => `<button type="button" class="map-mode-button" data-map-mode="${id}" aria-pressed="${mapMode === id}">${escapeHtml(label)}</button>`).join('');
    return `<div class="map-wrap"><div id="map-container" class="map-container" role="application" aria-label="Map of places"></div><div id="map-mode-switch" class="map-mode-switch" role="group" aria-label="Map version">${buttons}</div><span id="map-save-status" class="map-save-status status" aria-live="polite"></span><div class="map-credit-wrap"><button id="map-credit-toggle" class="map-credit-toggle" type="button" aria-label="Show map copyright and credit" title="Map copyright and credit" aria-expanded="false" aria-controls="map-credit"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></svg></button><p id="map-credit" class="map-credit" hidden>${mapById.get(mapMode)?.credit || ''}</p></div></div><div id="map-year-filter" class="map-year-filter"><output id="map-year-from-label">From ${selectedFrom ?? yearBounds.min}</output><div class="map-year-slider" role="group" aria-label="Filter places by years"><label class="visually-hidden" for="map-year-from">From year</label><input id="map-year-from" type="range" min="${yearBounds.min}" max="${yearBounds.max}" value="${selectedFrom ?? yearBounds.min}"><label class="visually-hidden" for="map-year-to">To year</label><input id="map-year-to" type="range" min="${yearBounds.min}" max="${yearBounds.max}" value="${selectedTo ?? yearBounds.max}"></div><output id="map-year-to-label">To ${selectedTo ?? yearBounds.max}</output></div>`;
  }

  function viewCornersToLatLon(mode, bounds, calibrationCities) {
    const corners = [bounds.getSouthWest(), bounds.getNorthEast(), bounds.getNorthWest(), bounds.getSouthEast()];
    if (mode === 'live') return corners.map(({ lat, lng }) => ({ lat, lon: lng }));
    const map = mapById.get(mode);
    const inverse = hrrBuildInverseWarp(calibrationCities, map);
    return corners.map(({ lat, lng }) => inverse.latLonForPixel(lng, map.height - lat));
  }

  function latLonCornersToView(corners, mode, calibrationCities) {
    if (mode === 'live') {
      const lats = corners.map((point) => point.lat), lons = corners.map((point) => point.lon);
      return [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]];
    }
    const map = mapById.get(mode);
    const warp = hrrBuildWarp(calibrationCities, map);
    const pixels = corners.map(({ lat, lon }) => warp.pixelForLatLon(lat, lon));
    const xs = pixels.map((point) => point.x), ys = pixels.map((point) => point.y);
    return [[map.height - Math.max(...ys), Math.min(...xs)], [map.height - Math.min(...ys), Math.max(...xs)]];
  }

  function markerOptions(place) {
    const category = typeof place.category === 'string' ? place.category.toLocaleLowerCase() : '';
    if (!PLACE_ICONS.has(category)) return {};
    const iconUrl = new URL(`../map/icon/${category}.svg?v=10`, import.meta.url).href;
    const size = ['city', 'village'].includes(category) ? 60 : 30;
    const html = `<span class="map-place-icon-art" style="width:${size}px;height:${size}px"><img class="map-place-icon-image" src="${iconUrl}" alt=""></span><span class="map-place-label">${escapeHtml(place.name)}</span>`;
    return { icon: L.divIcon({ className: `map-place-icon map-place-icon-${category}`, html, iconSize: [size, size + 12], iconAnchor: [size / 2, size], popupAnchor: [0, -size] }) };
  }

  function linkPlaceOnClick(marker, place) {
    marker.on('click', () => {
      window.location.href = `?place=${encodeURIComponent(place.name)}`;
    });
    return marker;
  }

  function renderLayer(container, places, calibrationCities, previousView) {
    getMap()?.remove();
    setMap(null);
    const carriedCorners = previousView ? viewCornersToLatLon(previousView.mode, previousView.bounds, calibrationCities) : null;
    const map = mapById.get(mapMode);
    if (map) {
      const bounds = [[0, 0], [map.height, map.width]];
      const leafletMap = L.map(container, { crs: L.CRS.Simple, scrollWheelZoom: true, minZoom: -10, maxZoom: 10, zoomSnap: 1 });
      setMap(leafletMap);
      L.imageOverlay(map.image, bounds).addTo(leafletMap);
      leafletMap.setMaxBounds(L.latLngBounds(bounds).pad(0.5));
      const warp = hrrBuildWarp(calibrationCities, map);
      places.forEach((place) => {
        const point = warp.pixelForLatLon(place.lat, place.lon);
        linkPlaceOnClick(L.marker([map.height - point.y, point.x], markerOptions(place)).addTo(leafletMap), place);
      });
      if (calibrationEditable) {
        const { x: keyX, y: keyY } = hrrCalibrationKeys(map);
        calibrationCities.forEach((city) => {
          const point = warp.pixelForLatLon(city.lat, city.lon);
          const marker = L.marker([map.height - point.y, point.x], { icon: calibrationIcon, draggable: mapEditable && calibrationEditable }).addTo(leafletMap);
          marker.bindPopup(escapeHtml(city.name));
          if (mapEditable && calibrationEditable) marker.on('dragend', () => {
            const position = marker.getLatLng();
            city[keyX] = position.lng;
            city[keyY] = map.height - position.lat;
            saveCalibrationCities();
          });
        });
      }
      leafletMap.fitBounds(carriedCorners ? latLonCornersToView(carriedCorners, mapMode, calibrationCities) : bounds);
      return;
    }
    const leafletMap = L.map(container, { scrollWheelZoom: true });
    setMap(leafletMap);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors', maxZoom: 18 }).addTo(leafletMap);
    const markers = places.map((place) => linkPlaceOnClick(L.marker([place.lat, place.lon], markerOptions(place)).addTo(leafletMap), place));
    if (carriedCorners) leafletMap.fitBounds(latLonCornersToView(carriedCorners, 'live', calibrationCities));
    else if (markers.length) leafletMap.fitBounds(L.featureGroup(markers).getBounds(), { padding: [40, 40] });
    else leafletMap.setView([49, 9], 6);
  }

  function setupMap() {
    const container = document.querySelector('#map-container');
    const records = [...state.documents.values()];
    const placesWithDates = state.places.map((place) => ({ ...place, _factYears: factsForPlace(records, place) }));
    const ranges = placesWithDates.flatMap((place) => place._factYears);
    yearBounds = ranges.length ? { min: Math.min(...ranges.map(([start]) => start)), max: Math.max(...ranges.map(([, end]) => end)) } : { min: 1200, max: 1700 };
    selectedFrom ??= yearBounds.min;
    selectedTo ??= yearBounds.max;
    for (const [id, value] of [['map-year-from', selectedFrom], ['map-year-to', selectedTo]]) {
      const input = document.querySelector(`#${id}`);
      if (input) { input.min = yearBounds.min; input.max = yearBounds.max; input.value = value; }
    }
    const yearSlider = document.querySelector('.map-year-slider');
    let places = placesWithDates.filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lon) && placeMatchesYears(place, yearBounds, selectedFrom, selectedTo));
    const updatePlaces = () => {
      const fromInput = document.querySelector('#map-year-from'), toInput = document.querySelector('#map-year-to');
      if (!fromInput || !toInput) return;
      selectedFrom = Number(fromInput.value); selectedTo = Number(toInput.value);
      if (selectedFrom > selectedTo) {
        if (document.activeElement === fromInput) toInput.value = String(selectedFrom);
        else fromInput.value = String(selectedTo);
        selectedFrom = Number(fromInput.value); selectedTo = Number(toInput.value);
      }
      document.querySelector('#map-year-from-label').textContent = `From ${selectedFrom}`;
      document.querySelector('#map-year-to-label').textContent = `To ${selectedTo}`;
      const span = yearBounds.max - yearBounds.min || 1;
      yearSlider.style.setProperty('--from', `${(selectedFrom - yearBounds.min) / span * 100}%`);
      yearSlider.style.setProperty('--to', `${(selectedTo - yearBounds.min) / span * 100}%`);
      const oldMap = getMap();
      const previousView = oldMap ? { mode: mapMode, bounds: oldMap.getBounds() } : null;
      places = placesWithDates.filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lon) && placeMatchesYears(place, yearBounds, selectedFrom, selectedTo));
      if (container && typeof L !== 'undefined') renderLayer(container, places, calibrationCities, previousView);
    };
    document.querySelector('#map-year-from')?.addEventListener('input', updatePlaces);
    document.querySelector('#map-year-to')?.addEventListener('input', updatePlaces);
    const calibrationCities = state.calibrationCities.filter((city) => Number.isFinite(city.lat) && Number.isFinite(city.lon));
    updatePlaces();
    document.querySelector('#map-credit-toggle')?.addEventListener('click', (event) => {
      const button = event.currentTarget;
      const credit = document.querySelector('#map-credit');
      credit.hidden = !credit.hidden;
      button.setAttribute('aria-expanded', String(!credit.hidden));
    });
    const modeSwitch = document.querySelector('#map-mode-switch');
    modeSwitch?.addEventListener('click', (event) => {
      const button = event.target.closest('[data-map-mode]');
      if (!button || button.dataset.mapMode === mapMode) return;
      const oldMap = getMap();
      const previousView = oldMap ? { mode: mapMode, bounds: oldMap.getBounds() } : null;
      mapMode = button.dataset.mapMode;
      modeSwitch.querySelectorAll('[data-map-mode]').forEach((other) => other.setAttribute('aria-pressed', String(other.dataset.mapMode === mapMode)));
      const credit = document.querySelector('#map-credit');
      if (credit) credit.innerHTML = mapById.get(mapMode)?.credit || '';
      if (container && typeof L !== 'undefined') renderLayer(container, places, calibrationCities, previousView);
    });
    if (!container || typeof L === 'undefined' || !places.length) return;
    renderLayer(container, places, calibrationCities);
  }

  return { renderMapPage, setupMap };
}
