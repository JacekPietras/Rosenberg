import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { webcrypto } from 'node:crypto';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

globalThis.crypto ||= webcrypto;
const { buildRelationshipGraph, resolvePerson, verifyFamilyGraph, evidenceFingerprint, canonicalEvidence, registryIdentities, focusFamilyGraph, expandEvidenceGraph, remapSourcePerson } =
  await import(await moduleUrl(new URL('../docs/app/data/relationships.js', import.meta.url)));
const { relationshipPanel } = await import(await moduleUrl(new URL('../docs/app/rendering/relationships.js', import.meta.url)));
const { renderPeopleTree } = await import(await moduleUrl(new URL('../docs/app/screens/tree.js', import.meta.url)));
const { createDataLoader } = await import(await moduleUrl(new URL('../docs/app/data/loader.js', import.meta.url)));
const { parsePeople, parsePlaces, buildPersonPattern } = await import(await moduleUrl(new URL('../docs/app/data/entities.js', import.meta.url)));
const { createRepository } = await import(await moduleUrl(new URL('../docs/app/data/repository.js', import.meta.url)));
const { loadPreferences } = await import(await moduleUrl(new URL('../docs/app/state/preferences.js', import.meta.url)));
const { renderActiveScreen } = await import(await moduleUrl(new URL('../docs/app/screens/router-view.js', import.meta.url)));
const { createEntityScreens } = await import(await moduleUrl(new URL('../docs/app/screens/entities.js', import.meta.url)));
const { escapeHtml } = await import(await moduleUrl(new URL('../docs/app/rendering/html.js', import.meta.url)));
const source = { path: 'data/documents/deep/event.json', pointer: '/entries/0/facts/0', fingerprint: '' };

async function fixture({ empty = false } = {}) {
  const document = { date: '1393', entries: [{ source: 'Charter', facts: [{ type: 'parent', person: 'a', of: 'c' }], guesses: [{ type: 'spouse', person: 'a', of: 'b' }] }] };
  const ref = { ...source, fingerprint: await evidenceFingerprint(document.entries[0].facts[0]) };
  const people = [
    { id: 'a', name: 'Same', relationships: empty ? [] : [{ type: 'parent', of: 'c', derivations: [
      { view: 'facts', identity: 'anchored', usesGuesses: false, sources: [ref] },
      { view: 'with-guesses', identity: 'anchored', usesGuesses: false, sources: [ref] },
    ] }] },
    { id: 'b', name: 'Same', relationships: [] },
    { id: 'c', name: 'Child', relationships: [] },
  ];
  const files = new Map([
    [source.path, document], ['data/people.json', people], ['data/places.json', []], ['data/names.md', 'Same, Sameus'],
  ]);
  const inputs = Object.fromEntries(await Promise.all([...files].map(async ([path, value]) => [path, await evidenceFingerprint(path === 'data/people.json' ? registryIdentities(value) : value)])));
  people[0].familyGraph = { schema: 1, engine: '1', policy: '1', configuration: { searchLimit: 10000 }, views: ['facts', 'with-guesses'], inputs,
    fingerprint: await evidenceFingerprint(inputs), coverage: { facts: { unresolvedMentions: 2, omittedRelationships: 1, conflicts: 0 } } };
  const repository = { getJson: async (path) => files.get(path), getText: async (path) => files.get(path) };
  return { people, documents: new Map([[source.path, document]]), repository, files };
}

test('Python and browser fingerprint encodings agree for all JSON types', async () => {
  const value = { 'ä': ['ß', '😀', true, null, 1, 1.25, 1e-9, -0, 49.6789], nested: { value: '\n' } };
  const python = JSON.parse(execFileSync('python3', ['-c',
    'import sys,json; sys.path.insert(0,"scripts"); from family_graph.model import fingerprint,canonical; v=json.load(sys.stdin); print(json.dumps([canonical(v),fingerprint(v)]))',
  ], { cwd: new URL('..', import.meta.url), encoding: 'utf8', input: JSON.stringify(value) }));
  assert.equal(canonicalEvidence(value), python[0]);
  assert.equal(await evidenceFingerprint(value), python[1]);
});

test('exact IDs and unique names resolve; ambiguous names never select a record', () => {
  const people = [{ id: 'a', name: 'Same' }, { id: 'b', name: 'Same' }, { name: 'Other' }];
  assert.equal(resolvePerson(people, 'a').person.id, 'a');
  assert.equal(resolvePerson(people, 'same').ambiguous, true);
  assert.equal(resolvePerson(people, 'Same').person, undefined);
  assert.equal(resolvePerson(people, 'OTHER').person.name, 'Other');
  assert.equal(resolvePerson(people, 'A').person, undefined);
});

test('generated edges are excluded until the complete build is verified', async () => {
  const data = await fixture();
  assert.equal(buildRelationshipGraph(data.people).edges.length, 0);
  const verification = await verifyFamilyGraph(data.people, data.documents, data.repository);
  assert.equal(verification.valid, true, verification.reason);
  const graph = buildRelationshipGraph(data.people, { verification });
  assert.equal(graph.edges.length, 1);
  assert.equal(graph.reverse.get('c')[0].person, 'a');
  assert.doesNotMatch(renderPeopleTree(data.people, data.documents, { graph }), /Reconstructed relationships/);
  assert.match(renderPeopleTree(data.people, data.documents, { graph }), /class="facts facts-view"/);
});

