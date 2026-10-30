import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

// The viewer uses browser ES modules without a Node package manifest.
import { moduleUrl } from './browser-module.mjs';
const { renderPeopleTree } = await import(await moduleUrl(new URL('../docs/app/screens/tree.js', import.meta.url)));
const { buildRelationshipGraph } = await import(await moduleUrl(new URL('../docs/app/data/relationships.js', import.meta.url)));
const person = (id, children = [], extra = {}) => ({ id, name: id, children, ...extra });
const attr = (markup, name) => markup.match(new RegExp(` ${name}="([^"]*)"`))?.[1];

function geometry(people, tree, view = 'facts', showKins = true) {
  const html = renderPeopleTree(people, [], { graph: buildRelationshipGraph(people, { tree, view, verification: { valid: true } }), showKins });
  const cards = [...html.matchAll(/<a class="people-tree-person-link"[^>]*>(.*?)<\/a>/g)].map(([markup]) => {
    const rect = markup.match(/<rect [^>]*>/)[0];
    return { id: decodeURIComponent(attr(markup, 'href').slice('?person='.length)),
      x: +attr(rect, 'x'), y: +attr(rect, 'y'), w: +attr(rect, 'width'), h: +attr(rect, 'height') };
  });
  const connections = [...html.matchAll(/<path class="people-tree-(parent|spouse|sibling|kin)"[^>]*>/g)].map(([markup, type]) => {
    const segments = [];
    let x, y;
    for (const [, command, value] of attr(markup, 'd').matchAll(/([MVH])([\d.]+(?: [\d.]+)?)/g)) {
      const numbers = value.split(' ').map(Number);
      if (command === 'M') [x, y] = numbers;
      else {
        const nextX = command === 'H' ? numbers[0] : x;
        const nextY = command === 'V' ? numbers[0] : y;
        segments.push({ x1: x, y1: y, x2: nextX, y2: nextY });
        [x, y] = [nextX, nextY];
      }
    }
    return { type, person: attr(markup, 'data-person'), of: attr(markup, 'data-of'), segments };
  });
  return { html, cards, connections, paths: connections.filter((edge) => edge.type === 'parent').map((edge) => edge.segments),
    spouses: connections.filter((edge) => edge.type === 'spouse').map((edge) => edge.segments) };
}

function intersects(a, b) {
  return Math.max(Math.min(a.x1, a.x2), Math.min(b.x1, b.x2)) <= Math.min(Math.max(a.x1, a.x2), Math.max(b.x1, b.x2))
    && Math.max(Math.min(a.y1, a.y2), Math.min(b.y1, b.y2)) <= Math.min(Math.max(a.y1, a.y2), Math.max(b.y1, b.y2));
}

function assertLayout(layout) {
  const { html, cards, paths, spouses } = layout;
  const [, , width, height] = attr(html, 'viewBox').split(' ').map(Number);
  assert.equal(new Set(cards.map((card) => card.id)).size, cards.length, 'each identity has exactly one card');
  for (const card of cards) {
    assert.ok(card.x >= 0 && card.y >= 0 && card.x + card.w <= width && card.y + card.h <= height, 'card stays in SVG bounds');
    for (const other of cards) {
      if (other === card) continue;
      assert.ok(card.x + card.w <= other.x || other.x + other.w <= card.x
        || card.y + card.h <= other.y || other.y + other.h <= card.y, 'cards do not overlap');
    }
    for (const line of layout.connections.flatMap((connection) => connection.segments)) {
      assert.ok(!intersects(line, { x1: card.x + .01, y1: card.y + .01, x2: card.x + card.w - .01, y2: card.y + card.h - .01 }),
        `connector avoids ${card.id}'s card`);
    }
  }
  for (const connection of layout.connections) {
    const first = connection.segments[0], last = connection.segments.at(-1);
    for (const [point, key] of [[{ x: first.x1, y: first.y1 }, connection.person], [{ x: last.x2, y: last.y2 }, connection.of]]) {
      const card = cards.find((item) => item.id === key);
      // Spouse paths may run left-to-right regardless of canonical endpoint order.
      const endpoints = connection.type !== 'parent' ? cards.filter((item) => [connection.person, connection.of].includes(item.id)) : [card];
      assert.ok(endpoints.some((item) => point.x >= item.x && point.x <= item.x + item.w && point.y >= item.y && point.y <= item.y + item.h),
        'connector attaches to its recorded participant');
    }
  }
}

