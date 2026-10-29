import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { webcrypto } from 'node:crypto';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

globalThis.crypto ||= webcrypto;
const { buildRelationshipGraph, resolvePerson, verifyFamilyGraph, evidenceFingerprint, canonicalEvidence, registryIdentities } =
  await import(await moduleUrl(new URL('../docs/app/data/relationships.js', import.meta.url)));
const { renderPeopleTree } = await import(await moduleUrl(new URL('../docs/app/screens/tree.js', import.meta.url)));
const { createDataLoader } = await import(await moduleUrl(new URL('../docs/app/data/loader.js', import.meta.url)));
const { parsePeople, parsePlaces } = await import(await moduleUrl(new URL('../docs/app/data/entities.js', import.meta.url)));
const { createRepository } = await import(await moduleUrl(new URL('../docs/app/data/repository.js', import.meta.url)));
const { loadPreferences } = await import(await moduleUrl(new URL('../docs/app/state/preferences.js', import.meta.url)));
const { renderActiveScreen } = await import(await moduleUrl(new URL('../docs/app/screens/router-view.js', import.meta.url)));
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
  assert.match(renderPeopleTree(data.people, data.documents, { graph }), /Reconstructed relationships/);
  assert.match(renderPeopleTree(data.people, data.documents, { graph }), /event.json#\/entries\/0\/facts\/0/);
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
  const html = renderPeopleTree(people, [], { graph });
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
  const loader = createDataLoader({ repository, state, parsePeople, parsePlaces,
    buildPersonPattern: () => [], buildPlacePattern: () => null,
    bookSortYear: () => 0, recordHasMissingSourceOrUrl: () => false,
    missingRecordLabel: 'missing', greyRecordLabels: [], savePreferences() {}, renderTabs() {},
    renderActive: async () => { renders++; } });
  await loader.loadAll();
  assert.equal(renders, 1);
  assert.equal(state.familyGraph.valid, true, state.familyGraph.reason);
  assert.equal(state.familyView, 'with-guesses');
  assert.equal(state.documents.size, 1);
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
  const metadata = data.people[0].familyGraph;
  metadata.inputs[source.path] = await evidenceFingerprint(data.documents.get(source.path));
  metadata.fingerprint = await evidenceFingerprint(metadata.inputs);
}

test('stale local evidence automatically rebuilds once and reloads the verified graph', async () => {
  const data = await fixture();
  data.documents.get(source.path).date = '1400';
  let rebuilds = 0;
  const { loader, state, counts } = loaderFor(data, { rebuild: async () => { rebuilds++; await updateFixtureBuild(data); } });
  await Promise.all([loader.loadAll(), loader.loadAll()]);
  assert.equal(rebuilds, 1);
  assert.equal(state.familyGraph.valid, true, state.familyGraph.reason);
  assert.equal(state.familyGraph.edges.length, 1);
  assert.equal(state.familyView, 'with-guesses');
  assert.equal(state.familyGraph.canRebuild, true);
  assert.deepEqual(counts(), { renders: 1, progress: 1 });
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
  assert.equal(rebuilds, 1);
  assert.equal(state.familyGraph.valid, false);
  assert.equal(state.familyGraph.edges.length, 0);
  const html = renderPeopleTree(state.personRecords, state.documents, { graph: state.familyGraph });
  assert.match(html, /data-family-rebuild/);
  assert.match(html, /Invalid source date/);
  await loader.rebuildFamilyGraph();
  assert.equal(rebuilds, 2);
  assert.equal(state.familyGraph.valid, true);
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
