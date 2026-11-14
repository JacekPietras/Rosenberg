import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { buildSourcePersonPattern, coordinatedByNameMatches, coordinatedByNameRouteNames, personMentionClass, personRouteName } = await import(await moduleUrl(new URL('../docs/app/data/person-name-recognition.js', import.meta.url)));
const names = '# Men\nArnold, Arnolt\nAnna\nKonrad, Conradus\nEberhard\nEbirhart\nGeorg\nHans\nHeinrich\nHartmut\nJohann\nMargaretha\nMichael\nPeter\nWilhelm\nWiprecht\n# Women\nElisabeth, Elsbeth';
const particles = 'von\nv.\nvon.\nde\nan\nvan\nzu';
const places = [{ name: 'Rosenberg', variations: ['Rosenberg'] }, { name: 'Uissigheim', variations: ['Uissigheim', 'Ussinkeim'] }, { name: 'Lauda', variations: ['Lauda'] }, { name: 'Amberg', variations: ['Amberg'] }, { name: 'Durn', variations: ['Durn', 'Dürn'] }, { name: 'Thüngen', variations: ['Thüngen'] }, { name: 'Michelsberg', variations: ['Michelsberg'] }, { name: 'Landstein', variations: ['Landstein'] }, { name: 'Helmstadt', variations: ['Helmstadt'] }, { name: 'Pappenheim', variations: ['Pappenheim'] }, { name: 'Marschalk', variations: ['Marschalk'] }];
const titles = '# Younger\nder Jüngere, the Younger\nder Junge\n# Older\nder Ältere, the Elder, the Older\nder Alte\n# Offices and ranks\nAmtmann, Amtman, Ambtman, Ambtmann, Amptman, Amptmann, Ambetman\nRitter, Ritters, miles, Knight\nVogt, advocatus\nVizedom, Vitzthum, Vizthum, Vitztum, Vizdom\nder Rote, Rufus';
const connectors = await readFile(new URL('../data/name-connectors.md', import.meta.url), 'utf8');
const projectNames = await readFile(new URL('../data/names.md', import.meta.url), 'utf8');
const byNames = await readFile(new URL('../data/by-names.md', import.meta.url), 'utf8');
const pattern = buildSourcePersonPattern(names, particles, places, titles, connectors, byNames);

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

test('recognizes listed by-names alone and as part of Rosenberg family names', () => {
  for (const form of ['Hans Schenk', 'Hans Schenk von Rosenberg', 'Hans Schenk zu Rosenberg']) {
    pattern.lastIndex = 0;
    assert.equal(pattern.exec(form)?.[0], form);
  }
  assert.equal(personRouteName('Hans Schenk von Rosenberg', titles, connectors, particles, names, byNames),
    personRouteName('Hans Schenk zu Rosenberg', titles, connectors, particles, names, byNames));
  assert.equal(personRouteName('Hans von Rosenberg', titles, connectors, particles, names, byNames),
    'Hans von Rosenberg');
  assert.equal(personRouteName('Hans zu Rosenberg', titles, connectors, particles, names, byNames),
    'Hans zu Rosenberg');
  assert.notEqual(personRouteName('Hans von Rosenberg', titles, connectors, particles, names, byNames),
    personRouteName('Hans zu Rosenberg', titles, connectors, particles, names, byNames));
});

test('recognizes and routes married-name forms by their listed birth surname', () => {
  for (const form of [
    'Elsbeth Rosenberg, née Marschalk zu Pappenheim',
    'Elisabeth von Rosenberg, née Marschalk zu Pappenheim'
  ]) {
    pattern.lastIndex = 0;
    assert.equal(pattern.exec(form)?.[0], form);
    assert.equal(personRouteName(form, titles, connectors, particles, names, byNames),
      'Elisabeth Marschalk zu Pappenheim');
  }
});

test('recognizes Elsbeth Rosenberg with her Marschalk birth surname as one mention', () => {
  const phrase = 'Issuer 2: Elsbeth Rosenberg, née Marschalk zu Pappenheim';
  const noMarschalkPlace = buildSourcePersonPattern(names, particles,
    places.filter((place) => place.name !== 'Marschalk'), titles, connectors, byNames);
  noMarschalkPlace.lastIndex = 0;
  assert.deepEqual([...phrase.matchAll(noMarschalkPlace)].map((match) => match[0]), [
    'Elsbeth Rosenberg, née Marschalk zu Pappenheim'
  ]);
  assert.equal(personRouteName('Elsbeth Rosenberg, née Marschalk zu Pappenheim', titles, connectors, particles, names),
    'Elisabeth Marschalk zu Pappenheim');
});

test('recognizes Elisabeth von Rosenberg with her Marschalk birth surname as one mention', () => {
  const phrase = 'Sealer 2: Elisabeth von Rosenberg, née Marschalk zu Pappenheim';
  const noMarschalkPlace = buildSourcePersonPattern(names, particles,
    places.filter((place) => place.name !== 'Marschalk'), titles, connectors, byNames);
  noMarschalkPlace.lastIndex = 0;
  assert.deepEqual([...phrase.matchAll(noMarschalkPlace)].map((match) => match[0]), [
    'Elisabeth von Rosenberg, née Marschalk zu Pappenheim'
  ]);
  assert.equal(personRouteName('Elisabeth von Rosenberg, née Marschalk zu Pappenheim', titles, connectors, particles, names),
    'Elisabeth Marschalk zu Pappenheim');
});