test('inherited context, new sources, and name inputs invalidate evidence', async () => {
  for (const change of ['context', 'source', 'names', 'registry', 'pointer']) {
    const data = await fixture();
    if (change === 'context') data.documents.get(source.path).date = '1400';
    if (change === 'source') data.documents.set('data/notes/new.json', { facts: [] });
    if (change === 'names') data.files.set('data/names.md', 'Changed');
    if (change === 'registry') data.people[0].name = 'Changed';
    if (change === 'pointer') data.people[0].relationships[0].derivations[0].sources[0].pointer = '/entries/0/facts/1';
    const verification = await verifyFamilyGraph(data.people, data.documents, data.repository);
    assert.equal(verification.valid, false, change);
    const graph = buildRelationshipGraph(data.people, { verification });
    assert.equal(graph.edges.length, 0);
    const html = renderPeopleTree(data.people, data.documents, { graph });
    assert.match(html, /Relationships need refreshing/);
    assert.doesNotMatch(html, /Build input changed|Rebuild family relationships to verify/);
  }
});

test('empty and identical views remain available; unavailable preferences fall back', async () => {
  const data = await fixture({ empty: true });
  const graph = buildRelationshipGraph(data.people, { view: 'with-guesses', verification: { valid: true } });
  assert.deepEqual(graph.views, ['facts', 'with-guesses']);
  assert.equal(graph.view, 'with-guesses');
  assert.equal(graph.edges.length, 0);
  data.people[0].familyGraph.views = ['facts'];
  assert.equal(buildRelationshipGraph(data.people, { view: 'with-guesses', verification: { valid: true } }).view, 'facts');
  assert.equal(loadPreferences({ getItem: () => '{"familyView":"anything"}' }).familyView, 'facts');
});

test('multiple marriages never confer parentage; kin terms and uncertainty are separate', async () => {
  const { people } = await fixture();
  people.push({ id: 'd', name: 'Other spouse', relationships: [] });
  const d = (identity = 'anchored', usesGuesses = false) => ({ view: 'with-guesses', identity, usesGuesses, sources: [source] });
  people[0].relationships.push({ type: 'spouse', of: 'b', derivations: [d()] }, { type: 'spouse', of: 'd', derivations: [d('inferred')] },
    { type: 'kin', of: 'b', term: 'Vetter', derivations: [d('inferred', true)] });
  const graph = buildRelationshipGraph(people, { view: 'with-guesses', verification: { valid: true } });
  assert.equal(graph.valid, true, graph.reason);
  assert.equal(graph.edges.filter((edge) => edge.type === 'parent').length, 1);
  const html = relationshipPanel(graph);
  assert.match(html, /Vetter/);
  assert.match(html, /inferred identity/);
  assert.match(html, /depends on guesses/);
  assert.equal(graph.edges.some((edge) => edge.person === 'b' && edge.of === 'c'), false);
});

test('ambiguous generated endpoints and parentage cycles suppress accepted graph', async () => {
  const { people } = await fixture();
  people[0].relationships[0].of = 'Same';
  assert.equal(buildRelationshipGraph(people, { verification: { valid: true } }).valid, false);
  people[0].relationships[0].of = 'c';
  people[2].relationships = [{ type: 'parent', of: 'a', derivations: people[0].relationships[0].derivations }];
  assert.match(buildRelationshipGraph(people, { verification: { valid: true } }).reason, /cycle/);
});

test('distinct no-ID records get distinct rendering keys; generated and legacy cannot mix', () => {
  const people = [{ name: 'Same' }, { name: 'Same' }, { id: 'a', name: 'Parent', children: ['Same'] }];
  const graph = buildRelationshipGraph(people);
  assert.equal(new Set(graph.records.map((person) => person._treeKey)).size, 3);
  assert.equal(graph.edges.length, 0);
  const collision = buildRelationshipGraph([{ name: 'Alex' }, { id: '@registry/0', name: 'Bea' }]);
  assert.deepEqual(collision.records.map((record) => record._treeKey), ['@registry/0~', '@registry/0']);
  people[0].relationships = [];
  assert.equal(buildRelationshipGraph(people, { verification: { valid: true } }).valid, false);
});

test('typed mention dates inherit document intervals and exclude publication years', async () => {
  const data = await fixture();
  data.documents.set('data/books/test.json', { book: 'Book', date: '1900', entries: [{ facts: [
    { type: 'title', person: 'a', personTitle: ['Ritter'], date: '1400' },
    { type: 'title', person: 'a', personTitle: ['Ritter'] },
  ] }] });
  data.documents.get(source.path).date = '1393-1394';
  const graph = buildRelationshipGraph(data.people, { verification: { valid: true } });
  const html = renderPeopleTree(data.people, data.documents, { graph });
  assert.match(html, /mentioned: \[1393-1400\]/);
  assert.doesNotMatch(html, /1900/);
});

