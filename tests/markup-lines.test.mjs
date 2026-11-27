import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { createMarkupRenderer } = await import(await moduleUrl(new URL('../docs/app/rendering/markup.js', import.meta.url)));
const { markdownMarkup } = createMarkupRenderer({ state: {} });

test('preserves line and paragraph breaks around lists', () => {
  assert.equal(markdownMarkup('First\nSecond\n\nThird', false), '<p>First<br>Second</p><p>Third</p>');
  assert.equal(markdownMarkup('First\n- Item\nLast\nNext', false), '<p>First</p><ul class="source-list"><li>Item</li></ul><p>Last<br>Next</p>');
});
