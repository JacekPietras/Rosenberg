import { imageCardMarkup } from '../rendering/images.js?v=5';

export function createEntityScreens({
  state,
  getDocuments,
  getPlaces,
  getPeople,
  buildPlacePattern,
  buildPersonPattern,
  escapeHtml,
  inlineMarkup,
  markdownLinks,
  formatDate,
  dateSortValue,
  documentTitle,
  documentNavigationUrl,
  displayedLanguagesFor,
}) {
  const fields = ['title', 'source', 'german', 'latin', 'english', 'facts'];

  const findByName = (entities, name) => entities.find((entity) => entity.name.toLocaleLowerCase() === String(name).toLocaleLowerCase());
  const fieldText = (entry, field) => Array.isArray(entry[field]) ? entry[field].join('\n') : String(entry[field] || '');

  function mentionsFor(entity, kind) {
    const patterns = kind === 'person' ? buildPersonPattern([entity]).map(({ pattern }) => pattern) : [buildPlacePattern([entity])];
    const mentions = [];
    getDocuments().forEach((doc, path) => (Array.isArray(doc?.entries) ? doc.entries : []).forEach((entry, index) => {
      if (patterns.some((pattern) => pattern && fields.some((field) => {
        pattern.lastIndex = 0;
        return pattern.test(fieldText(entry, field)) || (field === 'title' && pattern.test(String(doc.place || '')));
      }))) mentions.push({ doc, path, entry, index });
    }));
    return mentions;
  }

  function factDate(fact, doc, entry) {
    return fact && typeof fact === 'object' && fact.date ? fact.date : entry.date || doc.date || '';
  }

  function factText(fact) {
    return fact && typeof fact === 'object' ? fact.text : fact;
  }

  function renderFacts(mentions, factMatches = () => true) {
    const facts = mentions.flatMap(({ doc, path, entry, index }, mentionIndex) => (Array.isArray(entry.facts) ? entry.facts : [])
      .map((fact, factIndex) => ({ date: factDate(fact, doc, entry), text: factText(fact), mentionIndex, factIndex }))
      .filter((fact) => String(fact.text || '').trim() && factMatches(fact.text))
      .sort((left, right) => dateSortValue(left.date) - dateSortValue(right.date) || left.mentionIndex - right.mentionIndex || left.factIndex - right.factIndex));
    if (!facts.length) return '';
    const items = facts.map((fact, index) => {
      const showDate = index === 0 || fact.date !== facts[index - 1].date;
      const date = showDate && fact.date ? `<time class="entity-fact-date" datetime="${escapeHtml(fact.date)}">${escapeHtml(formatDate(fact.date))}</time>` : showDate ? '<span class="entity-fact-date">Undated</span>' : '<span class="entity-fact-date" aria-hidden="true"></span>';
      return `<li>${date}<span class="entity-fact-text">${inlineMarkup(fact.text)}</span></li>`;
    }).join('');
    return `<section class="entity-facts"><h3>Facts</h3><ul class="facts">${items}</ul></section>`;
  }

  function excerpt(value, pattern, linkEntities = true) {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    if (!text) return '';
    const sentences = text.split(/(?<=[.!?。！？])\s+/).filter((sentence) => { pattern.lastIndex = 0; return pattern.test(sentence); });
    let result = sentences.slice(0, 2).join(' ') || text;
    pattern.lastIndex = 0;
    const match = pattern.exec(result);
    if (match && result.length > 420) {
      const limit = 360;
      const maxStart = Math.max(0, result.length - limit);
      let start = Math.min(Math.max(0, match.index - 170), maxStart);
      if (match.index + match[0].length > start + limit) start = Math.min(match.index, maxStart);
      result = `${start ? '…' : ''}${result.slice(start, start + limit)}${start + limit < result.length ? '…' : ''}`;
    }
    return inlineMarkup(result, linkEntities);
  }

  function languageMarkup(entry, pattern) {
    const languages = displayedLanguagesFor(entry);
    if (!languages.length) return '';
    return `<div class="text-grid ${languages.length === 1 ? 'single' : ''}">${languages.map((language) => `<div class="language"><div class="text"><p>${excerpt(entry[language], pattern, language === 'english')}</p></div></div>`).join('')}</div>`;
  }

  function renderPage(entity, mentions, kind, pattern, extraMarkup = () => '', leadingMarkup = '', factMatches = () => true) {
    if (!entity) return `<article class="document"><h2>${kind === 'place' ? 'Place' : 'Person'} not found</h2><p class="status">No ${kind} matching the requested name is listed in the research data.</p></article>`;
    const heading = `<article class="document ${kind}-document-heading"><div class="document-heading"><div><h2>${escapeHtml(entity.name)}</h2></div><small>${mentions.length} mention${mentions.length === 1 ? '' : 's'}</small></div></article>`;
    const sorted = [...mentions].sort((left, right) => dateSortValue(left.entry.date || left.doc.date) - dateSortValue(right.entry.date || right.doc.date) || left.index - right.index);
    const content = sorted.map(({ doc, path, entry, index }) => {
      const date = entry.date || doc.date || '';
      return `<article class="document ${kind}-mention" role="link" tabindex="0" data-document-href="${escapeHtml(documentNavigationUrl(path, index))}"><p class="entry-title">${markdownLinks(entry.title || documentTitle(doc, path))}</p>${date ? `<p class="entry-date">${escapeHtml(formatDate(date))}</p>` : ''}${entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry, pattern) : ''}${extraMarkup(doc, entry)}</article>`;
    }).join('');
    return `${heading}${leadingMarkup}${renderFacts(mentions, factMatches)}${content ? `<h3 class="entity-section-title">Direct quotations</h3>${content}` : '<article class="document"><p class="status">No mentions found.</p></article>'}`;
  }

  function renderPersonPage() {
    const people = getPeople();
    const person = people.find((item) => item.id === state.person)
      || findByName(people, state.person);
    const pattern = person ? buildPersonPattern([person])[0]?.pattern : /$a/;
    return renderPage(person, person ? mentionsFor(person, 'person') : [], 'person', pattern);
  }

  function renderPlacePage() {
    const entity = findByName(getPlaces(), state.place);
    const place = entity || getPlaces().find((item) => item.name.toLocaleLowerCase() === String(state.place || '').toLocaleLowerCase());
    const pattern = place ? buildPlacePattern([place]) : /$a/;
    const mentions = place ? mentionsFor(place, 'place') : [];
    const effigies = place ? (state.manifest?.collections || []).filter((item) => item.placeId === place.id) : [];
    const factMatches = (text) => {
      if (!pattern) return false;
      pattern.lastIndex = 0;
      const matches = pattern.test(String(text || ''));
      pattern.lastIndex = 0;
      return matches;
    };
    const effigyMarkup = effigies.length ? `<section class="entity-effigies"><h3>Effigies</h3><div class="models-grid">${effigies.map((item) => imageCardMarkup(item)).join('')}</div></section>` : '';
    const historyItems = place?.history ? String(place.history).split(/\r?\n/).map((item) => item.replace(/^\s*[-*]\s+/, '').trim()).filter(Boolean) : [];
    const historyMarkup = historyItems.length ? `<section class="entity-history"><h3>History</h3><ul>${historyItems.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></section>` : '';
    return renderPage(place, mentions, 'place', pattern, (doc) => doc.place ? `<p class="place-record">Document place: ${inlineMarkup(doc.place)}</p>` : '', `${historyMarkup}${effigyMarkup}`, factMatches);
  }

  return { renderPersonPage, renderPlacePage };
}