test('local and published discovery return recursive sources plus watched build inputs', async () => {
  const tree = ['data/documents/deep/example.json', 'data/people.json', 'data/names.md', 'scripts/family_graph/graph.py', 'README.md'];
  const published = createRepository({ location: { hostname: 'example.github.io', pathname: '/Rosenberg/docs/' },
    fetchFunction: async () => ({ ok: true, json: async () => ({ tree: tree.map((path) => ({ path, type: 'blob', sha: 'abc' })) }) }) });
  const files = await published.getRepositoryFiles();
  assert.equal(files.length, 4);
  const local = createRepository({ location: { hostname: 'localhost', pathname: '/docs/' },
    fetchFunction: async () => ({ ok: true, json: async () => files }) });
  assert.deepEqual(await local.getRepositoryFiles(), files);
  const server = await readFile(new URL('../docs/serve.py', import.meta.url), 'utf8');
  assert.ok(server.includes('folder.rglob("*.json")'));
});

test('active loader filters watched non-source files and verifies evidence views', async () => {
  const data = await fixture();
  const state = { recordLabels: [], sealNames: [], imageRegions: [], active: 'tree', familyView: 'with-guesses' };
  const repository = {
    ...data.repository,
    getRepositoryFiles: async () => [...data.files.keys()].map((path) => ({ path })),
    getText: async (path) => path === 'data/people.json' ? JSON.stringify(data.people)
      : path === 'data/places.json' || path === 'docs/assets/calibration-cities.json' ? '[]'
        : data.files.get(path) || '',
  };
  let renders = 0;
  const validityAtRender = [];
  const loader = createDataLoader({ repository, state, parsePeople, parsePlaces,
    buildPersonPattern: () => [], buildPlacePattern: () => null,
    bookSortYear: () => 0, recordHasMissingSourceOrUrl: () => false,
    missingRecordLabel: 'missing', greyRecordLabels: [], savePreferences() {}, renderTabs() {},
    renderActive: async () => { renders++; validityAtRender.push(state.familyGraph.valid); } });
  await loader.loadAll();
  assert.equal(renders, 2);
  assert.deepEqual(validityAtRender, [false, true]);
  assert.equal(state.familyGraph.valid, true, state.familyGraph.reason);
  assert.equal(state.familyView, 'with-guesses');
  assert.equal(state.documents.size, 1);
});

test('a book renders before unrelated source files finish loading', async () => {
  const data = await fixture();
  const book = 'data/books/example.json';
  const delayed = 'data/documents/delayed.json';
  let releaseDocument;
  const documentReady = new Promise((resolve) => { releaseDocument = resolve; });
  let firstRender;
  let tabsRendered = false;
  const rendered = new Promise((resolve) => { firstRender = resolve; });
  const state = { recordLabels: [], sealNames: [], imageRegions: [], active: 'books', familyView: 'facts' };
  const repository = {
    ...data.repository,
    getRepositoryFiles: async () => [...data.files.keys(), book, delayed].map((path) => ({ path })),
    getText: async (path) => path === 'data/people.json' ? JSON.stringify(data.people)
      : path === 'data/places.json' || path === 'docs/assets/calibration-cities.json' ? '[]' : data.files.get(path) || '',
    getJson: async (path) => path === book ? { book: 'Example' }
      : path === delayed ? documentReady : data.repository.getJson(path),
  };
  const loader = createDataLoader({ repository, state, parsePeople, parsePlaces,
    buildPersonPattern: () => [], buildPlacePattern: () => null,
    bookSortYear: () => 0, recordHasMissingSourceOrUrl: () => false,
    missingRecordLabel: 'missing', greyRecordLabels: [], savePreferences() {}, renderTabs() { tabsRendered = true; },
    renderActive: async () => { if (state.active === book) firstRender(); } });
  const loading = loader.loadAll();
  await rendered;
  assert.equal(tabsRendered, true);
  assert.equal(state.documents.get(book).book, 'Example');
  assert.equal(state.documents.has(delayed), false);
  releaseDocument({});
  await loading;
  assert.equal(state.documents.has(delayed), true);
});

test('the tree mode control passes an available view explicitly to viewer state', async () => {
  const data = await fixture();
  let changeHandler, selected;
  const graph = buildRelationshipGraph(data.people, { verification: { valid: true } });
  const state = { active: 'tree', personRecords: data.people, documents: data.documents, familyGraph: graph,
    changeFamilyView: async (view) => { selected = view; } };
  const content = { innerHTML: '', querySelector: () => ({ addEventListener: (type, handler) => { changeHandler = handler; } }) };
  await renderActiveScreen({ state, content, status: { textContent: '', classList: { remove() {} } },
    renderPeopleTree, setupPeopleTreeZoom() {} });
  assert.match(content.innerHTML, /data-family-view/);
  await changeHandler({ target: { value: 'with-guesses' } });
  assert.equal(selected, 'with-guesses');
  assert.equal(state.familyView, 'with-guesses');
  selected = null;
  await changeHandler({ target: { value: 'unavailable' } });
  assert.equal(selected, null);
});

