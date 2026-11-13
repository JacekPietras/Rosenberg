import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { buildSourcePersonPattern, personRouteName } = await import(await moduleUrl(new URL('../docs/app/data/person-name-recognition.js', import.meta.url)));
const names = '# Men\nArnold, Arnolt\nKonrad, Conradus\nEberhard\nEbirhart\nHartmut\nHans\nJohann\nWilhelm\nWiprecht';
const particles = 'von\nv.\nvon.\nde\nan\nvan';
const places = [{ name: 'Rosenberg', variations: ['Rosenberg'] }, { name: 'Uissigheim', variations: ['Uissigheim', 'Ussinkeim'] }, { name: 'Lauda', variations: ['Lauda'] }, { name: 'Amberg', variations: ['Amberg'] }, { name: 'Durn', variations: ['Durn', 'Dürn'] }, { name: 'Thüngen', variations: ['Thüngen'] }, { name: 'Michelsberg', variations: ['Michelsberg'] }, { name: 'Landstein', variations: ['Landstein'] }, { name: 'Helmstadt', variations: ['Helmstadt'] }];
const titles = '# Younger\nder Jüngere, the Younger\nder Junge\n# Older\nder Ältere, the Elder, the Older\nder Alte\n# Offices and ranks\nAmtmann, Amtman, Ambtman, Ambtmann, Amptman, Amptmann, Ambetman\nRitter, Ritters, miles, Knight\nVogt, advocatus\nVizedom, Vitzthum, Vizthum, Vitztum, Vizdom\nder Rote, Rufus';
const connectors = await readFile(new URL('../data/name-connectors.md', import.meta.url), 'utf8');
const pattern = buildSourcePersonPattern(names, particles, places, titles, connectors);

