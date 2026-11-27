import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { moduleUrl } from './browser-module.mjs';

const { buildSourcePersonPattern, coordinatedByNameMatches, coordinatedByNameRouteNames, findPersonNameMentions, personMentionClass, personRouteName, splitPersonNameTitles } = await import(await moduleUrl(new URL('../docs/app/data/person-name-recognition.js', import.meta.url)));
const names = '# Men\nArnold, Arnolt\nAnna\nKonrad, Conradus\nEberhard\nEbirhart\nGeorg\nHans\nHeinrich\nHartmut\nJohann\nMargaretha\nMichael\nPeter\nWilhelm\nWiprecht\n# Women\nElisabeth, Elsbeth\nJuliane';
const particles = 'von\nv.\nvon.\nde\nan\nvan\nzu';
const places = [{ name: 'Rosenberg', variations: ['Rosenberg'] }, { name: 'Uissigheim', variations: ['Uissigheim', 'Ussinkeim'] }, { name: 'Lauda', variations: ['Lauda'] }, { name: 'Amberg', variations: ['Amberg'] }, { name: 'Durn', variations: ['Durn', 'Dürn'] }, { name: 'Thüngen', variations: ['Thüngen'] }, { name: 'Michelsberg', variations: ['Michelsberg'] }, { name: 'Landstein', variations: ['Landstein'] }, { name: 'Helmstadt', variations: ['Helmstadt'] }, { name: 'Pappenheim', variations: ['Pappenheim'] }, { name: 'Bartenstein', variations: ['Bartenstein'] }, { name: 'Marschalk', variations: ['Marschalk'] }];
const titles = '# Younger\nder Jüngere, the Younger\nder Junge\n# Older\nder Ältere, the Elder, the Older\nder Alte\n# Offices and ranks\nAmtmann, Amtman, Ambtman, Ambtmann, Amptman, Amptmann, Ambetman\nRitter, Ritters, miles, Knight\nVogt, advocatus\nVizedom, Vitzthum, Vizthum, Vitztum, Vizdom\nder Rote, Rufus';
const connectors = await readFile(new URL('../data/name-connectors.md', import.meta.url), 'utf8');
const projectNames = await readFile(new URL('../data/names.md', import.meta.url), 'utf8');
const projectTitles = await readFile(new URL('../data/titles-office.md', import.meta.url), 'utf8');
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

test('recognizes a parenthesized von in a debt acknowledgment', () => {
  const scenarioPattern = buildSourcePersonPattern(projectNames, particles, places,
    `${titles}\n${projectTitles}`, connectors, byNames);
  const sentence = 'Reinhart (von) Uissigheim acknowledges owing';
  const match = sentence.match(scenarioPattern)?.[0];
  assert.equal(match, 'Reinhart (von) Uissigheim');
  assert.equal(personRouteName(match, `${titles}\n${projectTitles}`, connectors, particles,
    projectNames, byNames, places), 'Reinhard von Uissigheim');
});

test('recognizes the parties in a pledge debt description, including King Sigmund', () => {
  const scenarioNames = projectNames;
  const scenarioTitles = `${titles}\n${projectTitles}`;
  const scenarioPattern = buildSourcePersonPattern(scenarioNames, particles, places, scenarioTitles, connectors, byNames);
  const sentence = 'pledge debt of 6,100 florins owed to the cousins Siegmund von Thüngen and Balthasar von Thüngen, King Sigmund, and Ulrich von Rosenberg. The charter is not extant.';
  assert.deepEqual([...sentence.matchAll(scenarioPattern)].map((match) => match[0]), [
    'Siegmund von Thüngen',
    'Balthasar von Thüngen',
    'King Sigmund',
    'Ulrich von Rosenberg'
  ]);
  assert.equal(personRouteName('King Sigmund', scenarioTitles, connectors, particles,
    scenarioNames, byNames, places), 'König Siegmund');
  assert.equal(personRouteName('Knight Hans von Seckendorf', scenarioTitles, connectors, particles,
    scenarioNames, byNames, places), 'Hans von Seckendorf');
  assert.equal(personRouteName('Knight Hans', scenarioTitles, connectors, particles,
    scenarioNames, byNames, places), 'Hans');
  const seckendorfPlaces = [{ name: 'Seckendorf', variations: ['Seckendorf', 'Seckendorff'] }];
  const agreement = 'Agreement by knight Hans von Seckendorf-Aberdar, court master';
  const agreementPattern = buildSourcePersonPattern(scenarioNames, particles, seckendorfPlaces,
    scenarioTitles, connectors, byNames);
  const knightMatch = agreement.match(agreementPattern)?.[0];
  assert.equal(knightMatch, 'knight Hans von Seckendorf');
  assert.equal(personRouteName(knightMatch, scenarioTitles, connectors, particles,
    scenarioNames, byNames, seckendorfPlaces), 'Hans von Seckendorf');
  assert.deepEqual(coordinatedByNameRouteNames(sentence, scenarioTitles, connectors, particles,
    scenarioNames, byNames, places), []);
});

test('recognizes Konz with a bracketed ordinal and knightly title in a castle grant', () => {
  const scenarioTitles = `${titles}\n${projectTitles}`;
  const scenarioPattern = buildSourcePersonPattern(projectNames, particles, places, scenarioTitles, connectors, byNames);
  const sentence = 'grant of Boxberg Castle to Konz [V.] von Rosenberg, Ritter, by King Ruprecht';
  assert.deepEqual([...sentence.matchAll(scenarioPattern)].map((match) => match[0]), [
    'Konz [V.] von Rosenberg, Ritter',
    'King Ruprecht'
  ]);
  const result = findPersonNameMentions(sentence, scenarioTitles, connectors, particles,
    projectNames, byNames, places, scenarioPattern);
  assert.deepEqual(result.singles.map(({ route, titles: personTitles }) => ({ route, titles: personTitles })), [
    { route: 'Kunz von Rosenberg', titles: ['Ritter'] },
    { route: 'König Ruprecht', titles: ['König'] }
  ]);
});