test('generations preserve parentage with one card per identity', () => {
  const people = [person('root', ['a', 'b']), person('a', ['a1', 'a2', 'a3', 'a4']),
    person('b', ['b1']), ...['a1', 'a2', 'a3', 'a4', 'b1'].map((id) => person(id))];
  const layout = geometry(people);
  assertLayout(layout);
  for (const parent of people.filter((p) => p.children.length)) {
    const card = layout.cards.find((c) => c.id === parent.id);
    const children = parent.children.map((id) => layout.cards.find((c) => c.id === id));
    assert.ok(children.every((child) => child.y > card.y + card.h));
    assert.equal(new Set(children.map((child) => child.y)).size, 1);
  }
  assert.equal(layout.paths.length, 7, 'one connector per recorded parent-child relationship');
});

test('spouses with the same child share one child card', () => {
  const layout = geometry([person('father', ['child'], { wife: 'mother' }),
    person('mother', ['child']), person('child')]);
  assertLayout(layout);
  assert.equal(layout.cards.length, 3);
  assert.equal(layout.paths.length, 2);
  assert.equal(layout.spouses.length, 1);
});

test('shared descendants and their descendants are never copied', () => {
  const layout = geometry([person('a', ['child']), person('b', ['child']),
    person('child', ['grandchild']), person('grandchild')]);
  assertLayout(layout);
  assert.equal(layout.cards.filter((card) => card.id === 'child').length, 1);
  assert.equal(layout.cards.filter((card) => card.id === 'grandchild').length, 1);
  assert.doesNotMatch(layout.html, /shown in multiple branches/);
  assert.equal(layout.paths.length, 3);
});

test('different spouse child lists retain their separate parentage', () => {
  const layout = geometry([person('a', ['child-a'], { wife: 'b' }),
    person('b', ['child-b']), person('child-a'), person('child-b')]);
  assertLayout(layout);
  assert.equal(layout.paths.length, 2);
  for (const [parentId, childId] of [['a', 'child-a'], ['b', 'child-b']]) {
    const parent = layout.cards.find((card) => card.id === parentId);
    const child = layout.cards.find((card) => card.id === childId);
    assert.ok(child.y > parent.y);
    assert.ok(layout.connections.some((edge) => edge.type === 'parent' && edge.person === parentId && edge.of === childId));
  }
});

test('cycles terminate, unknown references are ignored, and names are escaped', () => {
  const layout = geometry([person('a', ['b', 'missing']), person('b', ['a']), person('<C&>')]);
  assertLayout(layout);
  assert.equal(layout.cards.length, 3);
  assert.ok(layout.html.includes('&lt;C&amp;&gt;'));
  assert.ok(!layout.html.includes('NaN'));
  assert.match(renderPeopleTree([]), /No people found/);
});

