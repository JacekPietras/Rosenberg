import assert from 'node:assert/strict';
import test from 'node:test';
import { createTitleForms } from '../scripts/linters/title_forms.mjs';

const forms = createTitleForms({
  ageText: '# Younger\nder Jüngere, the Younger\n# Older\nder Ältere, the Elder\n',
  officeText: '// offices\nSchultheiß\n// ranks\nRitter, knight\nJunker\n// territorial titles\nBischof, Bishop\nAbt, Abbot\nHerzog, Duke\n// family titles\nGraf, Count\n',
  places: [
    { id: 'wuerzburg', variations: ['Würzburg'] },
    { id: 'fulda', variations: ['Fulda'] },
    { id: 'franken', variations: ['Franken'] },
    { id: 'nuremberg', variations: ['Nürnberg', 'Nuremberg'] },
    { id: 'hainstadt', variations: ['Hainstadt', 'Heinstadt'] },
    { id: 'bartenstein', variations: ['Bartenstein'] },
    { id: 'reichelsburg-aub', parent: 'aub', variations: ['Reichelsburg', 'Reigelsberg'] },
    { id: 'aub', category: 'city', variations: ['Aub'] },
    { id: 'schloss-halten', parent: 'niederstetten', variations: ['Haltenbergstetten', 'Haldenbergstetten'] },
    { id: 'niederstetten', category: 'city', variations: ['Niederstetten'] },
    { id: 'wallduern', variations: ['Dürn', 'Walldürn'] },
    { id: 'schloss-x', parent: 'niederstetten', variations: ['Schloss'] },
  ],
});

test('locative particles become zu, von and an are kept', () => {
  assert.deepEqual(forms.canonicalTitles(['Bishop of Würzburg', 'knight at Fulda', 'zum Bartenstein', 'Graf von Rieneck',
    'Abt an Fulda']),
  ['Bischof zu Würzburg', 'Ritter', 'zu Fulda', 'zu Bartenstein', 'Graf von Rieneck', 'Abt an Fulda']);
});

test('places are written as the record raw first variation', () => {
  assert.deepEqual(forms.canonicalTitles(['zu Haldenbergstetten', 'Schultheiß zu Nuremberg', 'Ritter zu Walldürn',
    'zu Reigelsberg', 'zu Reichelsburg, Aub', 'Ritter zu Unlisted']),
  ['zu Haltenbergstetten', 'Schultheiß zu Nürnberg', 'Ritter', 'zu Dürn', 'zu Reichelsburg', 'zu Unlisted']);
});

test('a located title keeps its place when consolidated', () => {
  assert.deepEqual(forms.consolidateTitles(['Bischof zu Würzburg', 'Herzog zu Franken']),
    ['Bischof zu Würzburg', 'Herzog zu Franken']);
  assert.deepEqual(forms.consolidateTitles(['Bischof', 'Bischof zu Würzburg', 'Bishop']), ['Bischof zu Würzburg']);
  assert.deepEqual(forms.consolidateTitles(['Herzog zu Franconia', 'Bischof']), ['Herzog zu Franconia', 'Bischof']);
});

test('variants of one place record collapse to one title', () => {
  assert.deepEqual(forms.consolidateTitles(['Schultheiß zu Nürnberg', 'Schultheiß zu Nuremberg']), ['Schultheiß zu Nürnberg']);
  assert.deepEqual(forms.consolidateTitles(['zu Hainstadt', 'zu Heinstadt']), ['zu Hainstadt']);
});

test('an age title with a place is split', () => {
  assert.deepEqual(forms.consolidateTitles(['der Jüngere zu Boxberg']), ['der Jüngere', 'zu Boxberg']);
});

test('titles with conflicting designations, offices or ages are incompatible', () => {
  assert.equal(forms.compatible(['zu Bartenstein'], ['zu Reichelsburg']), false);
  assert.equal(forms.compatible(['zu Reichelsburg'], ['zu Reichelsburg Aub']), true);
  assert.equal(forms.compatible(['Bischof zu Würzburg'], ['Abt zu Fulda']), false);
  assert.equal(forms.compatible(['Schultheiß zu Würzburg'], ['Bischof zu Würzburg']), false);
  assert.equal(forms.compatible(['der Ältere'], ['der Jüngere']), false);
  assert.equal(forms.compatible(['Graf von Wertheim'], ['Graf von Wertheim', 'Junker']), true);
  assert.equal(forms.compatible([], ['Abt zu Fulda']), true);
  assert.equal(forms.compatible(['Bischof'], ['Bischof zu Würzburg']), true);
});