test('requires surnames after office titles but permits route titles before given names', () => {
  const scenarioTitles = `${titles}\n${projectTitles}`;
  const scenarioNames = projectNames;
  const scenarioPattern = buildSourcePersonPattern(scenarioNames, particles, places,
    scenarioTitles, connectors, byNames);
  for (const officeOnly of ['which Vogt Wernher', 'which advocatus Wernher']) {
    assert.deepEqual([...officeOnly.matchAll(scenarioPattern)].map((match) => match[0]), [], officeOnly);
  }

  const phrase = 'which Vogt Wernher von Rosenberg (-berch)';
  assert.deepEqual([...phrase.matchAll(scenarioPattern)].map((match) => match[0]), [
    'Vogt Wernher von Rosenberg (-berch)'
  ]);
  assert.equal(personRouteName('Vogt Wernher von Rosenberg (-berch)', scenarioTitles,
    connectors, particles, scenarioNames, byNames, places), 'Wernher von Rosenberg');

  for (const routeTitle of ['King Sigmund', 'König Sigmund', 'Koenig Sigmund']) {
    assert.deepEqual([...routeTitle.matchAll(scenarioPattern)].map((match) => match[0]), [routeTitle], routeTitle);
  }
});

test('recognizes zum as zu before a place and routes it canonically', () => {
  const phrase = 'Konrad von Rosenberg zum Bartenstein';
  pattern.lastIndex = 0;
  assert.equal(pattern.exec(phrase)?.[0], phrase);
  assert.equal(personRouteName(phrase, titles, connectors, particles, projectNames, byNames),
    'Konrad von Rosenberg');
});

test('recognizes von und zu, von u. zu, and von and zu surnames as canonical von names', () => {
  for (const phrase of ['Konrad von und zu Rosenberg', 'Konrad von u. zu Rosenberg', 'Konrad von and zu Rosenberg']) {
    pattern.lastIndex = 0;
    assert.equal(pattern.exec(phrase)?.[0], phrase);
    const result = findPersonNameMentions(phrase, titles, connectors, particles,
      projectNames, byNames, places, pattern);
    assert.equal(result.singles[0]?.route, 'Konrad von Rosenberg');
    assert.deepEqual(result.singles[0]?.titles, ['zu Rosenberg']);
  }
  const phrase = 'Eberhard von und zu Rosenberg';
  const result = findPersonNameMentions(phrase, titles, connectors, particles,
    projectNames, byNames, places, pattern);
  assert.equal(result.singles[0]?.route, 'Eberhard von Rosenberg');
  assert.deepEqual(result.singles[0]?.titles, ['zu Rosenberg']);
  const englishPhrase = 'Eberhard von and zu Rosenberg';
  const englishResult = findPersonNameMentions(englishPhrase, titles, connectors, particles,
    projectNames, byNames, places, pattern);
  assert.equal(englishResult.singles[0]?.route, 'Eberhard von Rosenberg');
  assert.deepEqual(englishResult.singles[0]?.titles, ['zu Rosenberg']);
});

test('recognizes a trailing zu-place designation as a person title', () => {
  const scenarioPlaces = [...places, { name: 'Essingen', variations: ['Essingen'] }];
  const phrase = 'Hans von Rosenberg zu Essingen';
  const scenarioPattern = buildSourcePersonPattern(projectNames, particles, scenarioPlaces,
    `${titles}\n${projectTitles}`, connectors, byNames);
  const result = findPersonNameMentions(phrase, `${titles}\n${projectTitles}`, connectors,
    particles, projectNames, byNames, scenarioPlaces, scenarioPattern);
  assert.equal(result.singles[0]?.route, 'Hans von Rosenberg');
  assert.deepEqual(result.singles[0]?.titles, ['zu Essingen']);
});

test('does not treat a coordinated place as a title of Count Boppo von Wertheim', () => {
  const scenarioPlaces = [...places,
    { name: 'Wertheim', variations: ['Wertheim'] },
    { name: 'Bronnbach', variations: ['Bronnbach'] },
  ];
  const scenarioTitles = `${titles}\n${projectTitles}`;
  const phrase = 'between Count Boppo I von Wertheim and Bronnbach in 1178';
  const scenarioPattern = buildSourcePersonPattern(projectNames, particles, scenarioPlaces,
    scenarioTitles, connectors, byNames);
  const result = findPersonNameMentions(phrase, scenarioTitles, connectors, particles,
    projectNames, byNames, scenarioPlaces, scenarioPattern);
  assert.equal(result.singles.length, 1);
  assert.equal(result.singles[0]?.route, 'Boppe von Wertheim');
  assert.deepEqual(result.singles[0]?.titles, ['Graf von Wertheim']);
});

test('assigns an intervening office title to Konrad without attaching it to Eberhard', () => {
  const scenarioPlaces = [...places, { name: 'Wildenberg', variations: ['Wildenberg'] }];
  const scenarioTitles = `${titles}\n${projectTitles}`;
  const scenarioPattern = buildSourcePersonPattern(projectNames, particles, scenarioPlaces,
    scenarioTitles, connectors, byNames);
  for (const phrase of [
    'include the knights Konrad Rüdt, Burgrave zu Wildenberg, Eberhard Rüdt,',
    'knights Konrad Rüdt, Burgrave of Wildenberg, Eberhard Rüdt',
  ]) {
    const result = findPersonNameMentions(phrase, scenarioTitles, connectors, particles,
      projectNames, byNames, scenarioPlaces, scenarioPattern);
    assert.deepEqual(result.singles.map(({ route, titles: personTitles }) => ({ route, titles: personTitles })), [
      { route: 'Konrad Rüd', titles: ['Burggraf zu Wildenberg'] },
      { route: 'Eberhard Rüd', titles: [] },
    ], phrase);
  }
});

test('recognizes Mönch von Rosenberg zu Hainstadt as one person mention', () => {
  const scenarioPattern = buildSourcePersonPattern(projectNames, particles, places,
    `${titles}\n${projectTitles}`, connectors, byNames);
  const phrase = 'Ludwig Mönch von Rosenberg zu Hainstadt';
  assert.deepEqual([...phrase.matchAll(scenarioPattern)].map((match) => match[0]), [phrase]);
  assert.equal(personRouteName(phrase, `${titles}\n${projectTitles}`, connectors, particles,
    projectNames, byNames, places), 'Ludwig Mönch von Rosenberg');
});

test('keeps a complete locative place name in the person route', () => {
  const scenarioPlaces = [...places, { name: 'zum Jungen', variations: ['zum Jungen'] }];
  const phrase = 'Hen zum Jungen';
  const scenarioTitles = `${titles}\n${projectTitles}`;
  const scenarioPattern = buildSourcePersonPattern(projectNames, particles, scenarioPlaces,
    scenarioTitles, connectors, byNames);
  assert.deepEqual([...phrase.matchAll(scenarioPattern)].map((match) => match[0]), [phrase]);
  assert.equal(personRouteName(phrase, scenarioTitles, connectors, particles,
    projectNames, byNames, scenarioPlaces), phrase);
});

