import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { createDocumentRenderer } = await import(await moduleUrl(new URL('../docs/app/screens/documents.js', import.meta.url)));

test('document details are rendered only when a card is hydrated', () => {
  let images = 0;
  let factQueries = 0;
  const state = { active: 'documents', showFacts: true, places: [] };
  const renderer = createDocumentRenderer({
    state, formatDate: String, escapeHtml: String, markdownLinks: String, inlineMarkup: String,
    urlMarkup: (url) => `URL:${url}`, languageMarkup: (entry) => `TEXT:${entry.english}`,
    treeMarkup: String, imageMarkup: () => { images++; return 'IMAGE'; },
    diagramMarkup: () => 'DIAGRAM', entryAnchor: () => 'entry', entryHasSource: () => true,
    documentTitle: () => 'Title', documentYear: () => 1300,
    getPeople: () => { factQueries++; return []; }, distinctFamilies: new Set(),
  });
  const doc = { date: '1300', url: 'link', research: 'RESEARCH', entries: [{ english: 'English', source: 'SOURCE', img: 'photo', diagram: 'graph', mention: [{ person: 'Hans' }] }] };
  const path = 'data/documents/example.json';
  const initial = renderer.renderDocument(doc, path, 0);
  for (const text of ['TEXT:English', 'SOURCE', 'URL:link', '1300']) assert.ok(initial.includes(text));
  for (const text of ['IMAGE', 'DIAGRAM', 'RESEARCH', 'facts-view']) assert.ok(!initial.includes(text));
  assert.equal(images, 0);
  assert.equal(factQueries, 0);
  const hydrated = renderer.renderDocumentWithPersonLinks(doc, path, 0);
  for (const text of ['IMAGE', 'DIAGRAM', 'RESEARCH', 'facts-view']) assert.ok(hydrated.includes(text));
  assert.equal(images, 1);
  assert.equal(factQueries, 1);
  state.showFacts = false;
  renderer.renderDocumentWithPersonLinks(doc, path, 0);
  assert.equal(factQueries, 1);
});
