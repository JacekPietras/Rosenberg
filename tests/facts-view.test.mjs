import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

// Load the viewer's browser ES modules without a Node package manifest.
import { moduleUrl } from './browser-module.mjs';

const { renderFactsView } = await import(await moduleUrl(new URL('../docs/app/components/facts_view.js', import.meta.url)));
const { createDocumentRenderer } = await import(await moduleUrl(new URL('../docs/app/screens/documents.js', import.meta.url)));
const { createEntityScreens } = await import(await moduleUrl(new URL('../docs/app/screens/entities.js', import.meta.url)));
const { buildPersonPattern, buildPlacePattern } = await import(await moduleUrl(new URL('../docs/app/data/entities.js', import.meta.url)));
const { escapeHtml } = await import(await moduleUrl(new URL('../docs/app/rendering/html.js', import.meta.url)));
globalThis.window = { location: { hostname: 'example.github.io', pathname: '/Rosenberg/docs/' } };
const { documentNavigationUrl } = await import(await moduleUrl(new URL('../docs/app/rendering/navigation.js', import.meta.url)));
const options = { people: [{ id: 'eberhard', name: 'Eberhard' }], inlineMarkup: escapeHtml };

test('generic name pages include namesake effigies while ID pages distinguish them', async () => {
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
  assert.ok(renderPersonPage().includes(effigy.coverImage));
  assert.doesNotMatch(renderPersonPage(), /Ambiguous name|Choose a person/);
  state.person = 'vogt_zu_Durn';
  assert.ok(!renderPersonPage().includes(effigy.coverImage));
});

test('ID pages select their images and seals; name routes include all namesakes', () => {
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
  assert.doesNotMatch(nameHtml, /Ambiguous name|Choose a person/);
  for (const marker of ['generic-image', 'other-image', 'direct-image', 'person-id-image', 'seal-0', 'seal-1', 'seal-2']) {
    assert.ok(nameHtml.includes(marker), marker);
  }
});

test('name routes aggregate source identities while person and evidence IDs select their views', () => {
  const name = 'Hans von Rosenberg';
  const people = [{ id: 'hans_1513', name }, { id: 'hans_1516', name }];
  const path = 'data/documents/hans.json';
  const entries = [
    { date: '1359', facts: [{ text: `${name} appeared as a witness in 1359.` }] },
    { date: '1513', facts: [{ type: 'title', person: 'hans_1513', personTitle: ['Witness in 1513'] }] },
    { date: '1516', facts: [{ type: 'title', person: 'hans_1516', personTitle: ['Witness in 1516'] }] },
  ];
  const records = [0, 1].map((index) => ({
    name, _evidence: true, _treeKey: `@evidence/hans-${index}`,
    reconstruction: { name, key: `@evidence/hans-${index}`, status: 'source',
      mentions: [{ source: { path, pointer: `/entries/${index}/facts/0` }, field: 'person', date: entries[index].date }] },
  }));
  const state = { person: name, familyGraph: {
    valid: true, generated: true, records, reverse: new Map(), edges: [],
    view: 'facts', views: ['facts'], components: [],
    metadata: { schema: 4, coverage: { facts: {
      reconstructedPeople: 688, reconstructedRelationships: 476, conflicts: 0,
    } } },
  } };
  const { renderPersonPage } = createEntityScreens({
    state, getPeople: () => people, getDocuments: () => new Map([[path, { entries }]]),
    buildPersonPattern, escapeHtml, inlineMarkup: escapeHtml, markdownLinks: escapeHtml,
    dateSortValue: Number, formatDate: String, documentTitle: () => 'Document',
    documentNavigationUrl: (path, index) => `?document=${path}#entry-${index}`,
    displayedLanguagesFor: () => [],
  });
  const generic = renderPersonPage();
  for (const year of ['1513', '1516']) assert.ok(generic.includes(`Witness in ${year}`));
  assert.match(generic, /href="\?person=Hans%20von%20Rosenberg">Hans von Rosenberg<\/a> appeared as a witness in 1359/);
  assert.match(generic, /3 mentions/);
  assert.doesNotMatch(generic, /Choose a person|Ambiguous name|Source attestations|source identities|Reconstructed relationships|No resolved relationships/);

  state.person = 'hans_1513';
  const identified = renderPersonPage();
  assert.match(identified, /Witness in 1513/);
  assert.match(identified, /688 source identities|Reconstructed relationships/);
  assert.doesNotMatch(identified, /Witness in 1516|Source attestations/);

  state.person = '@evidence/hans-0';
  const evidence = renderPersonPage();
  assert.match(evidence, /Source attestations/);
  assert.match(evidence, /688 source identities|Reconstructed relationships/);
  assert.match(evidence, /href="\?person=Hans%20von%20Rosenberg">Hans von Rosenberg<\/a> appeared as a witness in 1359/);
  assert.doesNotMatch(evidence, /Witness in 1513|Witness in 1516/);

  // A name remains generic even if just one generated source identity is available.
  state.person = name;
  state.familyGraph.records = records.slice(0, 1);
  assert.match(renderPersonPage(), /3 mentions/);
  assert.doesNotMatch(renderPersonPage(), /Source attestations/);
});