function loaderFor(data, { rebuild, local = true } = {}) {
  const state = { recordLabels: [], sealNames: [], imageRegions: [], active: 'tree', familyView: 'with-guesses' };
  let renders = 0, progress = 0;
  const repository = {
    ...data.repository,
    isLocalServer: async () => local,
    rebuildFamilyGraph: rebuild,
    getRepositoryFiles: async () => [...data.files.keys()].map((path) => ({ path })),
    getText: async (path) => path === 'data/people.json' ? JSON.stringify(data.people)
      : path === 'data/places.json' || path === 'docs/assets/calibration-cities.json' ? '[]'
        : data.files.get(path) || '',
  };
  const loader = createDataLoader({ repository, state, parsePeople, parsePlaces,
    buildPersonPattern: () => [], buildPlacePattern: () => null,
    bookSortYear: () => 0, recordHasMissingSourceOrUrl: () => false,
    missingRecordLabel: 'missing', greyRecordLabels: [], savePreferences() {}, renderTabs() {},
    onFamilyRebuild: () => { progress++; }, renderActive: async () => { renders++; } });
  return { state, loader, counts: () => ({ renders, progress }) };
}

async function updateFixtureBuild(data) {
  const metadata = data.tree || data.people[0].familyGraph;
  metadata.inputs[source.path] = await evidenceFingerprint(data.documents.get(source.path));
  metadata.fingerprint = await evidenceFingerprint(metadata.inputs);
}

test('stale local evidence automatically rebuilds once and reloads the verified graph', async () => {
  const data = await fixture();
  data.documents.get(source.path).date = '1400';
  let rebuilds = 0;
  const { loader, state, counts } = loaderFor(data, { rebuild: async () => { rebuilds++; await updateFixtureBuild(data); } });
  await Promise.all([loader.loadAll(), loader.loadAll()]);
  await loader.waitForFamilyRebuild();
  assert.equal(rebuilds, 1);
  assert.equal(state.familyGraph.valid, true, state.familyGraph.reason);
  assert.equal(state.familyGraph.edges.length, 1);
  assert.equal(state.familyView, 'with-guesses');
  assert.equal(state.familyGraph.canRebuild, true);
  assert.doesNotMatch(renderPeopleTree(state.personRecords, state.documents, { graph: state.familyGraph }), /data-family-rebuild>/);
  assert.deepEqual(counts(), { renders: 3, progress: 1 });
});

test('other screens render before a slow family rebuild finishes', async () => {
  const data = await fixture();
  data.documents.get(source.path).date = '1400';
  let finish;
  const pending = new Promise((resolve) => { finish = resolve; });
  const { loader, state, counts } = loaderFor(data, { rebuild: async () => {
    await pending;
    await updateFixtureBuild(data);
  } });
  state.active = 'documents';
  await loader.loadAll();
  assert.equal(counts().renders, 1);
  assert.equal(state.familyGraph.rebuilding, true);
  finish();
  await loader.waitForFamilyRebuild();
  assert.equal(state.familyGraph.valid, true);
  assert.equal(state.familyGraph.rebuilding, false);
  assert.equal(counts().renders, 1);
});

test('rebuild failures retain hidden stale edges and a working retry action', async () => {
  const data = await fixture();
  data.documents.get(source.path).date = '1400';
  let rebuilds = 0;
  const { loader, state } = loaderFor(data, { rebuild: async () => {
    if (++rebuilds === 1) throw new Error('Invalid source date');
    await updateFixtureBuild(data);
  } });
  await loader.loadAll();
  await loader.waitForFamilyRebuild();
  assert.equal(rebuilds, 1);
  assert.equal(state.familyGraph.valid, false);
  assert.equal(state.familyGraph.edges.length, 0);
  const html = renderPeopleTree(state.personRecords, state.documents, { graph: state.familyGraph });
  assert.match(html, /data-family-rebuild>Retry rebuild/);
  assert.match(html, /Invalid source date/);
  await loader.rebuildFamilyGraph();
  assert.equal(rebuilds, 2);
  assert.equal(state.familyGraph.valid, true);
  assert.doesNotMatch(renderPeopleTree(state.personRecords, state.documents, { graph: state.familyGraph }), /data-family-rebuild>/);
});

test('a second input change cannot cause an automatic rebuild loop', async () => {
  const data = await fixture();
  data.documents.get(source.path).date = '1400';
  let rebuilds = 0;
  const { loader, state } = loaderFor(data, { rebuild: async () => {
    rebuilds++;
    await updateFixtureBuild(data);
    data.documents.get(source.path).date = '1401';
  } });
  await loader.loadAll();
  await loader.waitForFamilyRebuild();
  assert.equal(rebuilds, 1);
  assert.equal(state.familyGraph.valid, false);
  assert.equal(state.familyGraph.canRebuild, true);
});

