import assert from 'node:assert/strict';
import test from 'node:test';
import { createPlaceCanonicalizer } from '../docs/app/data/place-canonical.js';

const { canonicalPlace, placeKey } = createPlaceCanonicalizer([
  { id: 'niederstetten', category: 'city', variations: ['Niederstetten'] },
  { id: 'halten', parent: 'niederstetten', variations: ['Haltenbergstetten', 'Haldenbergstetten'] },
  { id: 'schloss-n', parent: 'niederstetten', variations: ['Schloss'] },
  { id: 'nuremberg', variations: ['Nürnberg', 'Nuremberg'] },
  { id: 'a1', variations: ['Twin', 'Zwilling'] },
  { id: 'a2', variations: ['Other', 'Zwilling'] },
]);

test('canonical place is the record raw first variation', () => {
  assert.equal(canonicalPlace('Haldenbergstetten'), 'Haltenbergstetten');
  assert.equal(canonicalPlace('Nuremberg'), 'Nürnberg');
  assert.equal(placeKey('Nuremberg'), placeKey('Nürnberg'));
});

test('a generic building name keeps its settlement-qualified form', () => {
  assert.equal(canonicalPlace('Schloss Niederstetten'), 'Schloss Niederstetten');
});

test('ambiguous and unlisted forms stay as written', () => {
  assert.equal(canonicalPlace('Zwilling'), 'Zwilling');
  assert.equal(canonicalPlace('Nowhere'), 'Nowhere');
});