test('prose facts link unregistered names from typed facts and source identities', async () => {
  const nameLink = /href="\?person=Hans%20von%20Rosenberg">Hans von Rosenberg<\/a> appeared as a witness/;
  const book = JSON.parse(await readFile(new URL('../data/books/bidermann_1751.json', import.meta.url), 'utf8'));
  const entry = book.entries.find((entry) => entry.facts?.some((fact) => fact.date === '1290' && fact.text === 'Hans von Rosenberg appeared as a witness in a document.'));
  assert.match(renderFactsView(entry.facts, options), nameLink);
  const prose = entry.facts.find((fact) => fact.date === '1290');
  assert.match(renderFactsView([prose], { ...options, personNames: ['Hans von Rosenberg'] }), nameLink);
  const { renderEntry } = createDocumentRenderer({
    state: { showFacts: true, familyGraph: { valid: true, records: [{ name: 'Hans von Rosenberg' }] } },
    escapeHtml, ...options, getPeople: () => options.people,
  });
  assert.match(renderEntry({ facts: [prose] }), nameLink);
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


test('source links are optional, preserve inline links, and address source entries', () => {
  const facts = [{ date: '1400', text: '[eberhard] held Boxberg.' }];
  assert.doesNotMatch(renderFactsView(facts, options), /fact-source-link|data-fact-source/);
  for (const path of ['data/books/example.json', 'data/documents/example.json', 'data/images/images.json']) {
    const url = documentNavigationUrl(path, 2);
    const html = renderFactsView(facts, { ...options, sourceHref: () => url });
    assert.match(html, /<li data-fact-source>/);
    assert.ok(html.includes(`class="fact-source-link" href="${escapeHtml(url)}"`));
    assert.match(html, /aria-label="Open fact source"/);
    assert.match(html, /href="\?person=eberhard"/);
    assert.doesNotMatch(html, /<a[^>]*><a/, 'source and person links are separate anchors');
    assert.doesNotMatch(html, />data\//, 'no visible source URLs added');
  }
});

test('person and place fact rows link to the correct source entry after sorting', () => {
  const people = options.people;
  const documents = new Map([
    ['data/books/example.json', { book: 'Example', entries: [{ facts: [{ date: '1400', text: '[eberhard] held Boxberg.' }] }] }],
    ['data/documents/example.json', { date: '1380', entries: [{}, { facts: [{ text: '[eberhard] visited Boxberg.' }] }] }],
    ['data/images/images.json', { entries: [{ facts: [{ date: '1390', text: '[eberhard] is depicted at Boxberg.' }] }] }],
  ]);
  const state = { person: 'eberhard' };
  const screens = createEntityScreens({
    state, getPeople: () => people, getPlaces: () => [{ id: 'boxberg', name: 'Boxberg', variations: ['Boxberg'] }],
    getDocuments: () => documents, buildPersonPattern, buildPlacePattern, escapeHtml,
    inlineMarkup: escapeHtml, markdownLinks: escapeHtml, documentNavigationUrl,
    dateSortValue: (date) => Number.parseInt(date, 10) || 0, formatDate: String,
    documentTitle: () => 'Source', displayedLanguagesFor: () => [], imageMarkup: () => '',
  });
  for (const kind of ['person', 'place']) {
    if (kind === 'place') { state.person = ''; state.place = 'boxberg'; }
    const html = kind === 'person' ? screens.renderPersonPage() : screens.renderPlacePage();
    const facts = html.match(/<section class="entity-facts">(.*?)<\/section>/)[1];
    const links = [...facts.matchAll(/class="fact-source-link" href="([^"]+)"/g)].map((match) => match[1]);
    assert.deepEqual(links, [
      documentNavigationUrl('data/documents/example.json', 1),
      documentNavigationUrl('data/images/images.json', 0),
      documentNavigationUrl('data/books/example.json', 0),
    ].map(escapeHtml), kind);
  }
});
