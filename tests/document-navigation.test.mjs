import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { documentAtMarker } = await import(await moduleUrl(new URL('../docs/app/components/document-navigation.js', import.meta.url)));

test('finds the current document across boundaries and layout changes', () => {
  const positions = [200, 400, 800];
  const targets = positions.map((_, index) => ({ element: { getBoundingClientRect: () => ({ top: positions[index] }) }, index }));
  assert.equal(documentAtMarker([]), null);
  assert.equal(documentAtMarker(targets).index, 0);
  positions.splice(0, 3, -100, 160, 500);
  assert.equal(documentAtMarker(targets).index, 1);
  positions.splice(0, 3, -500, -300, -1);
  assert.equal(documentAtMarker(targets).index, 2);
});

test('measures logarithmically many cards', () => {
  let measurements = 0;
  const targets = Array.from({ length: 4096 }, (_, index) => ({ element: { getBoundingClientRect: () => { measurements++; return { top: index }; } }, index }));
  assert.equal(documentAtMarker(targets, 2048).index, 2048);
  assert.ok(measurements <= 13);
});