test('recognizes brothers with their shared Marschalk zu Pappenheim title', () => {
  for (const [sentence, expectedBrothers] of [
    ['The brothers Heinrich, Georg, and Konrad Marschalk zu Pappenheim', [
      'Heinrich Marschalk zu Pappenheim',
      'Georg Marschalk zu Pappenheim',
      'Konrad Marschalk zu Pappenheim'
    ]],
    ['The brothers Georg and Konrad Marschalk zu Pappenheim', [
      'Georg Marschalk zu Pappenheim',
      'Konrad Marschalk zu Pappenheim'
    ]]
  ]) {
    assert.match(sentence, /Marschalk zu Pappenheim/u);
    for (const expected of expectedBrothers) {
      pattern.lastIndex = 0;
      assert.equal(pattern.exec(expected)?.[0], expected);
    }
  }
});

test('recognizes Anna Marschalk and Konrad von Rosenberg separately', () => {
  const widowSentence = 'In 1394, Anna Marschalk, widow of Konrad von Rosenberg, endowed';
  pattern.lastIndex = 0;
  assert.deepEqual([...widowSentence.matchAll(pattern)].map((match) => match[0]), [
    'Anna Marschalk', 'Konrad von Rosenberg'
  ]);
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

test('recognizes a woman by her birth surname in a grant description', () => {
  pattern.lastIndex = 0;
  const sentence = 'grants Margaretha, née von Rosenberg, wife of Michael von Seinsheim, lifetime';
  assert.equal(pattern.exec(sentence)?.[0], 'Margaretha, née von Rosenberg');
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

test('recognizes a called designation after a person name without absorbing it into the route name', () => {
  pattern.lastIndex = 0;
  const sentence = 'Anne von Mauer her son Peter von Helmstadt, called von Rosenberg';
  assert.equal(pattern.exec(sentence)?.[0], 'Peter von Helmstadt, called von Rosenberg');
  assert.equal(personRouteName('Peter von Helmstadt, called von Rosenberg', titles, connectors, particles),
    'Peter von Helmstadt');
  assert.equal(personMentionClass('Peter von Helmstadt, called von Rosenberg', connectors, particles), 'person-mention');
  assert.equal(personMentionClass('Peter von Rosenberg', connectors, particles), 'person-mention-blue');
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
  assert.equal(personRouteName('Hans Schenk zu Rosenberg', titles, connectors, particles, names, byNames),
    'Hans Schenk von Rosenberg');
});

test('routes spelling variants to the canonical given name and by-name', () => {
  assert.equal(personRouteName('Hainrich Marschalken zu Pappenheim', titles, connectors, particles,
    projectNames, byNames), 'Heinrich Marschalk zu Pappenheim');
});

test('recognizes coordinated brothers under their shared by-name and inherited place', () => {
  const source = 'Hainrich Marschalk zu Pappenheim, also acting for his brothers Goerg and Chuonrat Marschalken, acknowledges that he sold the Pappenheim convent';
  pattern.lastIndex = 0;
  const directRoutes = [...source.matchAll(buildSourcePersonPattern(projectNames, particles, places, titles, connectors, byNames))]
    .map((match) => personRouteName(match[0], titles, connectors, particles, projectNames, byNames));
  const coordinated = coordinatedByNameMatches(source, titles, connectors, particles, projectNames, byNames, places);
  assert.deepEqual([...directRoutes.slice(0, 1), ...coordinated.flatMap((match) => match.routes)], [
    'Heinrich Marschalk zu Pappenheim',
    'Georg Marschalk zu Pappenheim',
    'Konrad Marschalk zu Pappenheim'
  ]);
  assert.equal(directRoutes.length, 2);
  assert.equal(directRoutes[1], 'Konrad Marschalk');
});

test('recognizes a three-person Oxford-comma list with a shared Marschalk surname', () => {
  const source = 'Chuoncz Rosenkrancz declares that he has reached an amicable settlement with Sigmund, Haubt, and Hainrich Marschalken zu Pappenheim and all the Marschalk zu Pappenheim concerning';
  assert.deepEqual(coordinatedByNameRouteNames(source, titles, connectors, particles, projectNames, byNames, places), [
    'Siegmund Marschalk zu Pappenheim',
    'Haubt Marschalk zu Pappenheim',
    'Heinrich Marschalk zu Pappenheim'
  ]);
});

test('recognizes a four-person list with a shared von Rosenberg surname', () => {
  const source = 'Feud of Peter von Stedenberg and Hans Schelme with Arnold, Eberhard, Ulrich, and Georg von Rosenberg';
  assert.deepEqual(coordinatedByNameRouteNames(source, titles, connectors, particles, projectNames, byNames, places), [
    'Arnold von Rosenberg',
    'Eberhard von Rosenberg',
    'Ulrich von Rosenberg',
    'Georg von Rosenberg'
  ]);
});