test('hosted pages do not POST rebuilds to a static site', async () => {
  const data = await fixture();
  data.documents.get(source.path).date = '1400';
  const { loader, state } = loaderFor(data, { local: false, rebuild: async () => { assert.fail('static site cannot run Python'); } });
  await loader.loadAll();
  assert.equal(state.familyGraph.valid, false);
  assert.equal(state.familyGraph.canRebuild, false);
  assert.match(renderPeopleTree(state.personRecords, state.documents, { graph: state.familyGraph }), /Open the local viewer to rebuild/);
});

test('repository coalesces concurrent rebuild requests and allows retry after failure', async () => {
  let requests = 0, finish;
  const repository = createRepository({ location: { hostname: 'localhost', pathname: '/docs/' },
    fetchFunction: async (url, options) => {
      requests++;
      assert.equal(url, '/api/rebuild-family-tree');
      assert.equal(options.method, 'POST');
      return new Promise((resolve) => { finish = resolve; });
    } });
  const first = repository.rebuildFamilyGraph();
  const concurrent = repository.rebuildFamilyGraph();
  assert.equal(first, concurrent);
  assert.equal(requests, 1);
  finish({ ok: false, status: 422, json: async () => ({ error: 'Source validation failed' }) });
  await assert.rejects(first, /Source validation failed/);
  const retry = repository.rebuildFamilyGraph();
  assert.equal(requests, 2);
  finish({ ok: true, status: 200, json: async () => ({ ok: true }) });
  await retry;
  assert.equal(repository.revision, 1);
});

test('the rebuild button disables itself and reports a failed attempt with retry', async () => {
  const data = await fixture();
  let click, rebuilds = 0;
  const button = { disabled: false, textContent: '', addEventListener: (type, callback) => { click = callback; } };
  const message = { textContent: '' };
  const graph = buildRelationshipGraph(data.people, { verification: { valid: true } });
  graph.canRebuild = true;
  graph.valid = false;
  graph.rebuildError = 'Try again';
  const content = { innerHTML: '', querySelector: (selector) => selector === '[data-family-rebuild]' ? button
    : selector === '[data-family-rebuild-status]' ? message : null };
  const state = { active: 'tree', personRecords: data.people, documents: data.documents, familyGraph: graph,
    rebuildFamilyGraph: async () => { rebuilds++; assert.equal(button.disabled, true); throw new Error('Try again'); } };
  await renderActiveScreen({ state, content, status: { textContent: '', classList: { remove() {} } }, renderPeopleTree, setupPeopleTreeZoom() {} });
  await click({ currentTarget: button });
  assert.equal(rebuilds, 1);
  assert.equal(button.disabled, false);
  assert.equal(button.textContent, 'Retry rebuild');
  assert.match(message.textContent, /Try again/);
});

async function sourcePeopleFixture() {
  const data = await fixture();
  const doc = data.documents.get(source.path);
  doc.entries[0].facts[0].of = 'Unregistered Child';
  data.people.forEach((person) => { person.relationships = []; });
  const ref = { ...source, fingerprint: await evidenceFingerprint(doc.entries[0].facts[0]) };
  const nodes = [
    { key: 'a', registry: 'a', name: 'Same', status: 'anchored', titles: [], dates: ['1393'],
      mentions: [{ source: ref, field: 'person', date: '1393' }], identitySources: [] },
    { key: '@evidence/child', name: 'Unregistered Child', status: 'source', titles: [], dates: ['1393'],
      mentions: [{ source: ref, field: 'of', date: '1393' }], identitySources: [] },
  ];
  const relationships = [{ type: 'parent', person: 'a', of: '@evidence/child',
    derivations: [{ identity: 'source', usesGuesses: false, sources: [ref] }] }];
  const metadata = data.people[0].familyGraph;
  Object.assign(metadata, { schema: 2, engine: '2', policy: '2', evidence: {
    facts: { nodes, relationships }, 'with-guesses': structuredClone({ nodes, relationships }),
  } });
  metadata.coverage.facts.reconstructedPeople = 2;
  metadata.coverage.facts.reconstructedRelationships = 1;
  await updateFixtureBuild(data);
  return data;
}

test('schema 2 displays source people and relationships outside the registry', async () => {
  const data = await sourcePeopleFixture();
  const verification = await verifyFamilyGraph(data.people, data.documents, data.repository);
  assert.equal(verification.valid, true, verification.reason);
  const graph = buildRelationshipGraph(data.people, { verification });
  assert.equal(graph.records.length, 4);
  assert.equal(data.people.length, 3);
  assert.equal(graph.records.filter((person) => person.id).length, 3);
  assert.equal(graph.records.find((person) => person._treeKey === '@evidence/child')._evidence, true);
  assert.equal(graph.edges.length, 1);
  assert.equal(graph.edges[0].sourceIdentity, true);
  assert.match(renderPeopleTree(data.people, data.documents, { graph }), /person=%40evidence%2Fchild/);
});