test('keeps zu Bartenstein as a title after the Rosenberg family name in context', () => {
  const phrase = 'transferred the said Amt Klingenberg to Konrad von Rosenberg zu Bartenstein and his cousin';
  pattern.lastIndex = 0;
  assert.equal(pattern.exec(phrase)?.[0], 'Konrad von Rosenberg zu Bartenstein');
  assert.equal(personRouteName('Konrad von Rosenberg zu Bartenstein', titles, connectors, particles,
    projectNames, byNames), 'Konrad von Rosenberg');
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
    'Elsbeth Rosenberg, née Marschalk von Pappenheim',
    'Elisabeth von Rosenberg, née Marschalk von Pappenheim'
  ]) {
    pattern.lastIndex = 0;
    assert.equal(pattern.exec(form)?.[0], form);
    assert.equal(personRouteName(form, titles, connectors, particles, names, byNames),
      'Elisabeth Marschalk von Pappenheim');
  }
});

test('recognizes Juliane née von Rosenberg with or without parentheses', () => {
  for (const [text, expectedMatch] of [
    ['wife Juliane née von Rosenberg, and their lawful', 'Juliane née von Rosenberg'],
    ['wife Juliane (née von Rosenberg), and their lawful', 'Juliane (née von Rosenberg)']
  ]) {
    pattern.lastIndex = 0;
    assert.equal(pattern.exec(text)?.[0], expectedMatch);
    assert.equal(personRouteName(expectedMatch, titles, connectors, particles, names, byNames),
      'Juliane von Rosenberg');
  }
});

test('recognizes Elsbeth Rosenberg with her Marschalk birth surname as one mention', () => {
  const phrase = 'Issuer 2: Elsbeth Rosenberg, née Marschalk von Pappenheim';
  const noMarschalkPlace = buildSourcePersonPattern(names, particles,
    places.filter((place) => place.name !== 'Marschalk'), titles, connectors, byNames);
  noMarschalkPlace.lastIndex = 0;
  assert.deepEqual([...phrase.matchAll(noMarschalkPlace)].map((match) => match[0]), [
    'Elsbeth Rosenberg, née Marschalk von Pappenheim'
  ]);
  assert.equal(personRouteName('Elsbeth Rosenberg, née Marschalk von Pappenheim', titles, connectors, particles, names),
    'Elisabeth Marschalk von Pappenheim');
});

test('recognizes Elisabeth von Rosenberg with her Marschalk birth surname as one mention', () => {
  const phrase = 'Sealer 2: Elisabeth von Rosenberg, née Marschalk von Pappenheim';
  const noMarschalkPlace = buildSourcePersonPattern(names, particles,
    places.filter((place) => place.name !== 'Marschalk'), titles, connectors, byNames);
  noMarschalkPlace.lastIndex = 0;
  assert.deepEqual([...phrase.matchAll(noMarschalkPlace)].map((match) => match[0]), [
    'Elisabeth von Rosenberg, née Marschalk von Pappenheim'
  ]);
  assert.equal(personRouteName('Elisabeth von Rosenberg, née Marschalk von Pappenheim', titles, connectors, particles, names),
    'Elisabeth Marschalk von Pappenheim');
});

