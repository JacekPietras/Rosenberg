import assert from 'node:assert/strict';
import test from 'node:test';
import { recognizeMentions } from '../scripts/linters/generate_mentions.mjs';

test('a locative office title subsumes its bare title in generated mentions', () => {
  assert.deepEqual(recognizeMentions('for Bishop Hans zu Würzburg was'), [
    { person: 'Hans', personTitle: ['Bischof zu Würzburg'] },
  ]);
});

test('keeps an age title and a residence title as separate generated titles', () => {
  assert.deepEqual(recognizeMentions('Arnold von Rosenberg der Jüngere of Boxberg'), [
    { person: 'Arnold von Rosenberg', personTitle: ['der Jüngere', 'zu Boxberg'] },
  ]);
});

test('keeps a locative landgrave designation out of the person name', () => {
  assert.deepEqual(recognizeMentions('On June 8, 1489, Hans Landgraf zu Leuchtenberg enfeoffed Michael'), [
    { person: 'Hans', personTitle: ['Landgraf zu Leuchtenberg'] },
  ]);
  assert.deepEqual(recognizeMentions('was enfeoffed by Hans, Landgraf zu Leuchtenberg with the farm'), [
    { person: 'Hans', personTitle: ['Landgraf zu Leuchtenberg'] },
  ]);
});

test('same-named people with different designations stay separate mentions', () => {
  const found = recognizeMentions('Kunz von Rosenberg zu Reichelsburg, Kunz von Rosenberg zu Bartenstein');
  assert.equal(found.length, 2);
  assert.equal(found.every((item) => item.person === 'Kunz von Rosenberg' && item.personTitle.length === 1), true);
});

test('a bishop and an abbot of the same name are not merged', () => {
  const found = recognizeMentions('Johann, Bishop of Würzburg, and Johann, Abbot of Fulda');
  assert.equal(found.length, 2);
  assert.equal(found.every((item) => item.personTitle.length === 1), true);
});

test('removes fact-backed occurrences before merging same-name titles', () => {
  const stated = new Map([['Eberhard von Rosenberg', [['Vogt zu Dürn'], ['genannt von Zimmern'], ['der Jüngere']]]]);
  assert.deepEqual(recognizeMentions(
    'Lord Eberhard von Rosenberg, Vogt of Dürn, Eberhard von Rosenberg, called von Zimmern',
    { stated },
  ), []);
});