test('source identities have working pages with their original assertion and source link', async () => {
  const data = await sourcePeopleFixture();
  const graph = buildRelationshipGraph(data.people, { verification: { valid: true } });
  const state = { person: '@evidence/child', familyGraph: graph };
  const { renderPersonPage } = createEntityScreens({
    state, getPeople: () => data.people,
    getDocuments: () => data.documents, escapeHtml, inlineMarkup: escapeHtml, formatDate: String,
    buildPersonPattern, dateSortValue: () => 0, displayedLanguagesFor: () => [],
    markdownLinks: escapeHtml, documentTitle: () => 'Document',
    documentNavigationUrl: (path, index) => `?document=${path}&entry=${index}`,
  });
  const html = renderPersonPage();
  assert.match(html, /Unregistered Child/);
  assert.match(html, /No permanent person ID/);
  assert.match(html, /is parent of/);
  assert.match(html, /Source attestations/);
  assert.match(html, /event.json/);
  state.person = 'Unregistered Child';
  const nameHtml = renderPersonPage();
  assert.match(nameHtml, /is parent of/);
  assert.doesNotMatch(nameHtml, /Source attestations|No permanent person ID/);
});

test('family selection keeps connected source people and offers the complete graph', async () => {
  const data = await sourcePeopleFixture();
  const graph = buildRelationshipGraph(data.people, { verification: { valid: true } });
  assert.equal(graph.components.length, 3);
  const family = focusFamilyGraph(graph, graph.defaultFocus);
  assert.equal(family.records.length, 2);
  assert.equal(family.edges.length, 1);
  assert.equal(focusFamilyGraph(graph, 'all').records.length, 4);
  const html = renderPeopleTree(data.people, data.documents, { graph, focus: graph.defaultFocus });
  assert.match(html, /data-family-focus/);
  assert.match(html, /All family groups/);
  assert.equal((html.match(/class="people-tree-person-link"/g) || []).length, 2);
});

test('source graph verification rejects endpoint reassignment and stale occurrence pointers', async () => {
  for (const change of ['reverse', 'pointer', 'anchor']) {
    const data = await sourcePeopleFixture();
    const graph = data.people[0].familyGraph.evidence.facts;
    if (change === 'reverse') [graph.relationships[0].person, graph.relationships[0].of] = [graph.relationships[0].of, graph.relationships[0].person];
    if (change === 'pointer') graph.nodes[1].mentions[0].source = { ...source, pointer: '/entries/0/facts/1' };
    if (change === 'anchor') graph.nodes[1].mentions[0].field = 'person';
    assert.equal((await verifyFamilyGraph(data.people, data.documents, data.repository)).valid, false, change);
  }
});

test('compact source indexes expand to provenance and invalid indexes are rejected', async () => {
  const data = await sourcePeopleFixture();
  const graph = data.people[0].familyGraph.evidence.facts;
  const ref = graph.nodes[0].mentions[0].source;
  graph.sources = [ref];
  graph.nodes.forEach((node) => { node.mentions[0].source = 0; });
  graph.relationships[0].derivations[0].sources = [0];
  assert.deepEqual(expandEvidenceGraph(graph).relationships[0].derivations[0].sources, [ref]);
  assert.equal((await verifyFamilyGraph(data.people, data.documents, data.repository)).valid, true);
  graph.relationships[0].derivations[0].sources = [-1];
  assert.throws(() => expandEvidenceGraph(graph), /source index/);
});

test('source-person navigation follows verified occurrences across changed evidence groups', async () => {
  const data = await sourcePeopleFixture();
  const previous = buildRelationshipGraph(data.people, { verification: { valid: true } });
  const changed = data.people[0].familyGraph.evidence['with-guesses'];
  changed.nodes[1].key = '@evidence/changed';
  changed.relationships[0].of = '@evidence/changed';
  const state = { person: '@evidence/child', familyGraph: buildRelationshipGraph(data.people, { view: 'with-guesses', verification: { valid: true } }) };
  assert.equal(remapSourcePerson(state, previous), true);
  assert.equal(state.person, '@evidence/changed');
  state.sourcePersonChoices = { reference: state.person, matches: [] };
  assert.equal(remapSourcePerson(state, previous), false);
  assert.equal(state.sourcePersonChoices, null);
});

async function externalTreeFixture() {
  const data = await sourcePeopleFixture();
  data.tree = { ...data.people[0].familyGraph, schema: 3, engine: '3' };
  data.people = registryIdentities(data.people);
  data.files.set('data/people.json', data.people);
  data.files.set('data/tree.json', data.tree);
  data.repository.getFamilyTree = async () => data.tree;
  return data;
}

test('tree.json holds computed views while people remains an ID/name registry', async () => {
  const data = await externalTreeFixture();
  const before = JSON.stringify(data.people);
  const verification = await verifyFamilyGraph(data.people, data.documents, data.repository, [...data.documents.keys()], data.tree);
  assert.equal(verification.valid, true, verification.reason);
  const graph = buildRelationshipGraph(data.people, { tree: data.tree, verification });
  assert.equal(graph.records.length, 4);
  assert.equal(graph.edges.length, 1);
  assert.equal(JSON.stringify(data.people), before);
  assert.ok(data.people.every((person) => Object.keys(person).sort().join(',') === 'id,name'));
  assert.ok(!Object.hasOwn(data.tree.inputs, 'data/tree.json'));
});