test('recognizes the documented canonical and reordered name forms', () => {
  for (const form of [
    'Konrad von Rosenberg', 'Konrad von Rosenberg der Ältere', 'Arnold von Uissigheim, Ritter',
    'Ritter Arnold von Uissigheim', 'Arnold Ritter von Uissigheim', 'Konrad der Ältere von Rosenberg',
    'Conradus v. Rosenberg', 'Arnold v. Ussinkeim', 'Arnold von Uissigheim II.',
    'Arnold (II) von Uissigheim', 'Arnold [II] von Uissigheim', 'Eberhard von Rosenberg, Vogt zu Lauda',
    'Johann Vitzthum zu Amberg de Rosenberg', 'Hartmut of Rosenberg the Younger',
    'Arnold von Rosenberg; miles', 'Arnold von Rosenberg der Rote',
    'Eberhard von Rosenberg, Amtmann', 'Eberhard von Rosenberg, Amptman'
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

test('recognizes an optional given-name ending and translated Vogt title', () => {
  pattern.lastIndex = 0;
  const phrase = 'Eber(hard) von Rosenberg, Vogt of Dürn';
  assert.equal(pattern.exec(phrase)?.[0], phrase);
  assert.equal(personRouteName(phrase, titles), 'Eber(hard) von Rosenberg');
});

test('recognizes an office title in context after the person name', () => {
  pattern.lastIndex = 0;
  const sentence = 'which were paid to him by Konrad von Rosenberg, Vizdom zu Amberg, for the damages he suffered on behalf of Duke Ruprecht';
  assert.equal(pattern.exec(sentence)?.[0], 'Konrad von Rosenberg, Vizdom zu Amberg');
  assert.equal(personRouteName('Konrad von Rosenberg, Vizdom zu Amberg', titles), 'Konrad von Rosenberg');
});

test('recognizes a title variant before a parenthetical date note', () => {
  pattern.lastIndex = 0;
  const sentence = "a court letter of Konrad von Rosenberg, Vizthum zu Amberg (dated the Monday before St. Catherine's day 1379)";
  assert.equal(pattern.exec(sentence)?.[0], 'Konrad von Rosenberg, Vizthum zu Amberg');
  assert.equal(personRouteName('Konrad von Rosenberg, Vizthum zu Amberg', titles), 'Konrad von Rosenberg');
});

test('keeps an unlisted one-word place attached to a recognized title', () => {
  const withoutAmberg = buildSourcePersonPattern(names, particles,
    places.filter((place) => !place.variations.includes('Amberg')), titles, connectors);
  const sentence = 'charter according to which Konrad von Rosenberg, Vitztum zu Amberg, on the Monday';
  assert.equal([...sentence.matchAll(withoutAmberg)].map((match) => match[0])[0],
    'Konrad von Rosenberg, Vitztum zu Amberg');
});

test('keeps an Amtmann title attached across a parenthetical name note', () => {
  pattern.lastIndex = 0;
  const sentence = 'if they are prevented by "captivity necessity," knights Eberhard von Rosenberg (-sem-), Amtmann of Dürn, and Burchard Sturmfeder';
  assert.equal(pattern.exec(sentence)?.[0], 'Eberhard von Rosenberg (-sem-), Amtmann of Dürn');
  assert.equal(personRouteName('Eberhard von Rosenberg (-sem-), Amtmann of Dürn', titles, connectors), 'Eberhard von Rosenberg');
});

test('recognizes a name introduced by a data-listed German naming connector', () => {
  pattern.lastIndex = 0;
  const phrase = 'Ritters Eberhard genannt von Rosenberg';
  assert.equal(pattern.exec(phrase)?.[0], phrase);
});

test('recognizes the name in the English translation with named before it', () => {
  pattern.lastIndex = 0;
  const sentence = 'the sons of a (already deceased) knight named Eberhard von Rosenberg, appear';
  assert.equal(pattern.exec(sentence)?.[0], 'Eberhard von Rosenberg');
});

test('recognizes data-listed English name connectors before the given name', () => {
  for (const phrase of [
    'Knight called Eberhard von Rosenberg',
    'Knight known as Eberhard von Rosenberg'
  ]) {
    pattern.lastIndex = 0;
    assert.equal(pattern.exec(phrase)?.[0], phrase);
    assert.equal(personRouteName(phrase, titles, connectors), 'Eberhard von Rosenberg');
  }
});

test('does not attach the previous list item title to the next person across a semicolon', () => {
  pattern.lastIndex = 0;
  const sentence = 'the five are: Eberhard von Sauwensheim, Ritter; Wilhelm von Thüngen, Ritter; Eberhard Vogt von Salzburg; Karl vom Stein; and Arnold von Rosenberg the Elder.';
  assert.deepEqual([...sentence.matchAll(pattern)].map((match) => match[0]), [
    'Wilhelm von Thüngen, Ritter',
    'Arnold von Rosenberg the Elder'
  ]);
});

test('recognizes separate people around a parenthetical passage', () => {
  pattern.lastIndex = 0;
  const sentence = 'Campaign against the lords of Rosenberg and Hans von Michelsberg (who had become entangled in a feud with Wilhelm von Landstein and the Austrian lords of Walsee and Buchheim) and their subjugation';
  assert.deepEqual([...sentence.matchAll(pattern)].map((match) => match[0]), [
    'Hans von Michelsberg',
    'Wilhelm von Landstein'
  ]);
});

test('does not attach a preceding comma-separated office title to the next name', () => {
  pattern.lastIndex = 0;
  const sentence = 'namely Graf Emicho von Leiningen, the black Reinhard von Sickingen, Konrad von Rosenberg, (all?) Hofmeister, Schwicker von Sickingen, Vogt zu Bretten, Wiprecht von Helmstadt der Jüngere, Siegfried von Vennigen, all Ritter,';
  assert.deepEqual([...sentence.matchAll(pattern)].map((match) => match[0]), [
    'Konrad von Rosenberg',
    'Wiprecht von Helmstadt der Jüngere'
  ]);
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
