import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import test from 'node:test';

async function moduleUrl(path) {
  let source = await readFile(path, 'utf8');
  source = source.replaceAll('import.meta.url', JSON.stringify(path.href));
  for (const [statement, specifier] of [...source.matchAll(/from '([^']+)'/g)]) {
    const dependency = new URL(specifier, path);
    dependency.search = '';
    source = source.replace(statement, `from '${await moduleUrl(dependency)}'`);
  }
  return `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
}
const { parsePlaces, buildPlacePattern } = await import(await moduleUrl(new URL('../docs/app/data/entities.js', import.meta.url)));
const { createMarkupRenderer } = await import(await moduleUrl(new URL('../docs/app/rendering/markup.js', import.meta.url)));
const { createEntityScreens } = await import(await moduleUrl(new URL('../docs/app/screens/entities.js', import.meta.url)));
const { escapeHtml } = await import(await moduleUrl(new URL('../docs/app/rendering/html.js', import.meta.url)));
const { createMapScreen } = await import(await moduleUrl(new URL('../docs/app/screens/map.js', import.meta.url)));
const fixture = [
  { id: 'town', category: 'village', variations: ['Schönau', 'Schonau', 'Schoenau'] },
  { id: 'abbey', category: 'church', parent: 'town', variations: ['Schönau Abbey', 'Schönau Monastery'] },
];

test('building combinations use only the first parent variation in both orders', () => {
  const places = parsePlaces(JSON.stringify(fixture));
  assert.deepEqual(new Set(places[1].variations), new Set([
    'Abbey Schönau', 'Schönau Abbey',
    'Monastery Schönau', 'Schönau Monastery',
    'Abbey, Schönau', 'Schönau, Abbey',
    'Monastery, Schönau', 'Schönau, Monastery',
  ]));
  assert.equal(places[1].name, 'Schönau Abbey');
  assert.equal('Abbey and Monastery'.match(buildPlacePattern(places)), null);
  const { inlineMarkup } = createMarkupRenderer({ state: { places, placePattern: buildPlacePattern(places) } });
  for (const name of places[1].variations) {
    assert.equal(inlineMarkup(name), `<a class="place-link" href="?place=abbey">${name}</a>`);
  }
  assert.equal(inlineMarkup('Schönau'), '<a class="place-link" href="?place=town">Schönau</a>');
  assert.equal(inlineMarkup('Schoenau'), '<a class="place-link" href="?place=town">Schoenau</a>');
});

test('both name orders and full variations resolve without duplicating the parent', () => {
  const places = parsePlaces(JSON.stringify([...fixture.slice(0, 1), {
    id: 'castle', parent: 'town', variations: ['Schloss Schönau', 'Old Schonau Castle', 'Schloss, Schönau', 'Reichelsburg'],
  }]));
  assert.equal(places[1].name, 'Schloss Schönau');
  assert.ok(places[1].variations.includes('Schönau Schloss'));
  assert.ok(places[1].variations.includes('Old Schonau Castle'));
  assert.ok(places[1].variations.includes('Old Castle Schönau'));
  assert.ok(!places[1].variations.includes('Schloss Schoenau'));
  assert.ok(!places[1].variations.includes('Schonau Old Castle'));
  assert.ok(places[1].variations.includes('Reichelsburg'));
  assert.ok(places[1].variations.every((name) => !/(Schönau|Schonau|Schoenau).*(Schönau|Schonau|Schoenau)/.test(name)));
  assert.equal('Schloss'.match(buildPlacePattern(places)), null);
});

test('invalid and non-settlement parents fail explicitly', () => {
  assert.throws(() => parsePlaces(JSON.stringify([fixture[1]])), /Invalid settlement parent/);
  assert.throws(() => parsePlaces(JSON.stringify([{ ...fixture[0], category: 'castle' }, fixture[1]])), /Invalid settlement parent/);
});

const raw = await readFile(new URL('../data/places.json', import.meta.url), 'utf8');
const places = parsePlaces(raw);

test('Niederstetten chapel never repeats its settlement, including older comma-separated names', () => {
  const stored = JSON.parse(raw);
  const chapel = stored.find((place) => place.id === 'niederstetten-friedhofskapelle');
  assert.deepEqual(chapel.variations, ['Friedhofskapelle']);
  assert.equal(chapel.parent, 'niederstetten');
  assert.equal(places.find((place) => place.id === chapel.id).name, 'Friedhofskapelle Niederstetten');
  const parent = stored.find((place) => place.id === chapel.parent);
  const legacy = [{ ...chapel, variations: ['Friedhofskapelle, Niederstetten'] }, parent];
  const resolved = parsePlaces(JSON.stringify(legacy))[0];
  assert.equal(resolved.name, 'Friedhofskapelle, Niederstetten');
  assert.ok(resolved.variations.every((name) => name.match(/Niederstetten/g)?.length === 1));
  const python = JSON.parse(execFileSync('python3', ['-c',
    'import sys,json; sys.path.insert(0,"scripts"); from place_names import resolve_place_names; print(json.dumps(resolve_place_names(json.load(sys.stdin))))',
  ], { cwd: new URL('..', import.meta.url), input: JSON.stringify(legacy), encoding: 'utf8' }));
  assert.deepEqual(python[0].variations, resolved.variations);
});

test('Waldmannshofen has one village parent and Bartenstein keeps its castle name', () => {
  const stored = JSON.parse(raw);
  const byId = new Map(places.map((place) => [place.id, place]));
  const village = byId.get('waldmannshofen');
  assert.equal(village.category, 'village');
  assert.ok(village.variations.includes('Waldtmanßhouen'));
  for (const [id, localName, expected] of [
    ['waldmannshofen-castle', 'Schloss', 'Schloss Waldmannshofen'],
    ['waldmannshofen-evangelical-church', 'Johanniskirche', 'Johanniskirche Waldmannshofen'],
  ]) {
    const place = byId.get(id);
    assert.deepEqual(stored.find((place) => place.id === id).variations, [localName]);
    assert.equal(place.name, expected);
    assert.ok(place.variations.every((name) => !/Bartenstein.*Bartenstein|Waldmannshofen.*Waldmannshofen/.test(name)));
    assert.ok(!place.variations.includes(localName));
    assert.ok(!place.variations.includes(byId.get(place.parent).name));
  }
  const bartenstein = byId.get('bartenstein');
  assert.equal(bartenstein.category, undefined);
  assert.equal(bartenstein.showOnMap, false);
  assert.equal(byId.get('schloss-bartenstein').parent, undefined);
  assert.equal(byId.get('schloss-bartenstein').name, 'Bartenstein');
  assert.ok(byId.get('schloss-bartenstein').variations.includes('Schloss Bartenstein'));
  assert.equal('Schloss and Burg and Johanniskirche'.match(buildPlacePattern(places)), null);
  const { inlineMarkup } = createMarkupRenderer({ state: { places, placePattern: buildPlacePattern(places) } });
  for (const [text, id] of [
    ['Waldmannshofen', 'waldmannshofen'],
    ['Waldtmanßhouen', 'waldmannshofen'],
    ['Schloss Waldmannshofen', 'waldmannshofen-castle'],
    ['Johanniskirche Waldmannshofen', 'waldmannshofen-evangelical-church'],
    ['Schloss Bartenstein', 'schloss-bartenstein'],
    ['Bartenstein', 'schloss-bartenstein'],
  ]) assert.equal(inlineMarkup(text), `<a class="place-link" href="?place=${id}">${text}</a>`);
});

test('migration keeps distinct Essingen sites, IDs, and settlement-only links', () => {
  const essingen = places.filter((place) => place.id.startsWith('essingen-'));
  assert.equal(essingen.length, 2);
  assert.ok(essingen.every((place) => !place.parent && place.name === 'Essingen'));
  const { inlineMarkup } = createMarkupRenderer({ state: { places, placePattern: buildPlacePattern(places) } });
  assert.equal(inlineMarkup('St. Wendelinuskapelle Essingen'), '<a class="place-link" href="?place=essingen-st-wendelinuskapelle">St. Wendelinuskapelle Essingen</a>');
  assert.equal(inlineMarkup('Essingen St Quirinus'), '<a class="place-link" href="?place=essingen-st-quirinus">Essingen St Quirinus</a>');
  assert.equal(new Set(places.map((place) => place.id)).size, places.length);
  const church = places.find((place) => place.id === 'uissigheim-st-laurentius');
  assert.deepEqual(JSON.parse(raw).find((place) => place.id === church.id).variations, ['St. Laurentius']);
  assert.equal(church.name, 'St. Laurentius Uissigheim');
  assert.ok(church.variations.includes('St. Laurentius'));
  assert.ok(church.variations.includes('Uissigheim St. Laurentius'));
  assert.ok(!church.variations.includes('Ußinkeim St. Laurentius'));
  assert.ok(!church.variations.some((name) => name.includes('Ußinkeim')));
  assert.ok(!church.variations.includes('Uissigheim'));
});

test('place pages accept old full names, generated spelling variants, and stable IDs', () => {
  const state = {};
  const { renderPlacePage } = createEntityScreens({
    state, getPlaces: () => places, getPeople: () => [], getDocuments: () => new Map(),
    buildPlacePattern, escapeHtml, inlineMarkup: escapeHtml,
  });
  for (const query of ['St. Laurentius Uissigheim', 'Uissigheim St. Laurentius', 'uissigheim-st-laurentius', 'Reichelsburg',
    'Friedhofskapelle, Niederstetten', 'Johanniskirche,Waldmannshofen', 'St. Kilian, Röttingen',
    'bartenstein', 'schloss-bartenstein', 'Bartenstein', 'Schloss Bartenstein']) {
    state.place = query;
    assert.ok(!renderPlacePage().includes('Place not found'), query);
  }
});

test('shared settlement names link to settlements and each building has the correct parent', () => {
  const byId = new Map(places.map((place) => [place.id, place]));
  const groups = [
    ['gnoetzheim', ['gnoetzheim-st-johannis', 'gnoetzheim-castle']],
    ['unterschuepf', ['unterschuepf-evangelical-church', 'unterschuepf-wasserschloss']],
    ['oberschuepf', ['schuepf-old-castle', 'schuepf-church', 'oberschuepf-castle']],
    ['rosenberg-town', ['rosenberg', 'rosenberg-evangelical-church']],
  ];
  const { inlineMarkup } = createMarkupRenderer({ state: { places, placePattern: buildPlacePattern(places) } });
  for (const [parentId, children] of groups) {
    const parent = byId.get(parentId);
    for (const spelling of parent.variations) {
      assert.equal(inlineMarkup(spelling), `<a class="place-link" href="?place=${parentId}">${spelling}</a>`);
    }
    for (const id of children) {
      const child = byId.get(id);
      assert.equal(child.parent, parentId);
      assert.ok(!child.variations.includes(parent.name));
      assert.equal(inlineMarkup(child.name), `<a class="place-link" href="?place=${id}">${child.name}</a>`);
    }
  }
  assert.equal(inlineMarkup('rosenberg'), '<a class="place-link" href="?place=rosenberg-town">rosenberg</a>');
  assert.equal(inlineMarkup('Essingen'), 'Essingen', 'an ambiguous name must not select the first church');
});

test('Haltenbergstetten historical spellings belong to the settlement and Oberlauda retains its confirmed full label', () => {
  const byId = new Map(places.map((place) => [place.id, place]));
  const parent = byId.get('niederstetten');
  const castle = byId.get('schloss-haltenbergstetten');
  for (const name of ['Haldemarstetten', 'Zaltenbergstetten', 'Haltermannstetten', 'Haltenbergsketten']) {
    assert.ok(parent.variations.includes(name));
    assert.ok(!castle.variations.some((variation) => variation.includes(name)));
  }
  assert.equal(castle.name, 'Schloss Haltenbergstetten');
  assert.equal(byId.get('burg-oberlauda').name, 'Burg Oberlauda Lauda');
});

test('1387 categories distinguish markets and villages from cities', () => {
  const byId = new Map(places.map((place) => [place.id, place]));
  for (const id of ['aub', 'giebelstadt', 'wirsberg', 'gnoetzheim', 'unterschuepf', 'oberschuepf']) {
    assert.equal(byId.get(id).category, 'village', id);
  }
  assert.equal(byId.get('rosenberg-town').category, 'city');
});

test('punctuated building names link as one phrase and preserve the original text', () => {
  const { inlineMarkup } = createMarkupRenderer({ state: { places, placePattern: buildPlacePattern(places) } });
  for (const [text, id] of [
    ['Friedhofskapelle, Niederstetten', 'niederstetten-friedhofskapelle'],
    ['Friedhofskapelle,Niederstetten', 'niederstetten-friedhofskapelle'],
    ['Friedhofskapelle ,  Niederstetten', 'niederstetten-friedhofskapelle'],
    ['Niederstetten, Friedhofskapelle', 'niederstetten-friedhofskapelle'],
    ['Johanniskirche, Waldmannshofen', 'waldmannshofen-evangelical-church'],
    ['St. Kilian, Röttingen', 'roettingen-st-kilian'],
    ['Schloss, Gnötzheim', 'gnoetzheim-castle'],
  ]) assert.equal(inlineMarkup(text), `<a class="place-link" href="?place=${id}">${text}</a>`);
});

test('Python tools and browser expand repository and fixture names identically', () => {
  for (const input of [raw, JSON.stringify(fixture)]) {
    const output = execFileSync('python3', ['-c',
      'import sys,json; sys.path.insert(0,"scripts"); from place_names import resolve_place_names; print(json.dumps(resolve_place_names(json.load(sys.stdin))))',
    ], { cwd: new URL('..', import.meta.url), input, encoding: 'utf8' });
    assert.deepEqual(JSON.parse(output).map((place) => place.variations), parsePlaces(input).map((place) => place.variations));
  }
});

test('both map views use explicit short labels and full names with parents', (t) => {
  const originals = Object.fromEntries(['L', 'document', 'location'].map((key) => [key, globalThis[key]]));
  t.after(() => {
    for (const [key, value] of Object.entries(originals)) {
      if (value === undefined) delete globalThis[key]; else globalThis[key] = value;
    }
  });
  const html = [];
  const element = () => ({
    value: '', style: { setProperty() {} }, parentElement: { append() {} },
    setAttribute() {}, addEventListener() {},
  });
  const elements = new Map();
  globalThis.document = {
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, element());
      return elements.get(selector);
    },
    createElement: element,
  };
  globalThis.location = { hostname: 'localhost' };
  const bounds = { pad() { return this; }, isValid: () => true };
  const fitZoomSnaps = [];
  globalThis.L = {
    CRS: { Simple: {} }, divIcon: (options) => options, latLngBounds: () => bounds,
    map: (container, options) => ({
      options, setMaxBounds() {}, remove() {},
      fitBounds() { fitZoomSnaps.push(this.options.zoomSnap); },
    }),
    imageOverlay: () => ({ addTo() {} }),
    marker: (point, options) => {
      html.push(options.icon.html);
      return { addTo() { return this; }, on() {} };
    },
  };
  const selected = places.filter((place) => ['essingen-st-wendelinuskapelle', 'bartenstein', 'schloss-bartenstein'].includes(place.id));
  const state = {
    places: selected, calibrationCities: [], people: [{ id: 'person', name: 'Person' }],
    documents: new Map([['book', { entries: [{ date: '1400', facts: [
      '[person] visited St. Wendelinuskapelle Essingen and Bartenstein.',
    ] }] }]]),
  };
  let map;
  const screen = createMapScreen({ state, escapeHtml, getMap: () => map, setMap: (value) => { map = value; } });
  for (const render of [() => screen.setupMap(), () => screen.setupPersonMap('person')]) {
    html.length = 0;
    render();
    assert.equal(fitZoomSnaps.at(-1), 0.1, 'initial view fits places precisely');
    assert.equal(map.options.zoomSnap, 1, 'wheel zoom uses whole levels after fitting');
    assert.equal(html.length, 2);
    assert.ok(html.some((markup) => markup.includes('>Essingen</span>')));
    assert.ok(html.some((markup) => markup.includes('>Bartenstein</span>')));
  }
});