test('repository family tree shows each identity once with no overlaps or clipped cards', async () => {
  const people = JSON.parse(await readFile(new URL('../data/people.json', import.meta.url), 'utf8'));
  const tree = JSON.parse(await readFile(new URL('../data/tree.json', import.meta.url), 'utf8'));
  for (const view of tree.views) {
    const layout = geometry(people, tree, view);
    assertLayout(layout);
    const simplified = geometry(people, tree, view, false);
    assertLayout(simplified);
    assert.equal(simplified.cards.length, layout.cards.length);
    const graph = buildRelationshipGraph(people, { tree, view, verification: { valid: true } });
    assert.equal(new Set(layout.cards.map((card) => card.id)).size, graph.records.length);
    assert.equal(layout.cards.length, graph.records.length);
    const elisabeth = graph.records.find((record) => record.name === 'Elisabeth von Erligheim');
    assert.equal(layout.cards.filter((card) => card.id === elisabeth._treeKey).length, 1);
    assert.equal(layout.connections.length, graph.edges.length);
    const signature = (edge) => JSON.stringify([edge.type, edge.person, edge.of]);
    assert.deepEqual(layout.connections.map(signature).sort(), graph.edges.map(signature).sort());
  }
});

function recordedFamily(names, relationships) {
  const derivations = [{ view: 'facts', identity: 'anchored', usesGuesses: false,
    sources: [{ path: 'data/documents/family.json', pointer: '/facts/0' }] }];
  return Object.entries(names).map(([id, name], index) => ({ id, name,
    ...(index === 0 ? { familyGraph: { views: ['facts'] } } : {}),
    relationships: relationships.filter(([person]) => person === id).map(([, type, of]) => ({ type, of, derivations })),
  }));
}

test('simple view keeps shared children on their married fathers branch', () => {
  const people = recordedFamily({ mother: 'Elisabeth von Erligheim', father: 'Eberhard von Rosenberg',
    a: 'Arnold', b: 'Konrad', other: 'Other child' }, [
    ['mother', 'spouse', 'father'], ['mother', 'parent', 'a'], ['father', 'parent', 'a'],
    ['mother', 'parent', 'b'], ['father', 'parent', 'b'], ['mother', 'parent', 'other'],
  ]);
  const layout = geometry(people, undefined, 'facts', false);
  assertLayout(layout);
  assert.equal(layout.cards.length, 5);
  const parents = layout.connections.filter((edge) => edge.type === 'parent');
  assert.deepEqual(parents.map((edge) => [edge.person, edge.of]).sort(), [['father', 'a'], ['father', 'b'], ['mother', 'other']]);
  const busY = (edge) => edge.segments.find((segment) => segment.y1 === segment.y2).y1;
  assert.equal(busY(parents.find((edge) => edge.of === 'a')), busY(parents.find((edge) => edge.of === 'b')));
  const a = layout.cards.find((card) => card.id === 'a'), b = layout.cards.find((card) => card.id === 'b');
  assert.equal(a.y, b.y);
  assert.equal(Math.abs(a.x - b.x), a.w + 52, 'shared children stay adjacent');
  assert.equal(geometry(people).paths.length, 5, 'show kins restores both parent stems');
  assert.match(layout.html, /Elisabeth von Erligheim/);
  assert.doesNotMatch(layout.html, /entity-relationships|identity-comparisons/, 'tree has no evidence panels below it');
});

test('simple view preserves both parent stems without a marriage or identifiable father', () => {
  for (const [names, marriage] of [
    [{ left: 'Elisabeth von Erligheim', right: 'Eberhard von Rosenberg', child: 'Child' }, false],
    [{ left: 'Unidentified parent A', right: 'Unidentified parent B', child: 'Child' }, true],
  ]) {
    const people = recordedFamily(names, [['left', 'parent', 'child'], ['right', 'parent', 'child'],
      ...(marriage ? [['left', 'spouse', 'right']] : [])]);
    const layout = geometry(people, undefined, 'facts', false);
    assertLayout(layout);
    assert.equal(layout.paths.length, 2);
  }
});

test('children of different marriages keep distinct buses in the simple view', () => {
  const people = recordedFamily({ father: 'Eberhard von Rosenberg', first: 'Elisabeth von Erligheim',
    second: 'Anna von Dienheim', a: 'Arnold', b: 'Konrad' }, [
    ['first', 'spouse', 'father'], ['second', 'spouse', 'father'],
    ['father', 'parent', 'a'], ['first', 'parent', 'a'],
    ['father', 'parent', 'b'], ['second', 'parent', 'b'],
  ]);
  const layout = geometry(people, undefined, 'facts', false);
  assertLayout(layout);
  assert.equal(layout.paths.length, 2);
  const busY = layout.paths.map((path) => path.find((segment) => segment.y1 === segment.y2).y1);
  assert.equal(new Set(busY).size, 2, 'hidden mother stems do not collapse different recorded parent sets');
});

