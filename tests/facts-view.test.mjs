import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

// Load the viewer's browser ES modules without a Node package manifest.
import { moduleUrl } from './browser-module.mjs';

const { renderFactsView } = await import(await moduleUrl(new URL('../docs/app/components/facts_view.js', import.meta.url)));
const { createDocumentRenderer } = await import(await moduleUrl(new URL('../docs/app/screens/documents.js', import.meta.url)));
const { createEntityScreens } = await import(await moduleUrl(new URL('../docs/app/screens/entities.js', import.meta.url)));
const { buildPersonPattern } = await import(await moduleUrl(new URL('../docs/app/data/entities.js', import.meta.url)));
const { escapeHtml } = await import(await moduleUrl(new URL('../docs/app/rendering/html.js', import.meta.url)));
globalThis.window = { location: { hostname: 'example.github.io', pathname: '/Rosenberg/docs/' } };
const options = { people: [{ id: 'eberhard', name: 'Eberhard' }], inlineMarkup: escapeHtml };

test('ambiguous name pages list anchors while ID pages distinguish namesake effigies', async () => {
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
  for (const person of ['vogt_zu_Lauda']) {
    state.person = person;
    assert.ok(renderPersonPage().includes(effigy.coverImage), person);
  }
  state.person = 'Eberhard von Rosenberg';
  assert.match(renderPersonPage(), /Ambiguous name/);
  assert.match(renderPersonPage(), /person=vogt_zu_Lauda/);
  assert.match(renderPersonPage(), /person=vogt_zu_Durn/);
  state.person = 'vogt_zu_Durn';
  assert.ok(!renderPersonPage().includes(effigy.coverImage));
});

