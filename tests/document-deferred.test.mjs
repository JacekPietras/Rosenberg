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


test('Split appears for three distinct four-digit years in English entries', () => {
  const state = { active: 'documents', canEditDocuments: true, places: [] };
  const renderer = createDocumentRenderer({
    state, formatDate: String, escapeHtml: String, markdownLinks: String, inlineMarkup: String,
    urlMarkup: String, languageMarkup: () => '', treeMarkup: String, imageMarkup: String,
    diagramMarkup: String, entryAnchor: () => 'entry', entryHasSource: () => true,
    documentTitle: () => 'Title', documentYear: () => null, getPeople: () => [], distinctFamilies: new Set(),
  });
  const render = (entries) => renderer.renderDocument({ entries }, 'data/documents/example.json', 0);
  assert.ok(render([{ english: '1400, 1401 and 1400' }, { english: '1402' }]).includes('data-split-document'));
  assert.ok(!render([{ english: '1400, 1400 and 1401; 12345', german: '1402' }]).includes('data-split-document'));
  assert.ok(!renderer.renderDocument({ label: 'split', entries: [{ english: '1400 1401 1402' }] }, 'data/documents/example.json', 0).includes('data-split-document'));
  const labeled = renderer.renderDocument({ label: ['Franken', 'Important'], entries: [{ english: '1400 1401 1402' }] }, 'data/documents/example.json', 0);
  assert.equal((labeled.match(/data-edit-record-labels=/g) || []).length, 2);
  assert.match(labeled, /class="record-label record-label-button"/);
  assert.match(labeled, /data-split-document/);
  assert.match(labeled, /data-delete-document/);
  const proposed = renderer.renderDocument({ label: ['to review', 'Proposed: Franken'], entries: [] }, 'data/documents/example.json', 0);
  assert.match(proposed, /data-confirm-proposed-label="data\/documents\/example.json" data-proposed-label="Proposed: Franken"/);
  assert.doesNotMatch(renderer.renderDocument({ label: 'Proposed: ', entries: [] }, 'data/documents/example.json', 0), /data-confirm-proposed-label/);
  assert.match(render([]), /aria-label="Add record labels"/);
  state.canEditDocuments = false;
  assert.doesNotMatch(renderer.renderDocument({ label: 'Proposed: Franken', entries: [] }, 'data/documents/example.json', 0), /data-confirm-proposed-label/);
  assert.ok(!render([{ english: '1400 1401 1402' }]).includes('data-split-document'));
  assert.doesNotMatch(renderer.renderDocument({ label: 'Franken', entries: [] }, 'data/documents/example.json', 0), /data-edit-record-labels/);
});
