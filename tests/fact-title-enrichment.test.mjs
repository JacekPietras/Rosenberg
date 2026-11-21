import assert from 'node:assert/strict';
import test from 'node:test';
import { createTitleForms } from '../scripts/linters/title_forms.mjs';
import { enrichEntry } from '../scripts/linters/fact_title_enrichment.mjs';
import { acceptNormalizedName, acceptTitleSplit } from '../scripts/linters/name_guard.mjs';

const titles = createTitleForms({
  ageText: '# Younger\nder Jüngere\n# Older\nder Ältere\n',
  officeText: '// offices\nSchultheiß\n// ranks\nRitter\nJunker\n// territorial titles\nBischof\nAbt\n// family titles\nGraf\n',
  places: ['Würzburg', 'Fulda', 'Bartenstein', 'Reichelsburg', 'Wertheim', 'Boxberg'].map((name) => ({ id: name, variations: [name] })),
});
const context = { route: (name) => name, registry: new Map(), titles };
const run = (facts, mention) => enrichEntry({ facts, mention }, context).map(({ person, final }) => [person.fact[person.field], final]);
const fact = (person, personTitle) => ({ type: 'generic', person, ...(personTitle ? { personTitle } : {}), content: 'x' });

test('a titled person never takes titles from a differently designated namesake', () => {
  assert.deepEqual(run([fact('Kunz von Rosenberg', ['zu Bartenstein'])],
    [{ person: 'Kunz von Rosenberg', personTitle: ['zu Reichelsburg'] }]), []);
});

test('a different office at the same place is not added', () => {
  assert.deepEqual(run([fact('Hans', ['Schultheiß zu Würzburg'])],
    [{ person: 'Hans', personTitle: ['Bischof zu Würzburg'] }]), []);
});

test('nothing is added when two namesake mentions both fit', () => {
  assert.deepEqual(run([fact('Hans')], [
    { person: 'Hans', personTitle: ['Bischof zu Würzburg'] }, { person: 'Hans', personTitle: ['Abt zu Fulda'] },
  ]), []);
});

test('an office is not added to a person sharing no title with the mention', () => {
  assert.deepEqual(run([fact('Egilolf von Rosenberg', ['der Ältere'])],
    [{ person: 'Egilolf von Rosenberg', personTitle: ['Abt'] }]), []);
});

test('a missing non-conflicting rank is added from the single compatible mention', () => {
  assert.deepEqual(run([fact('Eberhard von Wertheim', ['Graf von Wertheim'])],
    [{ person: 'Eberhard von Wertheim', personTitle: ['Graf von Wertheim', 'Junker'] }]),
  [['Eberhard von Wertheim', ['Graf von Wertheim', 'Junker']]]);
});

test('a bare office is replaced by the located one and the place is kept as in the mention', () => {
  assert.deepEqual(run([fact('Hans', ['Bischof'])], [{ person: 'Hans', personTitle: ['Bischof zu Würzburg'] }]),
    [['Hans', ['Bischof zu Würzburg']]]);
});

test('a namesake with other titles in another fact blocks a shared mention', () => {
  assert.deepEqual(run([fact('Hans', ['Abt zu Fulda']), fact('Hans')],
    [{ person: 'Hans', personTitle: ['Bischof zu Würzburg'] }]), [['Hans', ['Bischof zu Würzburg']]]);
});

test('normalization never drops a surname or adds a place', () => {
  assert.equal(acceptNormalizedName('Georg Keller', 'Georg'), false);
  assert.equal(acceptNormalizedName('Heinrich', 'Heinrich zu Fulda'), false);
  assert.equal(acceptNormalizedName('Konrad v. Rosenberg', 'Konrad von Rosenberg'), true);
});

test('a title split never leaves a lone given name', () => {
  assert.equal(acceptTitleSplit('Georg Keller', { name: 'Georg', titles: ['Keller'] }), false);
  assert.equal(acceptTitleSplit('Georg von Rosenberg Ritter', { name: 'Georg von Rosenberg', titles: ['Ritter'] }), true);
});

test('a located title replaces the bare one', () => {
  assert.deepEqual(run([fact('Rudolf von Wertheim', ['Graf'])],
    [{ person: 'Rudolf von Wertheim', personTitle: ['Graf von Wertheim', 'Junker'] }]),
  [['Rudolf von Wertheim', ['Graf von Wertheim', 'Junker']]]);
});

test('a rank with a place adds nothing to a rank plus designation', () => {
  assert.deepEqual(run([fact('Albrecht von Rosenberg', ['Ritter', 'zu Boxberg'])],
    [{ person: 'Albrecht von Rosenberg', personTitle: ['Ritter zu Boxberg'] }]), []);
});

test('a bare office and designation already state the located office', () => {
  assert.deepEqual(run([fact('Otto', ['Abt', 'zu Fulda'])], [{ person: 'Otto', personTitle: ['Abt zu Fulda'] }]), []);
});
