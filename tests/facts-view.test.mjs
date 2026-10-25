import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

// Load the viewer's browser ES modules without a Node package manifest.
async function moduleUrl(path) {
  let source = await readFile(path, 'utf8');
  const imports = [...source.matchAll(/from '([^']+)'/g)];
  for (const [statement, specifier] of imports) {
    const dependency = new URL(specifier, path);
    dependency.search = '';
    source = source.replace(statement, `from '${await moduleUrl(dependency)}'`);
  }
  return `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
}
const { renderFactsView } = await import(await moduleUrl(new URL('../docs/app/components/facts_view.js', import.meta.url)));
const { createDocumentRenderer } = await import(await moduleUrl(new URL('../docs/app/screens/documents.js', import.meta.url)));
const { createEntityScreens } = await import(await moduleUrl(new URL('../docs/app/screens/entities.js', import.meta.url)));
const { buildPersonPattern } = await import(await moduleUrl(new URL('../docs/app/data/entities.js', import.meta.url)));
const { escapeHtml } = await import(await moduleUrl(new URL('../docs/app/rendering/html.js', import.meta.url)));
const options = { people: [{ id: 'eberhard', name: 'Eberhard' }], inlineMarkup: escapeHtml };

test('person name pages include ID-linked effigies while ID pages distinguish namesakes', async () => {
  const people = JSON.parse(await readFile(new URL('../data/people.json', import.meta.url), 'utf8'));
  const images = JSON.parse(await readFile(new URL('../data/images/images.json', import.meta.url), 'utf8'));
  const effigy = images.entries.find((entry) => entry.title === '[vogt_zu_Lauda]');
  const state = {};
  const { renderPersonPage } = createEntityScreens({
    state, getPeople: () => people,
    getDocuments: () => new Map([['data/images/images.json', { entries: [effigy] }]]),
    buildPersonPattern, escapeHtml, inlineMarkup: escapeHtml, markdownLinks: escapeHtml,
    dateSortValue: () => 0, formatDate: String,
    documentTitle: () => 'Images', documentNavigationUrl: () => '#',
    displayedLanguagesFor: () => [], imageMarkup: () => '',
  });
  for (const person of ['Eberhard von Rosenberg', 'eberhard von rosenberg', 'vogt_zu_Lauda']) {
    state.person = person;
    assert.ok(renderPersonPage().includes(effigy.coverImage), person);
  }
  state.person = 'vogt_zu_Durn';
  assert.ok(!renderPersonPage().includes(effigy.coverImage));
});

test('ID pages exclude name-only images and seals but name pages retain them', () => {
  const name = 'Eberhard von Rosenberg';
  const people = [{ id: 'lauda', name }, { id: 'durn', name }];
  const state = { person: 'lauda' };
  const entries = [
    { title: name, coverImage: 'generic-image' },
    { title: `${name} [durn]`, coverImage: 'other-image' },
    { title: '[lauda]', coverImage: 'direct-image' },
    { title: name, personId: 'lauda', coverImage: 'person-id-image' },
  ].map((entry) => ({ ...entry, type: 'link', url: 'https://example.com/collection' }));
  const seals = [name, `${name} [durn]`, '[lauda]'].map((person, index) => ({
    person, position: '0.5,0.5', size: 0.1, marker: `seal-${index}`,
  }));
  const { renderPersonPage } = createEntityScreens({
    state, getPeople: () => people,
    getDocuments: () => new Map([
      ['data/images/images.json', { entries }],
      ['data/documents/example.json', { entries: [{ img: { src: 'seal.jpg', seals } }] }],
    ]),
    buildPersonPattern, escapeHtml, inlineMarkup: escapeHtml, markdownLinks: escapeHtml,
    dateSortValue: () => 0, formatDate: String,
    documentTitle: () => 'Document', documentNavigationUrl: () => '#',
    displayedLanguagesFor: () => [], imageMarkup: (node, [seal]) => seal.marker,
  });
  const strictHtml = renderPersonPage();
  for (const marker of ['direct-image', 'person-id-image', 'seal-2']) assert.ok(strictHtml.includes(marker), marker);
  for (const marker of ['generic-image', 'other-image', 'seal-0', 'seal-1']) assert.ok(!strictHtml.includes(marker), marker);
  state.person = name;
  const nameHtml = renderPersonPage();
  for (const marker of ['generic-image', 'other-image', 'direct-image', 'person-id-image', 'seal-0', 'seal-1', 'seal-2']) {
    assert.ok(nameHtml.includes(marker), marker);
  }
});

test('shared facts view formats dates, groups repeated dates, and preserves person links', () => {
  const html = renderFactsView([
    { date: '1383', text: 'Wife of [eberhard].' },
    { date: '1383', text: 'Another fact.' },
    { date: '1421-03-02', text: 'Later fact.' },
    { text: 'Undated fact.' },
    'Legacy fact.',
  ], options);
  assert.match(html, /class="facts facts-view"/);
  assert.equal((html.match(/datetime="1383"/g) || []).length, 1);
  assert.match(html, /class="fact-date" aria-hidden="true"/);
  assert.match(html, /1421, March 2/);
  assert.match(html, /href="\?person=eberhard"/);
  assert.match(html, /Undated/);
  assert.match(html, /Legacy fact\./);
});

test('document facts use the shared view and respect the facts toggle', () => {
  const state = { showFacts: true };
  const { renderEntry } = createDocumentRenderer({ state, escapeHtml, ...options, getPeople: () => options.people });
  const facts = [{ date: '1383', text: 'Wife of [eberhard].' }];
  assert.equal(renderEntry({ facts }), `<article class="entry">${renderFactsView(facts, options)}</article>`);
  state.showFacts = false;
  assert.equal(renderEntry({ facts }), '<article class="entry"></article>');
});

test('shared facts view preserves the person screen ambiguity styling', () => {
  const html = renderFactsView([{ text: 'Eberhard' }], {
    ...options, itemClass: () => ' class="entity-fact-ambiguous"',
  });
  assert.match(html, /<li class="entity-fact-ambiguous">/);
});

test('document facts inherit the entry or document date while explicit fact dates take priority', () => {
  const { formatDate } = { formatDate: (date) => date };
  const { renderDocument } = createDocumentRenderer({
    state: { showFacts: true }, escapeHtml, formatDate, ...options,
    getPeople: () => options.people,
    documentTitle: () => 'Document', documentYear: () => '1383',
    entryAnchor: () => 'entry',
  });
  const doc = { date: '1383', entries: [
    { facts: ['Legacy fact.', { text: 'Another fact.' }, { date: '1382', text: 'Earlier event.' }] },
    { date: '1384', facts: [{ text: 'Entry date.' }] },
  ] };
  const html = renderDocument(doc, 'data/documents/example.json', 0);
  assert.match(html, /datetime="1383"/);
  assert.match(html, /datetime="1382"/);
  assert.match(html, /datetime="1384"/);
  assert.doesNotMatch(html, /Undated/);
  assert.equal((html.match(/datetime="1383"/g) || []).length, 1);
  assert.equal(doc.entries[0].facts[0], 'Legacy fact.');
});

test('a book publication date is not used as a fact date', () => {
  const { renderDocument } = createDocumentRenderer({
    state: { showFacts: true }, escapeHtml, formatDate: (date) => date, ...options,
    getPeople: () => options.people,
    documentTitle: () => 'Book', documentYear: () => '1872',
    markdownLinks: escapeHtml, entryAnchor: () => 'entry',
  });
  const html = renderDocument({ date: '1872', entries: [{ facts: [{ text: 'Undated fact.' }] }] }, 'data/books/example.json', 0);
  assert.match(html, /Undated/);
  assert.doesNotMatch(html, /datetime="1872"/);
});