test('active loader reads and rebuilds the separate tree without changing registry entries', async () => {
  const data = await externalTreeFixture();
  const before = JSON.stringify(data.people);
  data.documents.get(source.path).date = '1400';
  let rebuilds = 0;
  const { loader, state } = loaderFor(data, { rebuild: async (options) => {
    rebuilds++;
    assert.equal(options.includeGuesses, true);
    await updateFixtureBuild(data);
  } });
  await loader.loadAll();
  await loader.waitForFamilyRebuild();
  assert.equal(rebuilds, 1);
  assert.equal(state.tree, data.tree);
  assert.equal(state.familyGraph.valid, true, state.familyGraph.reason);
  assert.equal(JSON.stringify(state.personRecords), before);
});

test('missing tree.json triggers generation even when the registry has no relationship fields', async () => {
  const data = await externalTreeFixture();
  const generated = data.tree;
  data.tree = null;
  let rebuilds = 0;
  const { loader, state } = loaderFor(data, { rebuild: async () => { rebuilds++; data.tree = generated; } });
  await loader.loadAll();
  await loader.waitForFamilyRebuild();
  assert.equal(rebuilds, 1);
  assert.equal(state.familyGraph.valid, true, state.familyGraph.reason);
  assert.equal(state.familyGraph.edges.length, 1);
});

test('invalid saved build options cannot prevent automatic regeneration', async () => {
  for (const invalid of [{ views: {} }, { views: 'facts' }, { views: [] },
    { configuration: { searchLimit: -1 } }, { configuration: { searchLimit: 'bad' } }]) {
    const data = await externalTreeFixture();
    const generated = structuredClone(data.tree);
    Object.assign(data.tree, invalid);
    let rebuilds = 0;
    const { loader, state } = loaderFor(data, { rebuild: async (options) => {
      rebuilds++;
      assert.deepEqual(options, { includeGuesses: true, searchLimit: 10000 });
      data.tree = generated;
    } });
    await loader.loadAll();
    await loader.waitForFamilyRebuild();
    assert.equal(rebuilds, 1);
    assert.equal(state.familyGraph.valid, true, state.familyGraph.reason);
  }
});

test('reconstructed kin terms must be supported by their source assertion', async () => {
  const data = await externalTreeFixture();
  const fact = data.documents.get(source.path).entries[0].facts[0];
  fact.type = 'kin';
  fact.term = 'Vetter';
  const ref = { ...source, fingerprint: await evidenceFingerprint(fact) };
  for (const graph of Object.values(data.tree.evidence)) {
    graph.nodes.forEach((node) => node.mentions.forEach((mention) => { mention.source = ref; }));
    const edge = graph.relationships[0];
    edge.type = 'kin';
    edge.term = 'Schwager';
    edge.derivations.forEach((d) => { d.sources = [ref]; });
  }
  await updateFixtureBuild(data);
  const verification = await verifyFamilyGraph(data.people, data.documents, data.repository, [...data.documents.keys()], data.tree);
  assert.equal(verification.valid, false);
});

test('repository handles a missing generated tree without treating it as source data', async () => {
  const repository = createRepository({ location: { hostname: 'localhost', pathname: '/docs/' },
    fetchFunction: async (path) => { assert.match(path, /data\/tree.json/); return { ok: false, status: 404 }; } });
  assert.equal(await repository.getFamilyTree(), null);
});

async function probabilityFixture() {
  const data = await externalTreeFixture();
  const parameters = JSON.parse(await readFile(new URL('../data/matching.json', import.meta.url), 'utf8'));
  Object.assign(data.tree, { schema: 4, engine: '5', policy: '4', matchingBackground: { facts: { total: 0, counts: {} }, 'with-guesses': { total: 0, counts: {} } }, configuration: { searchLimit: 10000, probability: structuredClone(parameters) } });
  data.files.set('data/matching.json', parameters);
  data.tree.inputs['data/matching.json'] = await evidenceFingerprint(parameters);
  data.tree.fingerprint = await evidenceFingerprint(data.tree.inputs);
  for (const graph of Object.values(data.tree.evidence)) {
    graph.nodes.forEach((node) => { node.identityProbability = 1; });
    graph.relationships.forEach((edge) => edge.derivations.forEach((d) => { d.assertionWeight = 1; d.endpointProbability = null; }));
    graph.comparisons = [{ person: 'a', candidate: '@evidence/child', probability: .5, logOdds: 0,
      features: [{ name: 'test evidence', contribution: -Math.log(parameters.priorProbability / (1 - parameters.priorProbability)) }],
      status: 'below-threshold', reason: 'Below merge probability', usesGuesses: false,
      sources: [graph.relationships[0].derivations[0].sources[0]] }];
  }
  return data;
}