test('same-route items with conflicting titles stay separate people', () => {
  assert.deepEqual(forms.mergePeople([
    { person: 'Kunz', personTitle: ['zu Reichelsburg'] }, { person: 'Kunz', personTitle: ['zu Bartenstein'] },
  ]), [{ person: 'Kunz', personTitle: ['zu Reichelsburg'] }, { person: 'Kunz', personTitle: ['zu Bartenstein'] }]);
  assert.deepEqual(forms.mergePeople([
    { person: 'Hans', personTitle: ['Bischof zu Würzburg'] }, { person: 'Hans', personTitle: ['Abt zu Fulda'] },
  ]).map((item) => item.personTitle), [['Bischof zu Würzburg'], ['Abt zu Fulda']]);
});

test('same-route items with compatible titles merge', () => {
  assert.deepEqual(forms.mergePeople([
    { person: 'Hans', personTitle: ['Bischof'] }, { person: 'Hans', personTitle: ['Bischof zu Würzburg', 'Ritter'] },
    { person: 'Hans' }, { place: 'fulda' },
  ]), [{ person: 'Hans', personTitle: ['Bischof zu Würzburg', 'Ritter'] }, { place: 'fulda' }]);
  assert.deepEqual(forms.mergePeople([{ person: 'Hans' }, { person: 'Hans' }]), [{ person: 'Hans' }]);
});

test('a title compatible with several people is not merged into one of them', () => {
  const merged = forms.mergePeople([
    { person: 'Hans', personTitle: ['Bischof zu Würzburg'] }, { person: 'Hans', personTitle: ['Abt zu Fulda'] },
    { person: 'Hans', personTitle: ['Ritter'] }, { person: 'Hans', personTitle: ['Bischof zu Würzburg', 'Junker'] },
  ]);
  assert.deepEqual(merged.map((item) => item.personTitle), [['Bischof zu Würzburg', 'Junker'], ['Abt zu Fulda'], ['Ritter']]);
});

test('different age titles stay separate', () => {
  assert.equal(forms.mergePeople([
    { person: 'Konrad', personTitle: ['der Ältere'] }, { person: 'Konrad', personTitle: ['der Jüngere'] },
  ]).length, 2);
});

test('a fact states a mention only with compatible, covering titles', () => {
  assert.equal(forms.covers(['Schultheiß zu Nürnberg', 'Ritter'], ['Schultheiß']), true);
  assert.equal(forms.covers(['Schultheiß zu Nürnberg'], ['Schultheiß zu Nuremberg']), true);
  assert.equal(forms.covers(['zu Bartenstein'], ['zu Reichelsburg']), false);
  assert.equal(forms.covers(['Bischof zu Würzburg'], ['Abt zu Fulda']), false);
  assert.equal(forms.covers(['der Ältere'], ['der Jüngere']), false);
  assert.equal(forms.covers(['Ritter'], ['Ritter', 'der Ältere']), false);
});

test('a located title supersedes its bare form', () => {
  assert.deepEqual(forms.consolidateTitles(['Graf', 'Graf von Wertheim']), ['Graf von Wertheim']);
});

test('a bare office and a designation are not rewritten into a located office', () => {
  assert.deepEqual(forms.consolidateTitles(['Abt', 'zu Fulda']), ['Abt', 'zu Fulda']);
  assert.deepEqual(forms.consolidateTitles(['Abt zu Fulda', 'zu Fulda']), ['Abt zu Fulda']);
  });

test('ranks and ages never take a place', () => {
  assert.deepEqual(forms.canonicalTitles(['Ritter zu Bartenstein']), ['Ritter', 'zu Bartenstein']);
  assert.deepEqual(forms.consolidateTitles(['Ritter', 'zu Bartenstein']), ['Ritter', 'zu Bartenstein']);
  assert.equal(forms.covers(['Ritter', 'zu Bartenstein'], ['Ritter zu Bartenstein']), true);
  assert.equal(forms.covers(['Abt', 'zu Fulda'], ['Abt zu Fulda']), true);
  assert.equal(forms.covers(['Abt zu Fulda'], ['zu Fulda']), true);
  assert.equal(forms.covers(['Abt zu Fulda'], ['Abt', 'zu Fulda']), true);
});
