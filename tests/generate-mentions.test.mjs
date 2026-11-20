import assert from 'node:assert/strict';
import test from 'node:test';
import { recognizeMentions } from '../scripts/linters/generate_mentions.mjs';

test('a locative office title subsumes its bare title in generated mentions', () => {
  assert.deepEqual(recognizeMentions('for Bishop Hans zu Würzburg was'), [
    { person: 'Hans', personTitle: ['Bischof zu Würzburg'] },
  ]);
});