test('probability tree omits configuration while person evidence retains explained comparisons', async () => {
  const data = await probabilityFixture();
  const verification = await verifyFamilyGraph(data.people, data.documents, data.repository, [...data.documents.keys()], data.tree);
  assert.equal(verification.valid, true, verification.reason);
  const graph = buildRelationshipGraph(data.people, { tree: data.tree, verification });
  assert.equal(graph.view, 'with-guesses');
  const html = renderPeopleTree(data.people, data.documents, { graph });
  assert.doesNotMatch(html, /Facts \+ weighted guesses/);
  assert.doesNotMatch(html, /data-family-view/);
  assert.doesNotMatch(html, /Matching parameters|matching-parameters|sourceWeights.books|guessWeight/);
  assert.doesNotMatch(html, /Identity match estimates/);
  const evidence = relationshipPanel(graph);
  assert.match(evidence, /Identity match estimates/);
  assert.match(evidence, /50.0%/);
});

test('probability verification rejects altered estimates and effective parameters', async () => {
  for (const mutation of ['estimate', 'parameters']) {
    const data = await probabilityFixture();
    if (mutation === 'estimate') data.tree.evidence.facts.comparisons[0].probability = .99;
    else data.tree.configuration.probability.mergeProbability = .8;
    const verification = await verifyFamilyGraph(data.people, data.documents, data.repository, [...data.documents.keys()], data.tree);
    assert.equal(verification.valid, false);
    assert.match(verification.reason, /probability|Probability/);
  }
});

test('parameter changes automatically rebuild and a saved facts-only preference cannot omit guesses', async () => {
  const data = await probabilityFixture();
  const next = { ...data.files.get('data/matching.json'), mergeProbability: .8 };
  data.files.set('data/matching.json', next);
  let rebuilds = 0;
  const { loader, state } = loaderFor(data, { rebuild: async (options) => {
    rebuilds++;
    assert.equal(options.includeGuesses, true);
    data.tree.configuration.probability = structuredClone(next);
    data.tree.inputs['data/matching.json'] = await evidenceFingerprint(next);
    data.tree.fingerprint = await evidenceFingerprint(data.tree.inputs);
  } });
  state.familyView = 'facts';
  await loader.loadAll();
  await loader.waitForFamilyRebuild();
  assert.equal(rebuilds, 1);
  assert.equal(state.familyGraph.valid, true, state.familyGraph.reason);
  assert.equal(state.familyGraph.view, 'with-guesses');
});

test('text context participants preserve exact references and cannot override an ID', async () => {
  const data = await probabilityFixture();
  const doc = data.documents.get(source.path);
  const child = data.tree.evidence.facts.nodes.find((node) => !node.registry);
  const text = `[a] and ${child.name} held property at North.`;
  doc.entries[0].facts.push(text);
  const ref = { path: source.path, pointer: '/entries/0/facts/1', fingerprint: await evidenceFingerprint(text) };
  for (const graph of Object.values(data.tree.evidence)) {
    graph.nodes.find((node) => node.registry === 'a').mentions.push({ source: ref, field: 'text', reference: 'a', date: '1393' });
    graph.nodes.find((node) => !node.registry).mentions.push({ source: ref, field: 'text', reference: child.name, date: '1393' });
  }
  await updateFixtureBuild(data);
  let verification = await verifyFamilyGraph(data.people, data.documents, data.repository, [...data.documents.keys()], data.tree);
  assert.equal(verification.valid, true, verification.reason);
  data.tree.evidence.facts.nodes.find((node) => !node.registry).mentions.at(-1).reference = 'a';
  verification = await verifyFamilyGraph(data.people, data.documents, data.repository, [...data.documents.keys()], data.tree);
  assert.equal(verification.valid, false);
  assert.match(verification.reason, /fixed anchor/);
});

test('name-frequency background must agree with its total', async () => {
  const data = await probabilityFixture();
  data.tree.matchingBackground.facts = { total: 10, counts: { 'someone von somewhere': 3 } };
  const verification = await verifyFamilyGraph(data.people, data.documents, data.repository, [...data.documents.keys()], data.tree);
  assert.equal(verification.valid, false);
  assert.match(verification.reason, /name-frequency/);
});

test('context attestations render original text on source-person pages', async () => {
  const data = await probabilityFixture();
  const doc = data.documents.get(source.path);
  const child = data.tree.evidence.facts.nodes.find((node) => !node.registry);
  const text = `${child.name} held property at North.`;
  doc.entries[0].facts.push(text);
  const ref = { path: source.path, pointer: '/entries/0/facts/1', fingerprint: await evidenceFingerprint(text) };
  for (const graph of Object.values(data.tree.evidence)) graph.nodes.find((node) => !node.registry).mentions.push({ source: ref, field: 'text', reference: child.name, date: '1393' });
  const graph = buildRelationshipGraph(data.people, { tree: data.tree, verification: { valid: true } });
  const state = { person: child.key, familyGraph: graph };
  const { renderPersonPage } = createEntityScreens({ state, getPeople: () => data.people, getDocuments: () => data.documents,
    escapeHtml, inlineMarkup: escapeHtml, formatDate: String, documentNavigationUrl: (path, index) => `?document=${path}&entry=${index}` });
  assert.match(renderPersonPage(), /held property at North/);
});