test('ID pages exclude name-only images and seals; ambiguous routes list choices', () => {
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
  assert.match(nameHtml, /Ambiguous name/);
  assert.match(nameHtml, /person=lauda/);
  assert.match(nameHtml, /person=durn/);
  assert.ok(!nameHtml.includes('generic-image'));
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

const { factText, factPersonMatch, sourceFactDate } = await import(await moduleUrl(new URL('../docs/app/rendering/facts.js', import.meta.url)));

test('typed relationship facts render all supported relations with ID links and title lists', () => {
  const people = [{ id: 'arnold', name: 'Arnold von Rosenberg' }, { id: 'eberhard', name: 'Eberhard von Rosenberg' }];
  for (const [type, phrase] of [['parent', 'is parent of'], ['sibling', 'is sibling of'], ['spouse', 'is spouse of'], ['kin', 'is kin of']]) {
    const fact = { type, person: 'arnold', personTitle: ['der Ältere', 'Ritter'], of: 'eberhard', ofTitle: ['der Jüngere'], ...(type === 'kin' ? { term: 'Vetter' } : {}) };
    const html = renderFactsView([fact], { ...options, people });
    assert.match(html, /href="\?person=arnold">Arnold von Rosenberg<\/a>, der Ältere, Ritter/);
    assert.match(html, /href="\?person=eberhard">Eberhard von Rosenberg<\/a>, der Jüngere/);
    assert.ok(html.includes(phrase));
    assert.equal(factText(fact, people), `Arnold von Rosenberg, der Ältere, Ritter ${phrase} Eberhard von Rosenberg, der Jüngere${type === 'kin' ? ' (Vetter)' : ''}.`);
  }
});

test('typed title facts generate readable assertions and unknown names link to name routes', () => {
  const fact = { type: 'title', person: 'Unknown von Rosenberg', personTitle: ['der Jüngere', 'Ritter'] };
  const html = renderFactsView([fact], options);
  assert.match(html, /href="\?person=Unknown%20von%20Rosenberg">Unknown von Rosenberg<\/a> is designated der Jüngere, Ritter\./);
  assert.equal(factText(fact), 'Unknown von Rosenberg is designated der Jüngere, Ritter.');
  const noTitles = renderFactsView([{ type: 'spouse', person: 'A', of: 'B' }], options);
  assert.doesNotMatch(noTitles, /undefined|null|<\/a>,/);
});

test('typed names, title lists, and kinship terms are escaped without interpreting markup', () => {
  const html = renderFactsView([{ type: 'kin', person: '<img src=x>', personTitle: ['<script>'], of: 'B & C', term: '<b>Vetter</b>' }], options);
  assert.match(html, /&lt;img src=x&gt;/);
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /B &amp; C/);
  assert.match(html, /&lt;b&gt;Vetter&lt;\/b&gt;/);
  assert.doesNotMatch(html, /<img|<script|<b>/);
});

test('explicit null dates suppress inherited dates and date grouping restarts correctly', () => {
  const fact = { type: 'title', person: 'A', personTitle: ['Ritter'] };
  const html = renderFactsView([fact, { ...fact, date: null }, fact], { ...options, defaultDate: '1395' });
  assert.equal((html.match(/datetime="1395"/g) || []).length, 2);
  assert.equal((html.match(/>Undated</g) || []).length, 1);
  assert.equal(sourceFactDate({ date: null }, { date: '1395' }, {}, 'data/documents/a.json'), '');
  for (const path of ['data/books/a.json', 'data/notes/a.json']) {
    assert.equal(sourceFactDate(fact, { date: '1872' }, { date: '1871' }, path), '');
    assert.equal(sourceFactDate({ ...fact, date: '1395' }, { date: '1872' }, {}, path), '1395');
  }
});

test('typed participant matching preserves exact ID identity and ambiguous name discovery', () => {
  const people = [{ id: 'lauda', name: 'Eberhard' }, { id: 'durn', name: 'Eberhard' }];
  assert.equal(factPersonMatch({ type: 'spouse', person: 'X', of: 'lauda' }, 'lauda', people), 'direct');
  assert.equal(factPersonMatch({ type: 'title', person: 'durn' }, 'lauda', people), '');
  assert.equal(factPersonMatch({ type: 'title', person: 'Eberhard' }, 'lauda', people), 'ambiguous');
  assert.equal(factPersonMatch({ type: 'title', person: 'LAUDA' }, 'lauda', people), '');
  assert.equal(factPersonMatch({ type: 'title', person: 'durn' }, 'Eberhard', people), 'direct');
});

function typedPersonScreen(state, people, documents) {
  return createEntityScreens({
    state, getPeople: () => people, getDocuments: () => new Map(documents),
    buildPersonPattern, escapeHtml, inlineMarkup: escapeHtml, markdownLinks: escapeHtml,
    dateSortValue: (date) => Number.parseInt(date, 10) || 0, formatDate: String,
    documentTitle: () => 'Source document', documentNavigationUrl: (path, index) => `?record=${path}&entry=${index}`,
    displayedLanguagesFor: () => [], imageMarkup: () => '',
  }).renderPersonPage();
}

test('person pages include typed facts on either side and retain source links without merging homonyms', () => {
  const people = [{ id: 'lauda', name: 'Eberhard' }, { id: 'durn', name: 'Eberhard' }];
  const documents = [['data/documents/a.json', { date: '1395', entries: [{ source: 'Charter A', facts: [
    { type: 'spouse', person: 'Else', of: 'lauda', personTitle: ['direct marker'] },
    { type: 'title', person: 'Eberhard', personTitle: ['unresolved marker'] },
    { type: 'title', person: 'durn', personTitle: ['other identity marker'] },
  ] }] }]];
  const html = typedPersonScreen({ person: 'lauda' }, people, documents);
  assert.match(html, /direct marker/);
  assert.match(html, /unresolved marker/);
  assert.doesNotMatch(html, /other identity marker/);
  assert.match(html, /class="entity-fact-ambiguous"/);
  assert.match(html, /data-document-href="\?record=data\/documents\/a.json&amp;entry=0"/);
  assert.match(html, /Charter A/);
  assert.match(html, /datetime="1395"/);
});

test('aggregated person facts never inherit book or note dates and retain explicit event dates', () => {
  const people = [{ id: 'arnold', name: 'Arnold' }];
  const documents = ['books', 'notes'].map((kind) => [`data/${kind}/a.json`, { date: '1872', entries: [{ date: '1871', facts: [
    { type: 'title', person: 'arnold', personTitle: ['Undated designation'] },
    { type: 'title', person: 'arnold', personTitle: ['Dated designation'], date: '1395' },
    { type: 'title', person: 'arnold', personTitle: ['Unknown date designation'], date: null },
  ] }] }]);
  const html = typedPersonScreen({ person: 'arnold' }, people, documents);
  assert.match(html, /Undated designation/);
  assert.match(html, /datetime="1395"/);
  assert.doesNotMatch(html, /datetime="187[12]"/);
  assert.match(html, />Undated</);
});

test('unregistered typed names have working generic person pages', () => {
  const html = typedPersonScreen({ person: 'Unknown Arnold' }, [], [['data/documents/a.json', { date: '1395', entries: [{ facts: [
    { type: 'title', person: 'Unknown Arnold', personTitle: ['Ritter'] },
  ] }] }]]);
  assert.match(html, /<h2>Unknown Arnold<\/h2>/);
  assert.match(html, /is designated Ritter/);
  assert.doesNotMatch(html, /Person not found/);
});