test('long parent edges and nonadjacent marriages route around all cards', () => {
  const layout = geometry([person('a', ['b', 'grandchild'], { wife: 'c' }),
    person('b', ['grandchild']), person('c', [], { wife: 'd' }), person('d'), person('grandchild')]);
  assertLayout(layout);
  assert.equal(layout.cards.length, 5);
  assert.equal(layout.paths.length, 3);
  assert.equal(layout.spouses.length, 2);
});

test('marriages that conflict with generation alignment keep unique people and original parentage', () => {
  const layout = geometry([person('a', ['c'], { wife: 'd' }), person('b', ['d'], { wife: 'c' }), person('c'), person('d')]);
  assertLayout(layout);
  assert.equal(layout.cards.length, 4);
  assert.equal(layout.paths.length, 2);
  assert.equal(layout.spouses.length, 2);
  for (const [parent, child] of [['a', 'c'], ['b', 'd']]) {
    assert.ok(layout.cards.find((card) => card.id === child).y > layout.cards.find((card) => card.id === parent).y);
  }
});

test('namesakes with different identities retain separate cards', () => {
  const layout = geometry([person('first', [], { name: 'Same name', wife: 'spouse' }),
    person('second', [], { name: 'Same name' }), person('spouse')]);
  assertLayout(layout);
  assert.equal(layout.cards.length, 3);
  assert.deepEqual(layout.cards.map((card) => card.id).sort(), ['first', 'second', 'spouse']);
});

test('generated multiple marriages preserve explicit parents and repeated ancestry', () => {
  const derivations = [{ view: 'facts', identity: 'anchored', usesGuesses: false,
    sources: [{ path: 'data/documents/example.json', pointer: '/entries/0/facts/0' }] }];
  const edge = (type, of) => ({ type, of, derivations });
  const people = [
    { id: 'a', name: 'Parent A', familyGraph: { views: ['facts'] }, relationships: [edge('parent', 'child'), edge('spouse', 'b'), edge('spouse', 'other')] },
    { id: 'b', name: 'Parent B', relationships: [edge('parent', 'child')] },
    { id: 'other', name: 'Other spouse', relationships: [] },
    { id: 'child', name: 'Child', relationships: [edge('parent', 'grandchild')] },
    { id: 'grandchild', name: 'Grandchild', relationships: [] },
  ];
  const layout = geometry(people);
  assertLayout(layout);
  assert.equal(layout.cards.filter((card) => card.id === 'child').length, 1);
  assert.equal(layout.cards.filter((card) => card.id === 'grandchild').length, 1);
  assert.equal(layout.cards.filter((card) => card.id === 'other').length, 1);
  assert.equal(layout.paths.length, 3);
  assert.equal(layout.spouses.length, 2);
  assert.ok(!layout.connections.some((edge) => edge.type === 'parent' && edge.person === 'other'));
  assert.doesNotMatch(layout.html, /entity-relationships|identity-comparisons/);
});

