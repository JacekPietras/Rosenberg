import assert from 'node:assert/strict';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { buildSourcePersonPattern, personRouteName } = await import(await moduleUrl(new URL('../docs/app/data/person-name-recognition.js', import.meta.url)));
const names = '# Men\nArnold, Arnolt\nKonrad, Conradus\nEberhard\nEbirhart\nHartmut\nJohann';
const particles = 'von\nv.\nvon.\nde\nan\nvan';
const places = [{ name: 'Rosenberg', variations: ['Rosenberg'] }, { name: 'Uissigheim', variations: ['Uissigheim', 'Ussinkeim'] }, { name: 'Lauda', variations: ['Lauda'] }, { name: 'Amberg', variations: ['Amberg'] }, { name: 'Durn', variations: ['Durn'] }];
const titles = '# Younger\nder Jüngere, the Younger\nder Junge\n# Older\nder Ältere, the Elder, the Older\nder Alte\n# Offices and ranks\nRitter, miles, Knight\nVogt, advocatus\nVizedom, Vitzthum\nder Rote, Rufus';
const pattern = buildSourcePersonPattern(names, particles, places, titles);

test('recognizes the documented canonical and reordered name forms', () => {
  for (const form of [
    'Konrad von Rosenberg', 'Konrad von Rosenberg der Ältere', 'Arnold von Uissigheim, Ritter',
    'Ritter Arnold von Uissigheim', 'Arnold Ritter von Uissigheim', 'Konrad der Ältere von Rosenberg',
    'Conradus v. Rosenberg', 'Arnold v. Ussinkeim', 'Arnold von Uissigheim II.',
    'Arnold (II) von Uissigheim', 'Arnold [II] von Uissigheim', 'Eberhard von Rosenberg, Vogt zu Lauda',
    'Johann Vitzthum zu Amberg de Rosenberg', 'Hartmut of Rosenberg the Younger',
    'Arnold von Rosenberg; miles', 'Arnold von Rosenberg der Rote'
  ]) {
    pattern.lastIndex = 0;
    assert.equal(pattern.test(form), true, form);
  }
});

test('recognizes translated Knight as a non-canonical title in surrounding prose', () => {
  pattern.lastIndex = 0;
  const sentence = 'Famous Knight Eberhard von Rosenberg renders an account of his expenses in the service of Baldwin';
  assert.equal(pattern.exec(sentence)?.[0], 'Knight Eberhard von Rosenberg');
  assert.equal(personRouteName('Knight Eberhard von Rosenberg', titles), 'Eberhard von Rosenberg');
});

test('recognizes a parenthetical given-name variant and translated office title', () => {
  pattern.lastIndex = 0;
  const phrase = 'knight Ebirhart (or Eber-) von Rosenberg, vogt of Durn';
  assert.equal(pattern.exec(phrase)?.[0], phrase);
  assert.equal(personRouteName(phrase, titles), 'Ebirhart von Rosenberg');
});

test('does not treat an unknown given name or a partial place as a person', () => {
  pattern.lastIndex = 0;
  assert.equal(pattern.test('Unknown von Rosenberg'), false);
  pattern.lastIndex = 0;
  assert.equal(pattern.test('Arnold von Rosenbergstein'), false);
});

test('routes title variants to the title-free person name', () => {
  assert.equal(personRouteName('Ritter Arnold von Uissigheim', titles), 'Arnold von Uissigheim');
  assert.equal(personRouteName('Arnold Ritter von Uissigheim', titles), 'Arnold von Uissigheim');
  assert.equal(personRouteName('Konrad von Rosenberg der Ältere', titles), 'Konrad von Rosenberg');
  assert.equal(personRouteName('Hartmut of Rosenberg the Younger', titles), 'Hartmut of Rosenberg');
});
