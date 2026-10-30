import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { keepEntryInView } = await import(await moduleUrl(new URL('../docs/app/components/entry-scroll.js', import.meta.url)));

function fixture() {
  class Events {
    listeners = new Map();
    addEventListener(type, callback) {
      if (!this.listeners.has(type)) this.listeners.set(type, new Set());
      this.listeners.get(type).add(callback);
    }
    removeEventListener(type, callback) { this.listeners.get(type)?.delete(callback); }
    emit(type, event = {}) { this.listeners.get(type)?.forEach((callback) => callback(event)); }
  }
  const win = new Events();
  const content = new Events();
  const frames = new Map();
  let nextFrame = 0;
  let position = 1600;
  let scrollY = 0;
  let resized;
  let disconnected = false;
  const scrolls = [];
  win.requestAnimationFrame = (callback) => { frames.set(++nextFrame, callback); return nextFrame; };
  win.cancelAnimationFrame = (id) => frames.delete(id);
  win.scrollBy = (options) => { scrolls.push(options); scrollY += options.top; };
  win.ResizeObserver = class {
    constructor(callback) { resized = callback; }
    observe(element) { assert.equal(element, content); }
    disconnect() { disconnected = true; }
  };
  const target = {
    ownerDocument: { defaultView: win },
    isConnected: true,
    scrollIntoView(options) {
      assert.deepEqual(options, { block: 'start', behavior: 'instant' });
      scrollY = position;
    },
    getBoundingClientRect: () => ({ top: position - scrollY }),
  };
  const cleanup = keepEntryInView(target, content);
  return {
    win, content, target, cleanup, scrolls, frames,
    resize: () => resized(),
    shift: (amount) => { position += amount; },
    nativeAnchor: (amount) => { scrollY += amount; },
    top: () => target.getBoundingClientRect().top,
    disconnected: () => disconnected,
    flush() {
      const callbacks = [...frames.values()];
      frames.clear();
      callbacks.forEach((callback) => callback());
    },
  };
}

test('keeps the linked entry aligned through multiple delayed image loads', () => {
  const view = fixture();
  assert.equal(view.top(), 0);
  view.shift(420);
  view.content.emit('load');
  view.resize();
  assert.equal(view.frames.size, 1);
  view.flush();
  assert.equal(view.top(), 0);
  view.shift(230);
  view.resize();
  view.flush();
  assert.equal(view.top(), 0);
  assert.deepEqual(view.scrolls.map((scroll) => scroll.top), [420, 230]);
  assert.ok(view.scrolls.every((scroll) => scroll.behavior === 'instant'));
  view.cleanup();
});

test('does not double-correct browser scroll anchoring or changes below the entry', () => {
  const view = fixture();
  view.shift(420);
  view.nativeAnchor(420);
  view.resize();
  view.flush();
  view.content.emit('load');
  view.flush();
  assert.equal(view.scrolls.length, 0);
  view.cleanup();
});

for (const [type, event] of [
  ['wheel'], ['touchstart'], ['pointerdown'], ['keydown', { key: 'PageDown' }],
  ['keydown', { key: 'Tab' }], ['hashchange'], ['popstate'],
]) {
  test(`releases the entry on ${type}${event?.key ? ` ${event.key}` : ''}`, () => {
    const view = fixture();
    view.shift(420);
    view.resize();
    view.win.emit(type, event);
    assert.equal(view.frames.size, 0);
    assert.equal(view.disconnected(), true);
    view.content.emit('load');
    view.resize();
    view.flush();
    assert.equal(view.scrolls.length, 0);
  });
}

test('screen cleanup cancels pending corrections and removes listeners', () => {
  const view = fixture();
  view.resize();
  view.cleanup();
  view.cleanup();
  view.flush();
  assert.equal(view.frames.size, 0);
  assert.ok([...view.win.listeners.values(), ...view.content.listeners.values()].every((listeners) => !listeners.size));
  assert.equal(view.disconnected(), true);
});

test('a detached target releases the observer without scrolling', () => {
  const view = fixture();
  view.target.isConnected = false;
  view.resize();
  view.flush();
  assert.equal(view.disconnected(), true);
  assert.equal(view.scrolls.length, 0);
});