test('sibling and kin assertions connect their single cards without inferred parents', () => {
  const derivations = [{ view: 'facts', identity: 'anchored', usesGuesses: false,
    sources: [{ path: 'data/documents/example.json', pointer: '/facts/0' }] }];
  const people = [
    { id: 'a', name: 'Alex', familyGraph: { views: ['facts'] }, relationships: [
      { type: 'sibling', of: 'b', derivations }, { type: 'kin', of: 'c', term: 'Vetter', derivations }] },
    { id: 'b', name: 'Bea', relationships: [] }, { id: 'c', name: 'Chris', relationships: [] },
  ];
  const layout = geometry(people);
  const graph = buildRelationshipGraph(people, { verification: { valid: true } });
  const defaultHtml = renderPeopleTree(people, [], { graph });
  assert.match(defaultHtml, /data-show-kins> show kins/);
  assert.doesNotMatch(defaultHtml, /<path class="people-tree-(sibling|kin)"/);
  assert.equal((defaultHtml.match(/class="people-tree-person-link"/g) || []).length, 3);
  assert.match(layout.html, /data-show-kins checked/);
  assertLayout(layout);
  assert.equal(layout.cards.length, 3);
  assert.equal(layout.paths.length, 0);
  assert.deepEqual(layout.connections.map((edge) => edge.type).sort(), ['kin', 'sibling']);
  assert.match(layout.html, /people-tree-sibling/);
  assert.match(layout.html, /people-tree-kin/);
  assert.match(layout.html, />Vetter</);
});


test('hover facts use source identity pointers and keep namesakes separate', () => {
  const path = 'data/documents/example.json';
  const documents = new Map([[path, { date: '1400', entries: [{ facts: [
    { type: 'title', person: 'Same name', personTitle: ['Ritter'] },
    { type: 'title', person: 'Same name', personTitle: ['Vogt'] },
  ], guesses: [{ text: 'A guess that must stay out of facts.' }] }] }]]);
  const graph = { records: [0, 1].map((index) => ({ name: 'Same name', _treeKey: `source-${index}`,
    reconstruction: { dates: ['1400'], mentions: [
      { source: { path, pointer: `/entries/0/facts/${index}` }, date: '1400' },
      { source: { path, pointer: `/entries/0/facts/${index}` }, date: '1400' },
      { source: { path, pointer: '/entries/0/guesses/0' }, date: '1400' },
    ] } })), edges: [], reverse: new Map() };
  const html = renderPeopleTree([], documents, { graph });
  const templates = [...html.matchAll(/<template[^>]*>(.*?)<\/template>/g)].map((match) => match[1]);
  assert.equal(templates.length, 2);
  assert.match(templates[0], /Ritter/);
  assert.doesNotMatch(templates[0], /Vogt/);
  assert.match(templates[1], /Vogt/);
  assert.doesNotMatch(templates[1], /Ritter/);
  assert.equal((templates[0].match(/<li>/g) || []).length, 1, 'duplicate participant references show one fact');
  assert.match(templates[0], /<time>1400<\/time>/);
  assert.match(templates[0], /href="\?tab=documents&amp;record=/);
  assert.doesNotMatch(html, /A guess|entity-relationships|identity-comparisons/);
  assert.ok(html.endsWith('</section>'), 'nothing follows the tree wrapper');
});

test('registry hover facts use exact IDs and historical dates', () => {
  const people = [person('a', [], { name: 'Same name' }), person('b', [], { name: 'Same name' })];
  const html = renderPeopleTree(people, new Map([
    ['data/books/example.json', { date: '2020', entries: [{ facts: [
      { type: 'title', person: 'a', personTitle: ['Ritter'], date: '1350' },
      { type: 'title', person: 'b', personTitle: ['Vogt'], date: '1360' },
      { text: 'Same name held land.' },
      { text: '[a] used <script>unsafe</script> text.' },
    ] }] }],
  ]));
  const templates = [...html.matchAll(/<template[^>]*>(.*?)<\/template>/g)].map((match) => match[1]);
  assert.match(templates[0], /Ritter/);
  assert.match(templates[0], /<time>1350<\/time>/);
  assert.match(templates[0], /Undated/);
  assert.match(templates[0], /&lt;script&gt;/);
  assert.doesNotMatch(templates[0], /Vogt|2020|held land|<script>/);
  assert.match(templates[1], /Vogt/);
  assert.doesNotMatch(templates[1], /Ritter|unsafe/);
});
