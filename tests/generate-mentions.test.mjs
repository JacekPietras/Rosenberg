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
