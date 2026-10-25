export function factText(fact) {
  return fact && typeof fact === 'object' ? String(fact.text || '') : String(fact || '');
}

// Explicit IDs stay specific; plain names use the generic name route.
export function renderFactText(fact, { people = [], inlineMarkup }) {
  const peopleById = new Map(people.filter((person) => person.id).map((person) => [person.id, person]));
  const links = [];
  let text = factText(fact).replace(/\[([^\]]+)\]/g, (match, id) => {
    const person = peopleById.get(id);
    if (!person) return match;
    const marker = `\u0001FACTPERSON${links.length}\u0002`;
    links.push(`<a class="person-link" href="?person=${encodeURIComponent(person.id)}">${inlineMarkup(person.name, false)}</a>`);
    return marker;
  });
  const names = [...new Set(people.map((person) => person.name).filter(Boolean))]
    .sort((left, right) => right.length - left.length)
    .map((name) => name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (names.length) {
    const pattern = new RegExp(`(?<![\\p{L}\\p{N}])(?:${names.join('|')})(?![\\p{L}\\p{N}])`, 'giu');
    text = text.replace(pattern, (match) => {
      const person = people.find((item) => item.name.toLocaleLowerCase() === match.toLocaleLowerCase());
      if (!person) return match;
      const marker = `\u0001FACTPERSON${links.length}\u0002`;
      // Plain names are generic routes; explicit ID tokens above remain specific.
      links.push(`<a class="person-link" href="?person=${encodeURIComponent(person.name)}">${inlineMarkup(match, false)}</a>`);
      return marker;
    });
  }
  const rendered = inlineMarkup(text, false);
  return rendered.replace(/\u0001FACTPERSON(\d+)\u0002/g, (match, index) => links[Number(index)] ?? match);
}