test('recognizes brothers with their shared Marschalk von Pappenheim title', () => {
  for (const [sentence, expectedBrothers] of [
    ['The brothers Heinrich, Georg, and Konrad Marschalk von Pappenheim', [
      'Heinrich Marschalk von Pappenheim',
      'Georg Marschalk von Pappenheim',
      'Konrad Marschalk von Pappenheim'
    ]],
    ['The brothers Georg and Konrad Marschalk von Pappenheim', [
      'Georg Marschalk von Pappenheim',
      'Konrad Marschalk von Pappenheim'
    ]]
  ]) {
    assert.match(sentence, /Marschalk von Pappenheim/u);
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

test('recognizes the phrase “which knight Eberhard von Rosenberg, Vogt of Dürn”', () => {
  const phrase = 'which knight Eberhard von Rosenberg, Vogt of Dürn,';
  pattern.lastIndex = 0;
  const match = pattern.exec(phrase);
  assert.equal(match?.[0], 'knight Eberhard von Rosenberg, Vogt of Dürn');
  assert.equal(personRouteName(match[0], titles, connectors, particles, names, byNames, places),
    'Eberhard von Rosenberg');
  const sourcePattern = buildSourcePersonPattern(names, particles, places,
    titles, connectors, byNames);
  const { singles } = findPersonNameMentions(phrase, titles,
    connectors, particles, names, byNames, places, sourcePattern);
  assert.equal(singles.length, 1);
  assert.equal(singles[0].text, 'knight Eberhard von Rosenberg, Vogt of Dürn');
  assert.equal(singles[0].route, 'Eberhard von Rosenberg');
  assert.deepEqual(singles[0].titles, ['Ritter', 'Vogt zu Durn']);
});

test('recognizes a parenthetical given-name variant and translated office title', () => {
  pattern.lastIndex = 0;
  const phrase = 'knight Ebirhart (or Eber-) von Rosenberg, vogt of Durn';
  assert.equal(pattern.exec(phrase)?.[0], phrase);
  assert.equal(personRouteName(phrase, titles), 'Ebirhart von Rosenberg');
});

test('removes editorial delimiters from parenthetical and bracketed given-name endings', () => {
  for (const phrase of [
    'Eber(hard) von Rosenberg, Vogt of Dürn',
    'Eber[hard] von Rosenberg, Vogt of Dürn'
  ]) {
    pattern.lastIndex = 0;
    assert.equal(pattern.exec(phrase)?.[0], phrase);
    assert.equal(personRouteName(phrase, titles), 'Eberhard von Rosenberg');
  }
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

test('recognizes gen. von Rosenberg as the canonical designation of Diether von Helmstadt', () => {
  const scenarioTitles = `${titles}\n${projectTitles}`;
  const scenarioPattern = buildSourcePersonPattern(projectNames, particles, places,
    scenarioTitles, connectors, byNames);
  const sentence = 'elected Diether von Helmstadt, gen. von Rosenberg, as abbot';
  const result = findPersonNameMentions(sentence, scenarioTitles, connectors, particles,
    projectNames, byNames, places, scenarioPattern);
  assert.deepEqual(result.singles.map(({ route, titles: personTitles }) => ({ route, titles: personTitles })), [
    { route: 'Diether von Helmstadt', titles: ['genannt von Rosenberg'] },
  ]);
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
  assert.equal(personRouteName('Hainrich Marschalken von Pappenheim', titles, connectors, particles,
    projectNames, byNames), 'Heinrich Marschalk von Pappenheim');
});

test('canonicalizes a place variation in a person route', () => {
  const placeRecords = [{ name: 'Helmstadt', variations: ['Helmstadt', 'Helmstat', 'Helmstatt'] }];
  assert.equal(personRouteName('Raban von Helmstatt', titles, connectors, particles,
    projectNames, byNames, placeRecords), 'Raban von Helmstadt');
});

test('uses the first place variation as canonical when records have no name field', () => {
  const placeRecords = [{ id: 'pappenheim', variations: ['Pappenheim', 'Bappenhein', 'Bappenheim'] }];
  assert.equal(personRouteName('Haubt Marschalk von Bappenhein', titles, connectors, particles,
    projectNames, byNames, placeRecords), 'Haubt Marschalk von Pappenheim');
});

test('normalizes Bishop Wolfram of Würzburg into a person route and locative title', () => {
  const titleText = `${titles}\n${projectTitles}`;
  const placeRecords = [{ id: 'wurzburg', variations: ['Würzburg', 'Wirtzeburg', 'Wurzburg'] }];
  const sourcePattern = buildSourcePersonPattern(projectNames, particles, placeRecords,
    titleText, connectors, byNames);
  const { singles } = findPersonNameMentions('from Bishop Wolfram of Würzburg', titleText,
    connectors, particles, projectNames, byNames, placeRecords, sourcePattern);
  assert.equal(singles.length, 1);
  assert.equal(singles[0].route, 'Bischof Wolfram');
  assert.deepEqual(singles[0].titles, ['Bischof zu Würzburg']);
});

test('recognizes a bishop named before a locative designation', () => {
  const titleText = `${titles}\n${projectTitles}`;
  const placeRecords = [{ id: 'wurzburg', variations: ['Würzburg', 'Wirtzeburg', 'Wurzburg'] }];
  const sourcePattern = buildSourcePersonPattern(projectNames, particles, placeRecords,
    titleText, connectors, byNames);
  const { singles } = findPersonNameMentions(' Wolfram zu Würzburg, Bischof', titleText,
    connectors, particles, projectNames, byNames, placeRecords, sourcePattern);
  assert.equal(singles.length, 1);
  assert.equal(singles[0].route, 'Bischof Wolfram');
  assert.deepEqual(singles[0].titles, ['Bischof zu Würzburg']);
});

test('promotes Bishop Konrad of Würzburg to Bischof Konrad with locative title', () => {
  const titleText = `${titles}\n${projectTitles}`;
  const placeRecords = [{ name: 'Würzburg', variations: ['Würzburg', 'Wirtzeburg', 'Wurzburg'] }];
  const sourcePattern = buildSourcePersonPattern(projectNames, particles, placeRecords,
    titleText, connectors, byNames);
  const { singles } = findPersonNameMentions('Bishop Konrad of Würzburg', titleText,
    connectors, particles, projectNames, byNames, placeRecords, sourcePattern);
  assert.equal(singles.length, 1);
  assert.equal(singles[0].route, 'Bischof Konrad');
  assert.deepEqual(singles[0].titles, ['Bischof zu Würzburg']);
});

test('recognizes “Bishop Hans zu Würzburg” in surrounding prose', () => {
  const titleText = `${titles}\n${projectTitles}`;
  const placeRecords = [{ name: 'Würzburg', variations: ['Würzburg', 'Wirtzeburg', 'Wurzburg'] }];
  const sourcePattern = buildSourcePersonPattern(projectNames, particles, placeRecords,
    titleText, connectors, byNames);
  const { singles } = findPersonNameMentions('for Bishop Hans zu Würzburg was', titleText,
    connectors, particles, projectNames, byNames, placeRecords, sourcePattern);
  assert.equal(singles.length, 1);
  assert.equal(singles[0].route, 'Bischof Hans');
  assert.deepEqual(singles[0].titles, ['Bischof zu Würzburg']);
});

test('normalizes an office title of a place to zu when no surname is given', () => {
  const titleText = `${titles}\n${projectTitles}`;
  const sourcePattern = buildSourcePersonPattern(projectNames, particles,
    [{ name: 'Rosenberg', variations: ['Rosenberg'] }], titleText, connectors, byNames);
  const { singles } = findPersonNameMentions('Eberhard, Bishop of Rosenberg', titleText,
    connectors, particles, projectNames, byNames,
    [{ name: 'Rosenberg', variations: ['Rosenberg'] }], sourcePattern);
  assert.equal(singles.length, 1);
  assert.equal(singles[0].route, 'Bischof Eberhard');
  assert.deepEqual(singles[0].titles, ['Bischof zu Rosenberg']);
});

test('does not recognize an unlisted title or place in a title-only phrase', () => {
  const titleText = `${titles}\n${projectTitles}`;
  const sourcePattern = buildSourcePersonPattern(projectNames, particles, places,
    titleText, connectors, byNames);
  assert.deepEqual([...('Eberhard, Governor of Rosenberg'.matchAll(sourcePattern))], []);
  sourcePattern.lastIndex = 0;
  assert.deepEqual([...('Eberhard, Bishop of Atlantis'.matchAll(sourcePattern))], []);
});

test('recognizes coordinated brothers under their shared by-name and inherited place', () => {
  const source = 'Hainrich Marschalk von Pappenheim, also acting for his brothers Goerg and Chuonrat Marschalken, acknowledges that he sold the Pappenheim convent';
  pattern.lastIndex = 0;
  const directRoutes = [...source.matchAll(buildSourcePersonPattern(projectNames, particles, places, titles, connectors, byNames))]
    .map((match) => personRouteName(match[0], titles, connectors, particles, projectNames, byNames));
  const coordinated = coordinatedByNameMatches(source, titles, connectors, particles, projectNames, byNames, places);
  assert.deepEqual([...directRoutes.slice(0, 1), ...coordinated.flatMap((match) => match.routes)], [
    'Heinrich Marschalk von Pappenheim',
    'Georg Marschalk von Pappenheim',
    'Konrad Marschalk von Pappenheim'
  ]);
  assert.equal(directRoutes.length, 2);
  assert.equal(directRoutes[1], 'Konrad Marschalk');
});

test('recognizes a three-person Oxford-comma list with a shared Marschalk surname', () => {
  const source = 'Chuoncz Rosenkrancz declares that he has reached an amicable settlement with Sigmund, Haubt, and Hainrich Marschalken zu Pappenheim and all the Marschalk von Pappenheim concerning';
  assert.deepEqual(coordinatedByNameRouteNames(source, titles, connectors, particles, projectNames, byNames, places), [
    'Siegmund Marschalk',
    'Haubt Marschalk',
    'Heinrich Marschalk'
  ]);
  const [group] = coordinatedByNameMatches(source, titles, connectors, particles, projectNames, byNames, places);
  assert.deepEqual(group.members.map((member) => member.titles), [['zu Pappenheim'], ['zu Pappenheim'], ['zu Pappenheim']]);
});

test('recognizes every person in a coordinated von Rosenberg list', () => {
  const source = 'Among those named: Thomas, Anselm, Eberhard, Ulrich, and Georg von Rosenberg.';
  assert.deepEqual(coordinatedByNameRouteNames(source, titles, connectors, particles, projectNames, byNames, places), [
    'Thomas von Rosenberg',
    'Anselm von Rosenberg',
    'Eberhard von Rosenberg',
    'Ulrich von Rosenberg',
    'Georg von Rosenberg'
  ]);
});

test('recognizes coordinated brothers after the given names before their shared surname', () => {
  const source = 'confirms to the nobles Peter, Johann, and Ulrich, brothers von Rosenberg, their mutual inheritance';
  const matches = coordinatedByNameMatches(source, titles, connectors, particles,
    projectNames, byNames, places);
  assert.equal(matches.length, 1);
  assert.deepEqual(matches[0].routes, [
    'Peter von Rosenberg',
    'Hans von Rosenberg',
    'Ulrich von Rosenberg'
  ]);
  assert.deepEqual(coordinatedByNameRouteNames(source, titles, connectors, particles,
    projectNames, byNames, places), matches[0].routes);
});

test('retains a shared office title for coordinated brothers without adding it to their routes', () => {
  const source = 'Bernger and Heinrich, brothers von Eubigheim, Edelknecht, sell their forest';
  const scenarioTitles = `${titles}\n${projectTitles}`;
  const scenarioPlaces = [...places, { name: 'Eubigheim', variations: ['Eubigheim'] }];
  const matches = coordinatedByNameMatches(source, scenarioTitles, connectors, particles,
    projectNames, byNames, scenarioPlaces);
  assert.equal(matches.length, 1);
  assert.deepEqual(matches[0].routes, ['Bernger von Eubigheim', 'Heinrich von Eubigheim']);
  assert.deepEqual(matches[0].titles, ['Edelknecht']);
  assert.equal(matches[0].text, 'Bernger and Heinrich, brothers von Eubigheim, Edelknecht');
});

test('recognizes brothers Hans and Lutz Mönch von Rosenberg with their shared Hainstadt title', () => {
  const source = 'Brothers Hans and Lutz Mönch von Rosenberg zu Hainstadt, sell to the abbot';
  const scenarioPlaces = [...places, { name: 'Hainstadt', variations: ['Hainstadt'] }];
  const matches = coordinatedByNameMatches(source, titles, connectors, particles,
    projectNames, byNames, scenarioPlaces);
  assert.equal(matches.length, 1);
  assert.equal(matches[0].text, 'Hans and Lutz Mönch von Rosenberg zu Hainstadt');
  assert.deepEqual(matches[0].routes, [
    'Hans Mönch von Rosenberg',
    'Ludwig Mönch von Rosenberg'
  ]);
  assert.deepEqual(matches[0].titles, ['zu Hainstadt']);
});

test('keeps compound given names together in a coordinated von Rosenberg list', () => {
  const source = 'enfeoffs Adam Hector, Johann Konrad and Hans Dietrich von Rosenberg with houses';
  const matches = coordinatedByNameMatches(source, projectTitles, connectors, particles,
    projectNames, byNames, places);
  assert.equal(matches.length, 1);
  assert.deepEqual(matches[0].givenNames, ['Adam Hector', 'Johann Konrad', 'Hans Dietrich']);
  assert.deepEqual(matches[0].routes, [
    'Adam Hector von Rosenberg',
    'Hans Konrad von Rosenberg',
    'Hans Dietrich von Rosenberg'
  ]);
});

test('shared person parser returns the same coordinated names for English and German lists', () => {
  for (const source of [
    'Adam Hector, Johann Konrad and Hans Dietrich von Rosenberg',
    'Adam Hector, Johann Konrad und Hans Dietrich von Rosenberg',
  ]) {
    const result = findPersonNameMentions(source, titles, connectors, particles,
      projectNames, byNames, places, /Hans Dietrich von Rosenberg/giu,
      [{ pattern: /Konrad von Rosenberg/giu, people: [] }]);
    assert.deepEqual(result.coordinated[0]?.routes, [
      'Adam Hector von Rosenberg',
      'Hans Konrad von Rosenberg',
      'Hans Dietrich von Rosenberg',
    ]);
    assert.deepEqual(result.singles, []);
  }
});

test('does not attach Rudolf von Rosenberg to the preceding unrelated names', () => {
  const source = 'Benedikt Francke the Elder, the Council of Bautzen, Andreas Hentzsche, and Rudolf von Rosenberg.';
  assert.deepEqual(coordinatedByNameRouteNames(source, projectTitles, connectors, particles,
    projectNames, byNames, places), []);
});


test('a by-name that is also a title stays in the family name', async () => {
  const officeTitles = `${titles}\n${await readFile(new URL('../data/titles-office.md', import.meta.url), 'utf8')}`;
  const voitByNames = `${byNames}\nVoit, Voyt`;
  const voitPattern = buildSourcePersonPattern(projectNames, particles, places, officeTitles, connectors, voitByNames);
  const routes = (text) => findPersonNameMentions(text, officeTitles, connectors, particles, projectNames, voitByNames, places, voitPattern)
    .singles.map((single) => single.route);
  assert.deepEqual(routes('Friedrich Voit von Rosenberg'), ['Friedrich Voit von Rosenberg']);
  assert.deepEqual(routes('Georg Voit von Rosenberg der Jüngere'), ['Georg Voit von Rosenberg']);
  assert.deepEqual(routes('Hans Voit zu Rosenberg'), ['Hans Voit von Rosenberg']);
  assert.deepEqual(routes('Arnold von Rosenberg, Vogt'), ['Arnold von Rosenberg']);
});

const rulePlaces = [
  ...places,
  { name: 'Würzburg', variations: ['Würzburg', 'Wirtzeburg', 'Wurzburg'] },
  { name: 'Nürnberg', variations: ['Nürnberg', 'Nuremberg'] },
  { name: 'Hainstadt', variations: ['Hainstadt', 'Heinstadt'] },
  { name: 'Hanau', variations: ['Hanau'] },
  { name: 'Aisch', variations: ['Aisch'] },
  { name: 'Rieneck', variations: ['Rieneck'] },
  { name: 'Wertheim', variations: ['Wertheim'] },
  { name: 'Speyer', variations: ['Speyer'] },
  { name: 'Fulda', variations: ['Fulda'] },
  { name: 'Ebrach', variations: ['Ebrach'] },
  { name: 'Franken', variations: ['Franken', 'Franconia'] },
  { name: 'Heidelberg', variations: ['Heidelberg'] },
  { name: 'Schaumberg', variations: ['Schaumberg'] },
  { name: 'Böhmen', variations: ['Böhmen', 'Bohemia'] },
  { name: 'Hardegg', variations: ['Hardegg'] },
  { name: 'Schwarzburg', variations: ['Schwarzburg'] },
  { name: 'Brunn', variations: ['Brunn'] },
  { name: 'Leuchtenberg', variations: ['Leuchtenberg'] },
  { name: 'Pfalz', variations: ['Pfalz'] },
  { name: 'Vestenberg', variations: ['Vestenberg'] },
  { name: 'Rügland', variations: ['Rügland'] },
];
const ruleTitles = `${titles}\n${projectTitles}`;
const splitTitles = (name) => splitPersonNameTitles(name, ruleTitles);
const ruleNames = `${projectNames}\nLudwig\nPhilipp\nJulius\nWenzel\nThomas\nDorothea\nHiltpold\nEglolf\nEgilolf\nFriedrich`;
const ruleByNames = `${byNames}`;
const seatsText = await readFile(new URL('../data/title-seats.md', import.meta.url), 'utf8');
const ruleConnectors = `${connectors}\n${seatsText}`;
const rulePattern = buildSourcePersonPattern(ruleNames, particles, rulePlaces, ruleTitles, ruleConnectors, ruleByNames);
const mentionsIn = (text) => {
  const result = findPersonNameMentions(text, ruleTitles, ruleConnectors, particles, ruleNames, ruleByNames, rulePlaces, rulePattern);
  return [...result.singles, ...result.coordinated.flatMap((group) => group.members.map((member) => ({ ...member, text: group.text })))]
    .map(({ route, titles: found }) => ({ route, titles: found }));
};
const routeOf = (name) => personRouteName(name, ruleTitles, ruleConnectors, particles, ruleNames, ruleByNames, rulePlaces);

test('territorial titles take the place after them, never the family name', () => {
  for (const [text, route, found] of [
    ['Bishop Konrad of Würzburg', 'Bischof Konrad', ['Bischof zu Würzburg']],
    ['Konrad zu Würzburg, Bischof', 'Bischof Konrad', ['Bischof zu Würzburg']],
    ['Johann II zu Würzburg, Bischof', 'Bischof Hans', ['Bischof zu Würzburg']],
    ['Heinrich zu Fulda, Abt', 'Heinrich', ['Abt zu Fulda']],
    ['Otto zu Ebrach, Abt', 'Otto', ['Abt zu Ebrach']],
    ['Philipp zu Speyer, Bischof', 'Bischof Philipp', ['Bischof zu Speyer']],
    ['Johann, Abt von Fulda', 'Hans', ['Abt von Fulda']],
    ['Friedrich, Bishop of Würzburg, Duke of Franconia', 'Bischof Friedrich', ['Bischof zu Würzburg', 'Herzog zu Franken']],
    ['Julius, Bischof zu Würzburg, Herzog zu Franken', 'Bischof Julius', ['Bischof zu Würzburg', 'Herzog zu Franken']],
    ['Burgrave Friedrich zu Nuremberg', 'Friedrich', ['Burggraf zu Nürnberg']],
    ['Gerhard von Schwarzburg, Bischof', 'Gerhard von Schwarzburg', ['Bischof']],
  ]) {
    const found2 = mentionsIn(text);
    assert.deepEqual(found2.slice(0, 1), [{ route, titles: found }], text);
  }
});

test('a count takes the place as family name and keeps the source particle', () => {
  for (const [text, route, found] of [
    ['Thomas, Graf von Rieneck', 'Thomas von Rieneck', ['Graf von Rieneck']],
    ['Count Thomas of Rieneck', 'Thomas von Rieneck', ['Graf von Rieneck']],
    ['Count Thomas von Rieneck', 'Thomas von Rieneck', ['Graf von Rieneck']],
    ['Graf Thomas von Rieneck', 'Thomas von Rieneck', ['Graf von Rieneck']],
    ['Johann, Graf zu Hardegg', 'Hans zu Hardegg', ['Graf zu Hardegg']],
    ['Junker Eberhart, Graf von Wertheim', 'Eberhard von Wertheim', ['Junker', 'Graf von Wertheim']],
  ]) {
    assert.deepEqual(mentionsIn(text).slice(0, 1), [{ route, titles: found }], text);
  }
});

test('a king keeps the realm out of the route', () => {
  assert.deepEqual(mentionsIn('King Wenzel of Bohemia').slice(0, 1), [{ route: 'König Wenzel', titles: ['König von Böhmen'] }]);
  assert.deepEqual(mentionsIn('King Wenzel IV of Bohemia').slice(0, 1), [{ route: 'König Wenzel', titles: ['König von Böhmen'] }]);
});

test('by-name with zu is von only for Rosenberg; other places are designations', () => {
  assert.deepEqual(mentionsIn('Hanns Truchseß zu Aue'), [{ route: 'Hans Truchsess', titles: ['zu Aue'] }]);
  assert.deepEqual(mentionsIn('Hans Stieber zu Aisch'), [{ route: 'Hans Stieber', titles: ['zu Aisch'] }]);
  assert.deepEqual(mentionsIn('Hans Schenk zu Rosenberg'), [{ route: 'Hans Schenk von Rosenberg', titles: [] }]);
  assert.equal(routeOf('Hans Schenk von Rosenberg'), 'Hans Schenk von Rosenberg');
});

test('of between a name and a place is not guessed into a particle', () => {
  assert.equal(routeOf('Hans of Wertheim'), 'Hans of Wertheim');
});

test('an unlisted title place is a capitalized non-article word', () => {
  for (const text of [
    'Peter zu Rosenberg, Vitzthum zu the Bartholomew church',
    'Peter zu Rosenberg, Domherr zu the Bartholomew church',
  ]) {
    const [single] = mentionsIn(text);
    assert.equal(single.route, 'Peter zu Rosenberg', text);
    assert.ok(single.titles.every((found) => !/\bthe\b/iu.test(found)), `${text}: ${single.titles}`);
  }
  assert.deepEqual(mentionsIn('Konrad von Rosenberg, Vogt zu Bergen').at(0)?.titles, ['Vogt zu Bergen']);
});

test('title places and designations use the canonical place', () => {
  assert.deepEqual(mentionsIn('Konrad von Rosenberg, Burggraf zu Nuremberg'), [{ route: 'Konrad von Rosenberg', titles: ['Burggraf zu Nürnberg'] }]);
  assert.deepEqual(mentionsIn('Konrad von Rosenberg zu Heinstadt'), [{ route: 'Konrad von Rosenberg', titles: ['zu Hainstadt'] }]);
});

test('trailing punctuation never becomes part of a title or name', () => {
  assert.deepEqual(mentionsIn('Georg von Rosenberg, Amtmann zu Hanau.'), [{ route: 'Georg von Rosenberg', titles: ['Amtmann zu Hanau'] }]);
  assert.deepEqual(mentionsIn('Hans Stieber von Aisch.'), [{ route: 'Hans Stieber von Aisch', titles: [] }]);
  assert.equal(findPersonNameMentions('Georg von Rosenberg, Amtmann zu Hanau.', ruleTitles, ruleConnectors, particles, ruleNames,
    ruleByNames, rulePlaces, rulePattern).singles[0].text, 'Georg von Rosenberg, Amtmann zu Hanau');
});

test('a leading title place must be a place and a route is never empty of given names', () => {
  assert.deepEqual(mentionsIn('Abbot of St. Burkard in Würzburg'), []);
  assert.deepEqual(mentionsIn('Count of Schaumberg. Heinrich von Rosenberg'), [{ route: 'Heinrich von Rosenberg', titles: [] }]);
});

test('a bare place surname never crosses a sentence end', () => {
  assert.deepEqual(mentionsIn('Count Palatine Friedrich IV.   Heidelberg, October 1'), []);
  assert.deepEqual(mentionsIn('Count Palatine Friedrich IV. Heidelberg, October 1'), []);
  assert.deepEqual(mentionsIn('Hans II. Heidelberg'), []);
  assert.deepEqual(mentionsIn('Hans von Rosenberg. Heidelberg lies on the Neckar'), [{ route: 'Hans von Rosenberg', titles: [] }]);
});

test('recognizes a title after a bare place surname', () => {
  const scenarioPlaces = [{ name: 'Rosenberg', variations: ['Rosenberg', 'Rosenberger'] },
    { name: 'Oggersheim', variations: ['Oggersheim'] }];
  const scenarioTitles = `${titles}\nSchultheiß`;
  const sourcePattern = buildSourcePersonPattern(names, particles, scenarioPlaces, scenarioTitles, connectors, byNames);
  const text = 'friend Michael Rosenberger, Schultheiß zu Oggersheim and son-in-law';
  const found = findPersonNameMentions(text, scenarioTitles, connectors, particles, names, byNames, scenarioPlaces, sourcePattern);
  assert.deepEqual(found.singles.map(({ text, route, titles }) => ({ text, route, titles })), [{
    text: 'Michael Rosenberger, Schultheiß zu Oggersheim',
    route: 'Michael Rosenberg',
    titles: ['Schultheiß zu Oggersheim'],
  }]);
});

test('an age title and a designation are separate canonical titles', () => {
  assert.deepEqual(mentionsIn('Eberhard von Rosenberg der Junge, called von Thüngen'),
    [{ route: 'Eberhard von Rosenberg', titles: ['der Junge', 'genannt von Thüngen'] }]);
});

test('a lone title word after one given name is a surname', () => {
  assert.equal(routeOf('Georg Keller'), 'Georg Keller');
  assert.equal(routeOf('Hans Schultheiß, Schultheiß zu Würzburg'), 'Hans Schultheiß');
  assert.deepEqual(splitTitles('Georg Keller'), { name: 'Georg Keller', titles: [] });
});

test('a title before a given name belongs to the next person in a coordinated list', () => {
  const source = 'Eglolf and Egilolf von Rosenberg, Abbot Hiltpold';
  const [group] = coordinatedByNameMatches(source, ruleTitles, ruleConnectors, particles, ruleNames, ruleByNames, rulePlaces);
  assert.deepEqual(group.members, [
    { route: 'Eglolf von Rosenberg', titles: [] },
    { route: 'Egilolf von Rosenberg', titles: [] },
  ]);
  assert.deepEqual(group.titles, []);
  assert.equal(mentionsIn(source).length, 2);
});

test('a territorial title and a place after a coordinated list belong to the last person only', () => {
  const [group] = coordinatedByNameMatches('Elector Ludwig and Philipp zu Speyer, Bischof', ruleTitles, ruleConnectors, particles,
    ruleNames, ruleByNames, rulePlaces);
  assert.deepEqual(group.members, [
    { route: 'Ludwig', titles: ['Kurfürst'] },
    { route: 'Bischof Philipp', titles: ['Bischof zu Speyer'] },
  ]);
});

test('a birth name becomes the route while the married designation stays a title', () => {
  assert.deepEqual(mentionsIn('Dorothea von Wertheim, Gräfin, née von Rieneck'),
    [{ route: 'Dorothea von Rieneck', titles: ['von Wertheim', 'Graf'] }]);
  assert.deepEqual(mentionsIn('Elisabeth von Rosenberg, née Marschalk von Pappenheim'),
    [{ route: 'Elisabeth Marschalk von Pappenheim', titles: ['von Rosenberg'] }]);
});

test('recognizes Anna Marschalk von Pappenheim and her son Kunz von Rosenberg', () => {
  const names = `${ruleNames}\nAnna\nKunz`;
  const places = [...rulePlaces, { name: 'Minneburg', variations: ['Minneburg'] }];
  const sourcePattern = buildSourcePersonPattern(names, particles, places, ruleTitles, ruleConnectors, ruleByNames);
  const text = 'I, Anna Marschalk von Pappenheim, I, Kunz von Rosenberg der Ältere zu Minneburg, her son';
  const found = findPersonNameMentions(text, ruleTitles, ruleConnectors, particles, names, ruleByNames, places, sourcePattern);
  assert.deepEqual(found.singles.map(({ route, titles: foundTitles }) => ({ route, titles: foundTitles })), [
    { route: 'Anna Marschalk von Pappenheim', titles: [] },
    { route: 'Kunz von Rosenberg', titles: ['der Ältere', 'zu Minneburg'] },
  ]);
});

test('every trailing title is returned', () => {
  assert.deepEqual(mentionsIn('Konrad von Rosenberg, Ritter, Vogt zu Lauda, Amtmann zu Amberg'),
    [{ route: 'Konrad von Rosenberg', titles: ['Ritter', 'Vogt zu Lauda', 'Amtmann zu Amberg'] }]);
});

test('dictionaries are built once per argument set', () => {
  const first = buildSourcePersonPattern(ruleNames, particles, rulePlaces, ruleTitles, ruleConnectors, ruleByNames);
  const second = buildSourcePersonPattern(ruleNames, particles, rulePlaces, ruleTitles, ruleConnectors, ruleByNames);
  assert.equal(first.source, second.source);
  const started = performance.now();
  for (let index = 0; index < 200; index += 1) routeOf('Knight Hans von Rosenberg, Vogt zu Lauda');
  assert.ok(performance.now() - started < 1000);
});

test('a lowercase unlisted word is not a title place and non-Latin1 text does not change matches', () => {
  assert.deepEqual(mentionsIn('Konrad von Rosenberg, Vogt zu bergen'), [{ route: 'Konrad von Rosenberg', titles: ['Vogt'] }]);
  assert.deepEqual(mentionsIn('⁵¹ Konrad von Rosenberg, Vogt zu Lauda'), [{ route: 'Konrad von Rosenberg', titles: ['Vogt zu Lauda'] }]);
});

test('a leading territorial title takes the place after the given name', () => {
  for (const [text, route, found] of [
    ['Bischof Konrad von Würzburg', 'Bischof Konrad', ['Bischof von Würzburg']],
    ['Bishop Rudolf von Würzburg', 'Bischof Rudolf', ['Bischof von Würzburg']],
    ['Bishop Rudolf of Würzburg', 'Bischof Rudolf', ['Bischof zu Würzburg']],
    ['Gerhard von Schwarzburg, Bischof', 'Gerhard von Schwarzburg', ['Bischof']],
  ]) assert.deepEqual(mentionsIn(text).slice(0, 1), [{ route, titles: found }], text);
});

test('ranks never take a place', () => {
  assert.deepEqual(mentionsIn('Albrecht von Rosenberg, Ritter zu Boxberg'),
    [{ route: 'Albrecht von Rosenberg', titles: ['Ritter', 'zu Boxberg'] }].map((item) => ({ ...item, titles: item.titles })));
});

test('recognizes two trailing zu-place titles', () => {
  assert.deepEqual(mentionsIn('Caspar von Vestenberg zu Rügland zu Rosenberg received'), [
    { route: 'Caspar von Vestenberg', titles: ['zu Rügland', 'zu Rosenberg'] },
  ]);
});

test('a realm title takes only a listed realm after of or von', () => {
  const only = (text) => mentionsIn(text).slice(0, 1);
  assert.deepEqual(only('King Wenzel of Bohemia'), [{ route: 'König Wenzel', titles: ['König von Böhmen'] }]);
  for (const text of ['King Wenzel of Bohemian', 'King Wenzel of Atlantis']) {
    assert.deepEqual(only(text), [{ route: 'König Wenzel', titles: ['König'] }].slice(0, 1), text);
  }
  assert.deepEqual(only('King Wenzel of Bohemia’s'), [{ route: 'König Wenzel', titles: ['König'] }]);
  assert.deepEqual(only('the Roman King Hans von Neitperg and Ulrich Riederer'), [{ route: 'Hans von Neitperg', titles: [] }]);
});

test('a possessive after a realm title or name is ignored', () => {
  assert.deepEqual(mentionsIn("King Albrecht's charter").slice(0, 1), [{ route: 'König Albrecht', titles: ['König'] }]);
});

test('after a leading title von is the office place only for a listed seat or realm', () => {
  const only = (text) => mentionsIn(text).slice(0, 1);
  assert.deepEqual(only('Bishop Hans von Brunn'), [{ route: 'Hans von Brunn', titles: ['Bischof'] }]);
  assert.deepEqual(only('Bishop Konrad von Thüngen'), [{ route: 'Konrad von Thüngen', titles: ['Bischof'] }]);
  assert.deepEqual(only('Abbess Ottilia von Rosenberg'), [{ route: 'Ottilia von Rosenberg', titles: ['Äbtissin'] }]);
  assert.deepEqual(only('Count Palatine Wolfgang von Rosenberg'), [{ route: 'Wolfgang von Rosenberg', titles: ['Pfalzgraf'] }]);
  assert.deepEqual(only('Landgrave Hans von Rieneck'), [{ route: 'Hans von Rieneck', titles: ['Landgraf'] }]);
  assert.deepEqual(only('Count Palatine Otto von Pfalz'), [{ route: 'Otto', titles: ['Pfalzgraf von Pfalz'] }]);
  assert.deepEqual(only('King Philipp von Spanien'), [{ route: 'König Philipp', titles: ['König von Spanien'] }]);
  assert.deepEqual(only('King Philipp of Spain'), [{ route: 'König Philipp', titles: ['König von Spanien'] }]);
  const vomPattern = buildSourcePersonPattern(ruleNames, `${particles}\nvom`, rulePlaces, ruleTitles, ruleConnectors, ruleByNames);
  const vom = findPersonNameMentions('Landgraf Hans vom Leuchtenberg', ruleTitles, ruleConnectors, `${particles}\nvom`, ruleNames, ruleByNames, rulePlaces, vomPattern);
  assert.deepEqual(vom.singles.map(({ route, titles: found }) => ({ route, titles: found })), [{ route: 'Hans', titles: ['Landgraf von Leuchtenberg'] }]);
});
