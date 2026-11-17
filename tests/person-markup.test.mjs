import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { parsePlaces, buildPlacePattern, buildPersonPattern, buildSourcePersonPattern } = await import(await moduleUrl(new URL('../docs/app/data/entities.js', import.meta.url)));
const { personMentionClass } = await import(await moduleUrl(new URL('../docs/app/data/person-name-recognition.js', import.meta.url)));
const { createMarkupRenderer } = await import(await moduleUrl(new URL('../docs/app/rendering/markup.js', import.meta.url)));

test('source names take precedence over places and explicit IDs remain specific', async () => {
  const [names, particles, placesJson, byNames] = await Promise.all(['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md']
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const people = [{ id: 'hans_id', name: 'Hans von Rosenberg' }, { id: 'irmtraut', name: 'Irmtraut' }];
  const state = { people, places, personPattern: buildPersonPattern(people),
    byNamesText: byNames, personNamesText: names, nobiliaryParticlesText: particles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, '', '', byNames), placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const person = (name) => `<a class="person-link ${personMentionClass(name)}" href="?person=${encodeURIComponent(name)}">${name}</a>`;
  assert.equal(inlineMarkup('Margaretha von Rosenberg'), person('Margaretha von Rosenberg'));
  assert.equal(inlineMarkup('Hans Mönch von Rosenberg'), person('Hans Mönch von Rosenberg'));
  assert.equal(inlineMarkup('Margaretha v. Rosenberg'),
    `<a class="person-link ${personMentionClass('Margaretha v. Rosenberg')}" href="?person=${encodeURIComponent('Margaretha von Rosenberg')}">Margaretha v. Rosenberg</a>`);
  assert.equal(inlineMarkup('[hans_id]'), '<a class="person-link person-id-link" href="?person=hans_id">Hans von Rosenberg</a>');
  assert.equal(inlineMarkup('Irmtraut'), person('Irmtraut'));
  assert.match(inlineMarkup('Rosenberg'), /^<a class="place-link"/);
  assert.doesNotMatch(inlineMarkup('Unknown von Rosenberg'), /class="person-link"/);
});

test('coordinated by-name mentions link each brother to the inherited place route', async () => {
  const files = ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md', 'titles-age.md', 'titles-office.md'];
  const [names, particles, placesJson, byNames, connectors, ageTitles, officeTitles] = await Promise.all(files
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const titles = `${ageTitles}\n${officeTitles}`;
  const people = [];
  const state = { people, places, personPattern: [], personNamesText: names, byNamesText: byNames,
    nobiliaryParticlesText: particles, nameConnectorsText: connectors, personNameTitlesText: titles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, titles, connectors, byNames),
    placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const rendered = inlineMarkup('Hainrich Marschalk zu Pappenheim, also acting for his brothers Goerg and Chuonrat Marschalken, acknowledges that he sold the Pappenheim convent');
  assert.match(rendered, /href="\?person=Heinrich%20Marschalk%20zu%20Pappenheim"/u);
  assert.match(rendered, /href="\?person=Georg%20Marschalk%20zu%20Pappenheim"/u);
  assert.match(rendered, /href="\?person=Konrad%20Marschalk%20zu%20Pappenheim"/u);
});

test('does not repeat a coordinated by-name before its trailing residence title', async () => {
  const files = ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md', 'titles-age.md', 'titles-office.md'];
  const [names, particles, placesJson, byNames, connectors, ageTitles, officeTitles] = await Promise.all(files
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const titles = `${ageTitles}\n${officeTitles}`;
  const state = { people: [], places, personPattern: [], personNamesText: names, byNamesText: byNames,
    nobiliaryParticlesText: particles, nameConnectorsText: connectors, personNameTitlesText: titles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, titles, connectors, byNames),
    placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const source = 'Brothers Hans and Lutz Mönch von Rosenberg zu Hainstadt, sell to';
  const rendered = inlineMarkup(source);
  assert.equal(rendered.replace(/<[^>]+>/gu, ''), source);
  assert.match(rendered, /href="\?person=Hans%20M%C3%B6nch%20von%20Rosenberg"/u);
  assert.ok(rendered.includes(`<a class="person-link person-mention-blue" href="?person=${encodeURIComponent('Lutz Mönch von Rosenberg')}">Lutz Mönch von Rosenberg zu Hainstadt</a>`));
});

test('inline links keep the three compound names from the fief list intact', async () => {
  const files = ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md', 'titles-age.md', 'titles-office.md'];
  const [names, particles, placesJson, byNames, connectors, ageTitles, officeTitles] = await Promise.all(files
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const titles = `${ageTitles}\n${officeTitles}`;
  const state = { people: [], places, personPattern: [], personNamesText: names, byNamesText: byNames,
    nobiliaryParticlesText: particles, nameConnectorsText: connectors, personNameTitlesText: titles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, titles, connectors, byNames),
    placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const rendered = inlineMarkup('enfeoffs Adam Hector, Johann Konrad and Hans Dietrich von Rosenberg with houses');
  for (const route of [
    'Adam Hector von Rosenberg',
    'Hans Konrad von Rosenberg',
    'Hans Dietrich von Rosenberg',
  ]) assert.ok(rendered.includes(`href="?person=${encodeURIComponent(route)}"`), route);
  assert.doesNotMatch(rendered, /href="\?person=Konrad%20von%20Rosenberg"/u);
});

test('links all three names in a coordinated Marschalk list', async () => {
  const files = ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md', 'titles-age.md', 'titles-office.md'];
  const [names, particles, placesJson, byNames, connectors, ageTitles, officeTitles] = await Promise.all(files
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const titles = `${ageTitles}\n${officeTitles}`;
  const state = { people: [], places, personPattern: [], personNamesText: names, byNamesText: byNames,
    nobiliaryParticlesText: particles, nameConnectorsText: connectors, personNameTitlesText: titles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, titles, connectors, byNames),
    placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const text = 'Chuoncz Rosenkrancz declares that he has reached an amicable settlement with Sigmund, Haubt, and Hainrich Marschalken zu Pappenheim and all the Marschalk zu Pappenheim concerning';
  const rendered = inlineMarkup(text);
  for (const route of ['Siegmund Marschalk zu Pappenheim', 'Haubt Marschalk zu Pappenheim', 'Heinrich Marschalk zu Pappenheim']) {
    assert.ok(rendered.includes(`href="?person=${encodeURIComponent(route)}"`), route);
  }
});

test('highlights the complete final name in a list ending with von Rosenberg', async () => {
  const files = ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md', 'titles-age.md', 'titles-office.md'];
  const [names, particles, placesJson, byNames, connectors, ageTitles, officeTitles] = await Promise.all(files
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const titles = `${ageTitles}\n${officeTitles}`;
  const state = { people: [], places, personPattern: [], personNamesText: names, byNamesText: byNames,
    nobiliaryParticlesText: particles, nameConnectorsText: connectors, personNameTitlesText: titles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, titles, connectors, byNames),
    placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const text = 'Among those named: Thomas, Anselm, Eberhard, Ulrich, and Georg von Rosenberg.';
  const rendered = inlineMarkup(text);
  assert.ok(rendered.includes(`<a class="person-link person-mention-blue" href="?person=${encodeURIComponent('Georg von Rosenberg')}">Georg von Rosenberg</a>`));
  for (const name of ['Thomas', 'Anselm', 'Eberhard', 'Ulrich']) {
    assert.ok(rendered.includes(`href="?person=${encodeURIComponent(`${name} von Rosenberg`)}"`), name);
  }
});

test('links only the given names before brothers von Rosenberg', async () => {
  const files = ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md', 'titles-age.md', 'titles-office.md'];
  const [names, particles, placesJson, byNames, connectors, ageTitles, officeTitles] = await Promise.all(files
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const titles = `${ageTitles}\n${officeTitles}`;
  const state = { people: [], places, personPattern: [], personNamesText: names, byNamesText: byNames,
    nobiliaryParticlesText: particles, nameConnectorsText: connectors, personNameTitlesText: titles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, titles, connectors, byNames),
    placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const rendered = inlineMarkup('confirms to the nobles Peter, Johann, and Ulrich, brothers von Rosenberg, their mutual inheritance');
  for (const [givenName, route] of [['Peter', 'Peter von Rosenberg'], ['Johann', 'Hans von Rosenberg'], ['Ulrich', 'Ulrich von Rosenberg']]) {
    assert.ok(rendered.includes(`href="?person=${encodeURIComponent(route)}">${givenName}</a>`), givenName);
  }
  assert.match(rendered, /, brothers von Rosenberg, their mutual inheritance/u);
  assert.doesNotMatch(rendered, /href="\?person=[^"]*Rosenberg[^"]*">[^<]*von Rosenberg/u);
});

test('keeps the shared Edelknecht title outside brother links and routes', async () => {
  const files = ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md', 'titles-age.md', 'titles-office.md'];
  const [names, particles, placesJson, byNames, connectors, ageTitles, officeTitles] = await Promise.all(files
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const titles = `${ageTitles}\n${officeTitles}`;
  const state = { people: [], places, personPattern: [], personNamesText: names, byNamesText: byNames,
    nobiliaryParticlesText: particles, nameConnectorsText: connectors, personNameTitlesText: titles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, titles, connectors, byNames),
    placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const rendered = inlineMarkup('Bernger and Heinrich, brothers von Eubigheim, Edelknecht, sell their forest');
  assert.ok(rendered.includes(`href="?person=${encodeURIComponent('Bernger von Eubigheim')}">Bernger</a>`));
  assert.ok(rendered.includes(`href="?person=${encodeURIComponent('Heinrich von Eubigheim')}">Heinrich</a>`));
  assert.match(rendered, /, brothers von Eubigheim, Edelknecht, sell their forest/u);
  assert.doesNotMatch(rendered, /href="\?person=[^"]*(?:Edelknecht|Eubigheim)[^"]*">[^<]*(?:Edelknecht|Eubigheim)/u);
});

test('highlights Georg von Rosenberg after an adjacent witness list', async () => {
  const files = ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md', 'titles-age.md', 'titles-office.md'];
  const [names, particles, placesJson, byNames, connectors, ageTitles, officeTitles] = await Promise.all(files
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const titles = `${ageTitles}\n${officeTitles}`;
  const state = { people: [], places, personPattern: [], personNamesText: names, byNamesText: byNames,
    nobiliaryParticlesText: particles, nameConnectorsText: connectors, personNameTitlesText: titles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, titles, connectors, byNames),
    placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const text = 'pledged to Ulrich and Heinrich von Rechberg, Thomas, Ulrich, and Georg von Rosenberg,';
  const rendered = inlineMarkup(text);
  assert.ok(rendered.includes(`href="?person=${encodeURIComponent('Georg von Rosenberg')}"`));
  assert.ok(rendered.includes(`href="?person=${encodeURIComponent('Thomas von Rosenberg')}"`));
  assert.ok(rendered.includes(`href="?person=${encodeURIComponent('Ulrich von Rosenberg')}"`));
});

test('routes a trailing zum place as a title rather than part of the name', async () => {
  const files = ['names.md', 'nobiliary_particles.md', 'places.json', 'by-names.md', 'name-connectors.md', 'titles-age.md', 'titles-office.md'];
  const [names, particles, placesJson, byNames, connectors, ageTitles, officeTitles] = await Promise.all(files
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const titles = `${ageTitles}\n${officeTitles}`;
  const state = { people: [], places, personPattern: [], personNamesText: names, byNamesText: byNames,
    nobiliaryParticlesText: particles, nameConnectorsText: connectors, personNameTitlesText: titles,
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places, titles, connectors, byNames),
    placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const rendered = inlineMarkup('transferred the said Amt Klingenberg to Konrad von Rosenberg zum Bartenstein and his cousin');
  assert.ok(rendered.includes(`href="?person=${encodeURIComponent('Konrad von Rosenberg')}"`));
  assert.ok(rendered.includes('Konrad von Rosenberg zum Bartenstein'));
});
