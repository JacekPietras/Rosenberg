// Pure logic of enrich_fact_titles.mjs: which titles an entry's mentions add to its facts' people.

// Fact participants of an entry whose name is a plain route name or a registered person.
export function participants(entry, { route, registry }) {
  const result = [];
  for (const fact of entry.facts ?? []) {
    if (!fact || typeof fact !== 'object' || fact.type === 'title' || fact.date !== undefined) continue;
    for (const [field, titleField] of [['person', 'personTitle'], ['of', 'ofTitle']]) {
      const name = fact[field];
      if (typeof name !== 'string') continue;
      if (registry.has(name)) {
        result.push({ fact, field, titleField, key: route(registry.get(name)), registered: true, existing: [] });
        continue;
      }
      if (route(name) !== name) continue;
      result.push({ fact, field, titleField, key: name, existing: fact[titleField] ?? [],
        deceased: Boolean(fact[`${field}Deceased`]) });
    }
  }
  return result;
}

// A person gets titles only from the single mention compatible with their own
// titles; nothing is added when another same-named person could own that mention.
export function enrichEntry(entry, { route, registry, titles }) {
  const people = participants(entry, { route, registry });
  const report = [];
  if (!people.length) return report;
  const mentions = (entry.mention ?? []).filter((item) => typeof item.person === 'string')
    .map((item) => ({ key: registry.has(item.person) ? route(registry.get(item.person)) : item.person,
      titles: titles.canonicalTitles(item.personTitle ?? []) }));
  for (const key of new Set(people.map((person) => person.key))) {
    const mine = people.filter((person) => person.key === key);
    if (mine.some((person) => person.registered)) continue;
    if (new Set(mine.map((person) => person.deceased)).size > 1
      || mine.some((person) => person.fact.person === person.fact.of)) continue;
    if (mine.some((person) => mine.some((other) => other.fact === person.fact && other !== person))) continue;
    const theirs = mentions.filter((mention) => mention.key === key);
    for (const person of mine) {
      const own = titles.canonicalTitles(person.existing);
      const fits = theirs.filter((mention) => titles.compatible(own, mention.titles));
      if (fits.length !== 1) continue;
      const [mention] = fits;
      const bases = new Set(own.map((title) => titles.parseTitle(title)).map((item) => item.base ?? item.value));
      const shares = !own.length || mention.titles.some((title) => {
        const parsed = titles.parseTitle(title);
        return titles.covers(own, [title]) || bases.has(parsed.base ?? parsed.value);
      });
      const contested = mine.some((other) => other !== person && other.fact !== person.fact
        && titles.compatible(titles.canonicalTitles(other.existing), mention.titles)
        && !titles.compatible(titles.canonicalTitles(other.existing), own));
      if (!shares || contested) continue;
      const added = mention.titles.filter((title) => titles.parseTitle(title).kind !== 'other'
        && !titles.covers(own, [title]));
      const final = titles.consolidateTitles([...own, ...added]);
      if (added.length && JSON.stringify(final) !== JSON.stringify(own)) report.push({ person, added, final });
    }
  }
  return report;
}
