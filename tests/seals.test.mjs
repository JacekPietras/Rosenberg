import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { createSealScreen } = await import(await moduleUrl(new URL('../docs/app/screens/seals.js', import.meta.url)));

test('selected seal filters can be cleared when no seals match', () => {
  const state = { sealNames: ['after:unknown'], sealType: 'full' };
  let saved = 0;
  let rendered = 0;
  const link = {
    dataset: { sealPart: 'after', sealName: 'unknown' },
    addEventListener(type, callback) { if (type === 'click') this.click = callback; },
  };
  const previousDocument = globalThis.document;
  globalThis.document = { querySelectorAll: () => [link], querySelector: () => null };
  try {
    const screen = createSealScreen({ state, savePreferences: () => saved++, rerender: () => rendered++ });
    screen.setupSealHighlight([]);
    let prevented = false;
    link.click({ preventDefault: () => { prevented = true; } });
    assert.equal(prevented, true);
    assert.deepEqual(state.sealNames, []);
    assert.equal(saved, 1);
    assert.equal(rendered, 1);
  } finally {
    globalThis.document = previousDocument;
  }
});
