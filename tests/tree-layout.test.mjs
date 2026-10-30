import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

// The viewer uses browser ES modules without a Node package manifest.
import { moduleUrl } from './browser-module.mjs';
const { renderPeopleTree } = await import(await moduleUrl(new URL('../docs/app/screens/tree.js', import.meta.url)));
const { buildRelationshipGraph } = await import(await moduleUrl(new URL('../docs/app/data/relationships.js', import.meta.url)));
const person = (id, children = [], extra = {}) => ({ id, name: id, children, ...extra });
const attr = (markup, name) => markup.match(new RegExp(` ${name}="([^"]*)"`))?.[1];

function geometry(people) {
  const html = renderPeopleTree(people, [], { graph: buildRelationshipGraph(people, { verification: { valid: true } }) });
  const cards = [...html.matchAll(/<a class="people-tree-person-link"[^>]*>(.*?)<\/a>/g)].map(([markup]) => {
    const rect = markup.match(/<rect [^>]*>/)[0];
    return { id: decodeURIComponent(attr(markup, 'href').slice('?person='.length)),
      x: +attr(rect, 'x'), y: +attr(rect, 'y'), w: +attr(rect, 'width'), h: +attr(rect, 'height') };
  });
  const paths = [...html.matchAll(/<path class="people-tree-parent"[^>]*>/g)].map(([markup]) => {
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
    return segments;
  });
  const spouses = [...html.matchAll(/<line class="people-tree-spouse"[^>]*>/g)].map(([markup]) =>
    Object.fromEntries(['x1', 'y1', 'x2', 'y2'].map((key) => [key, +attr(markup, key)])));
  return { html, cards, paths, spouses };
}

function intersects(a, b) {
  return Math.max(Math.min(a.x1, a.x2), Math.min(b.x1, b.x2)) <= Math.min(Math.max(a.x1, a.x2), Math.max(b.x1, b.x2))
    && Math.max(Math.min(a.y1, a.y2), Math.min(b.y1, b.y2)) <= Math.min(Math.max(a.y1, a.y2), Math.max(b.y1, b.y2));
}

function assertPlanar(layout) {
  const { html, cards, paths, spouses } = layout;
  const [, , width, height] = attr(html, 'viewBox').split(' ').map(Number);
  for (const card of cards) {
    assert.ok(card.x >= 0 && card.y >= 0 && card.x + card.w <= width && card.y + card.h <= height, 'card stays in SVG bounds');
    for (const other of cards) {
      if (other === card) continue;
      assert.ok(card.x + card.w <= other.x || other.x + other.w <= card.x
        || card.y + card.h <= other.y || other.y + other.h <= card.y, 'cards do not overlap');
    }
    for (const line of [...paths.flat(), ...spouses]) {
      assert.ok(!intersects(line, { x1: card.x + .01, y1: card.y + .01, x2: card.x + card.w - .01, y2: card.y + card.h - .01 }),
        `connector avoids ${card.id}'s card`);
    }
  }
  // Segments of a single family intentionally meet at their shared bus.
  const connectors = [...paths, ...spouses.map((line) => [line])];
  connectors.forEach((segments, index) => {
    connectors.slice(index + 1).forEach((other) => segments.forEach((a) => other.forEach((b) => {
      assert.ok(!intersects(a, b), 'unrelated connectors do not intersect or overlap');
    })));
  });
}

test('wide branches stay separate and parents center over their children', () => {
  const people = [person('root', ['a', 'b']), person('a', ['a1', 'a2', 'a3', 'a4']),
    person('b', ['b1']), ...['a1', 'a2', 'a3', 'a4', 'b1'].map((id) => person(id))];
  const layout = geometry(people);
  assertPlanar(layout);
  for (const parent of people.filter((p) => p.children.length)) {
    const card = layout.cards.find((c) => c.id === parent.id);
    const children = parent.children.map((id) => layout.cards.find((c) => c.id === id));
    const left = Math.min(...children.map((c) => c.x));
    const right = Math.max(...children.map((c) => c.x + c.w));
    assert.equal(card.x + card.w / 2, (left + right) / 2);
    assert.ok(children.every((child) => child.y > card.y + card.h));
    assert.equal(new Set(children.map((child) => child.y)).size, 1);
  }
  assert.equal(layout.paths.length, 3, 'one bus per sibling set');
});

test('spouses with the same children share a single bus', () => {
  const layout = geometry([person('father', ['child'], { wife: 'mother' }),
    person('mother', ['child']), person('child')]);
  assertPlanar(layout);
  assert.equal(layout.cards.length, 3);
  assert.equal(layout.paths.length, 1);
  assert.equal(layout.spouses.length, 1);
});

test('shared descendants repeat visibly under each parent branch', () => {
  const layout = geometry([person('a', ['child']), person('b', ['child']),
    person('child', ['grandchild']), person('grandchild')]);
  assertPlanar(layout);
  assert.equal(layout.cards.filter((card) => card.id === 'child').length, 2);
  assert.equal(layout.cards.filter((card) => card.id === 'grandchild').length, 2);
  assert.equal((layout.html.match(/shown in multiple branches/g) || []).length, 4);
});

test('different spouse child lists retain their separate parentage', () => {
  const layout = geometry([person('a', ['child-a'], { wife: 'b' }),
    person('b', ['child-b']), person('child-a'), person('child-b')]);
  assertPlanar(layout);
  assert.equal(layout.paths.length, 2);
  for (const [parentId, childId] of [['a', 'child-a'], ['b', 'child-b']]) {
    const parent = layout.cards.find((card) => card.id === parentId);
    const child = layout.cards.find((card) => card.id === childId);
    assert.equal(parent.x, child.x);
  }
});

test('cycles terminate, unknown references are ignored, and names are escaped', () => {
  const layout = geometry([person('a', ['b', 'missing']), person('b', ['a']), person('<C&>')]);
  assertPlanar(layout);
  assert.equal(layout.cards.length, 4);
  assert.ok(layout.html.includes('&lt;C&amp;&gt;'));
  assert.ok(!layout.html.includes('NaN'));
  assert.match(renderPeopleTree([]), /No people found/);
});

test('repository family tree has no crossings, overlaps, or clipped cards', async () => {
  const people = JSON.parse(await readFile(new URL('../data/people.json', import.meta.url), 'utf8'));
  const layout = geometry(people);
  assertPlanar(layout);
  const graph = buildRelationshipGraph(people, { verification: { valid: true } });
  assert.equal(new Set(layout.cards.map((card) => card.id)).size, graph.records.length);
  assert.ok(layout.cards.length < graph.records.length * 3, 'repeated family occurrences remain bounded');
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
  assertPlanar(layout);
  assert.equal(layout.cards.filter((card) => card.id === 'child').length, 2);
  assert.equal(layout.cards.filter((card) => card.id === 'grandchild').length, 2);
  assert.equal(layout.cards.filter((card) => card.id === 'other').length, 1);
  assert.equal(layout.paths.length, 4);
  assert.match(layout.html, /is spouse of/);
});
