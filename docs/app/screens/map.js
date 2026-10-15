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

export function createMapScreen({ state, escapeHtml, getMap, setMap, saveCalibrationCities }) {
  let mapMode = '1378';
  const mapEditable = !location.hostname.endsWith('github.io');
  const calibrationEditable = false;
  const mapById = new Map(HRR_MAPS.map((map) => [map.id, map]));
  const calibrationIcon = typeof L === 'undefined' ? null : L.divIcon({ className: 'calibration-point-icon', iconSize: [10, 10] });

  function renderMapPage() {
    const buttons = [{ id: 'live', label: 'Current' }, ...HRR_MAPS.map((map) => ({ id: map.id, label: map.label }))]
      .map(({ id, label }) => `<button type="button" class="map-mode-button" data-map-mode="${id}" aria-pressed="${mapMode === id}">${escapeHtml(label)}</button>`).join('');
    return `<div class="map-wrap"><div id="map-container" class="map-container" role="application" aria-label="Map of places"></div><div id="map-mode-switch" class="map-mode-switch" role="group" aria-label="Map version">${buttons}</div><span id="map-save-status" class="map-save-status status" aria-live="polite"></span></div><p id="map-credit" class="map-credit">${mapById.get(mapMode)?.credit || ''}</p>`;
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
    const html = `<img class="map-place-icon-image" src="${iconUrl}" alt="">`;
    const size = ['city', 'village'].includes(category) ? 60 : 30;
    return { icon: L.divIcon({ className: `map-place-icon map-place-icon-${category}`, html, iconSize: [size, size], iconAnchor: [size / 2, size], popupAnchor: [0, -size] }) };
  }

  function bindPlaceMarker(marker, place) {
    return marker
      .bindPopup(`<a class="place-link" href="?place=${encodeURIComponent(place.name)}">${escapeHtml(place.name)}</a>`)
      .bindTooltip(escapeHtml(place.name), { permanent: true, direction: 'bottom', offset: [0, 0], className: 'map-place-label' });
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
        bindPlaceMarker(L.marker([map.height - point.y, point.x], markerOptions(place)).addTo(leafletMap), place);
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
    const markers = places.map((place) => bindPlaceMarker(L.marker([place.lat, place.lon], markerOptions(place)).addTo(leafletMap), place));
    leafletMap.fitBounds(carriedCorners ? latLonCornersToView(carriedCorners, 'live', calibrationCities) : L.featureGroup(markers).getBounds(), carriedCorners ? undefined : { padding: [40, 40] });
  }

  function setupMap() {
    const container = document.querySelector('#map-container');
    const places = state.places.filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lon));
    const calibrationCities = state.calibrationCities.filter((city) => Number.isFinite(city.lat) && Number.isFinite(city.lon));
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
      if (container && places.length && typeof L !== 'undefined') renderLayer(container, places, calibrationCities, previousView);
    });
    if (!container || typeof L === 'undefined' || !places.length) return;
    renderLayer(container, places, calibrationCities);
  }

  return { renderMapPage, setupMap };
}
