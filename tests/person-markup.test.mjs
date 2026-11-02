import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { parsePlaces, buildPlacePattern, buildPersonPattern, buildSourcePersonPattern } = await import(await moduleUrl(new URL('../docs/app/data/entities.js', import.meta.url)));
const { createMarkupRenderer } = await import(await moduleUrl(new URL('../docs/app/rendering/markup.js', import.meta.url)));

test('source names take precedence over places and explicit IDs remain specific', async () => {
  const [names, particles, placesJson] = await Promise.all(['names.md', 'nobiliary_particles.md', 'places.json']
    .map((file) => readFile(new URL(`../data/${file}`, import.meta.url), 'utf8')));
  const places = parsePlaces(placesJson);
  const people = [{ id: 'hans_id', name: 'Hans von Rosenberg' }, { id: 'irmtraut', name: 'Irmtraut' }];
  const state = { people, places, personPattern: buildPersonPattern(people),
    sourcePersonPattern: buildSourcePersonPattern(names, particles, places), placePattern: buildPlacePattern(places) };
  const { inlineMarkup } = createMarkupRenderer({ state });
  const person = (name) => `<a class="person-link" href="?person=${encodeURIComponent(name)}">${name}</a>`;
  assert.equal(inlineMarkup('Margaretha von Rosenberg'), person('Margaretha von Rosenberg'));
  assert.equal(inlineMarkup('Hans Mönch von Rosenberg'), person('Hans Mönch von Rosenberg'));
  assert.equal(inlineMarkup('Margaretha v. Rosenberg'), person('Margaretha v. Rosenberg'));
  assert.equal(inlineMarkup('[hans_id]'), '<a class="person-link" href="?person=hans_id">Hans von Rosenberg</a>');
  assert.equal(inlineMarkup('Irmtraut'), person('Irmtraut'));
  assert.match(inlineMarkup('Rosenberg'), /^<a class="place-link"/);
  assert.doesNotMatch(inlineMarkup('Unknown von Rosenberg'), /class="person-link"/);
});
