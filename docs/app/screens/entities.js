import { imageCardMarkup } from '../rendering/images.js?v=13';
import { factText, factPersonMatch, sourceFactDate, isTypedFact } from '../rendering/facts.js?v=6';
import { renderFactsView } from '../components/facts_view.js?v=6';
import { findPlaceByName } from '../data/entities.js?v=87';
import { resolvePerson, resolveEvidencePointer } from '../data/relationships.js?v=7';
import { relationshipControls, relationshipPanel } from '../rendering/relationships.js?v=7';

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
  imageMarkup,
}) {
  const fields = ['title', 'source', 'german', 'latin', 'english', 'facts'];

  const findByName = (entities, name) => entities.find((entity) => entity.name.toLocaleLowerCase() === String(name).toLocaleLowerCase());
  const fieldText = (entry, field) => Array.isArray(entry[field]) ? entry[field].map((value) => field === 'facts' ? factText(value, getPeople()) : String(value)).join('\n') : String(entry[field] || '');

  function mentionsFor(entity, kind) {
    const patterns = kind === 'person' ? buildPersonPattern([entity]).map(({ pattern }) => pattern) : [buildPlacePattern([entity])];
    const mentions = [];
    getDocuments().forEach((doc, path) => (Array.isArray(doc?.entries) ? doc.entries : []).forEach((entry, index) => {
      const factMatch = kind === 'person' && (entry.facts || []).some((fact) => factPersonMatch(fact, state.person || entity.id || entity.name, getPeople()));
      if (factMatch || patterns.some((pattern) => pattern && fields.some((field) => {
        if (kind === 'person' && field === 'facts') return false;
        pattern.lastIndex = 0;
        return pattern.test(fieldText(entry, field))
          || (field === 'title' && pattern.test(String(doc.place || '')));
      }))) mentions.push({ doc, path, entry, index });
    }));
    return mentions;
  }

  function renderFacts(mentions, factMatches = () => true) {
    const people = getPeople();
    const personQuery = state.person || '';
    const facts = mentions.flatMap(({ doc, path, entry, index }, mentionIndex) => (Array.isArray(entry.facts) ? entry.facts : [])
      .map((fact, factIndex) => ({
        ...(fact && typeof fact === 'object' ? fact : { text: fact }),
        date: sourceFactDate(fact, doc, entry, path),
        mentionIndex, factIndex, sourceHref: documentNavigationUrl(path, index),
        personMatch: personQuery ? factPersonMatch(fact, personQuery, people) : 'direct',
      }))
      .filter((fact) => factText(fact, people).trim() && factMatches(factText(fact, people)) && fact.personMatch))
      .sort((left, right) => dateSortValue(left.date) - dateSortValue(right.date) || left.mentionIndex - right.mentionIndex || left.factIndex - right.factIndex);
    if (!facts.length) return '';
    const items = renderFactsView(facts, {
      people,
      inlineMarkup,
      sourceHref: (fact) => fact.sourceHref,
      itemClass: (fact) => fact.personMatch === 'ambiguous' ? ' class="entity-fact-ambiguous"' : '',
    });
    return `<section class="entity-facts"><h3>Facts</h3>${items}</section>`;
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
    if (state.sourcePersonChoices?.reference === state.person && state.familyGraph?.valid) {
      const { name, matches } = state.sourcePersonChoices;
      return `<article class="document"><h2>${escapeHtml(name)}</h2><p>This source identity ${matches.length ? 'separates into several groups' : 'is not present'} in the selected evidence view.</p><ul>${matches.map((person) => `<li><a class="person-link" href="?person=${encodeURIComponent(person.id || person._treeKey)}">${escapeHtml(person.name)}</a> · ${escapeHtml((person.reconstruction?.dates || []).join(', '))}</li>`).join('')}</ul><a href="?tab=tree">Open the family tree</a></article>${relationshipControls(state.familyGraph)}`;
    }
    const resolution = resolvePerson(people, state.person);
    const exactAnchor = people.some((person) => person.id && person.id === state.person);
    // Names collect all matching mentions; only an evidence key selects a source identity.
    const reconstructed = state.familyGraph?.valid && !exactAnchor
      ? state.familyGraph.records.find((record) => record._evidence && record._treeKey === state.person)
      : undefined;
    if (reconstructed) {
      const node = reconstructed.reconstruction;
      const seen = new Set();
      const occurrences = node.mentions.filter(({ source }) => {
        const key = source.path + '#' + source.pointer;
        if (seen.has(key)) return false;
        seen.add(key); return true;
      });
      const attestations = occurrences.map(({ source, date }) => {
        const doc = getDocuments().get(source.path);
        const fact = resolveEvidencePointer(doc, source.pointer);
        const index = Number(source.pointer.match(/\/entries\/(\d+)/)?.[1] || 0);
        return `<article class="document"><p class="entry-date">${source.pointer.includes('/guesses/') ? 'Guess · ' : ''}${escapeHtml(formatDate(date))}</p>${renderFactsView([{ ...(typeof fact === 'string' ? { text: fact } : fact), date }], { people, inlineMarkup, sourceHref: () => documentNavigationUrl(source.path, index) })}<p class="source"><a href="${escapeHtml(documentNavigationUrl(source.path, index))}">${escapeHtml(source.path)}#${escapeHtml(source.pointer)}</a></p></article>`;
      }).join('');
      return `<article class="document person-document-heading"><h2>${escapeHtml(node.name)}</h2><p>${node.status === 'contextual' ? 'Inferred identity across source passages; dated titles, places, family context and weighted source evidence supply the links.' : 'Source person; correspondence with other mentions remains open.'} No permanent person ID has been created.</p></article>${relationshipControls(state.familyGraph)}${relationshipPanel(state.familyGraph, node.key)}<h3>Source attestations</h3>${attestations}`;
    }
    if (String(state.person).startsWith('@evidence/')) return '<article class="document"><h2>Source identity changed</h2><p>This generated source group changed after rebuilding.</p><a href="?tab=tree">Open the family tree to choose its current source identities</a></article>';
    let person = exactAnchor ? resolution.person
      : { name: resolution.matches[0]?.name || String(state.person) };
    const mentions = mentionsFor(person, 'person');
    if (!exactAnchor && !resolution.matches.length && !mentions.length) person = undefined;
    const pattern = person ? buildPersonPattern([person])[0]?.pattern : /$a/;
    if (!person) return renderPage(person, [], 'person', pattern);
    const selectedId = people.some((item) => item.id === state.person) ? person.id : '';
    const selectedIds = selectedId ? [selectedId] : people
      .filter((item) => item.id && item.name.toLocaleLowerCase() === person.name.toLocaleLowerCase())
      .map((item) => item.id);
    const matchesPerson = (value, personId) => {
      const text = String(value || '');
      return selectedIds.some((id) => personId === id || text.includes(`[${id}]`))
        || (!selectedId && text.toLocaleLowerCase().includes(person.name.toLocaleLowerCase()));
    };
    const imageEntries = getDocuments().get('data/images/images.json')?.entries || [];
    const relatedImages = imageEntries.filter((entry) => matchesPerson(
      [entry.title, entry.description, ...(Array.isArray(entry.facts) ? entry.facts : []).filter((fact) => !isTypedFact(fact)).map((fact) => factText(fact, people))].join(' '), entry.personId || entry.personid,
    ) || (entry.facts || []).some((fact) => isTypedFact(fact) && factPersonMatch(fact, state.person, people) === 'direct'));
    const imagesMarkup = relatedImages.length ? `<section class="entity-images"><h3 class="entity-section-title">Images</h3><div class="models-grid armorial-grid">${relatedImages.map((entry) => imageCardMarkup(entry, { titleMarkup: inlineMarkup })).join('')}</div></section>` : '';
    const sealEntries = [];
    getDocuments().forEach((doc, path) => {
      if (!path.startsWith('data/documents/')) return;
      (doc?.entries || []).forEach((entry, index) => {
        const nodes = Array.isArray(entry.img) ? entry.img : [entry.img];
        nodes.forEach((node, imageIndex) => {
          if (!node || (typeof node === 'object' && node.deleted === 'true')) return;
          const seals = node && typeof node === 'object' ? node.seals : imageIndex === 0 ? entry.seals : [];
          (Array.isArray(seals) ? seals : []).forEach((seal) => {
            if (!matchesPerson(seal?.person, '')) return;
            const position = String(seal.position || '').split(',').map(Number);
            const size = Number(seal.size);
            if (position.length !== 2 || !position.every(Number.isFinite) || !Number.isFinite(size) || size <= 0) return;
            const crop = { x: position[0], y: position[1], size, width: Number(seal.width) || 0, wideningRotation: Number(seal.wideningRotation) || 0, rotation: Number(seal.rotation) || 0 };
            sealEntries.push({ doc, path, entry, index, node, imageIndex, seal, crop });
          });
        });
      });
    });
    const sealsMarkup = sealEntries.length ? `<section class="entity-seals"><h3 class="entity-section-title">Seals</h3><div class="models-grid armorial-grid">${sealEntries.map(({ doc, path, entry, index, node, imageIndex, seal, crop }) => {
      const date = entry.date || doc.date || '';
      const title = entry.title || documentTitle(doc, path);
      return `<article class="model-card"><div class="model-info"><h2 class="model-title">${markdownLinks(title)}${date ? ` [${escapeHtml(date)}]` : ''}</h2></div><div class="image-record-visual seal-entry-media">${imageMarkup(node, [seal], { path, index, imageIndex, title, crop, sealScreen: true })}</div></article>`;
    }).join('')}</div></section>` : '';
    const personPlacesMarkup = person ? '<section class="person-places-map"><div class="person-map-wrap"><div id="person-place-map" class="map-container person-place-map" role="application" aria-label="Places mentioned in this person’s facts"></div></div></section>' : '';
    const graphPerson = state.familyGraph?.records[people.indexOf(person)];
    const relationships = exactAnchor
      ? `${relationshipControls(state.familyGraph)}${relationshipPanel(state.familyGraph, graphPerson?._treeKey || '__unregistered__')}`
      : '';
    return renderPage(person, mentions, 'person', pattern, () => '', `${relationships}${personPlacesMarkup}${imagesMarkup}${sealsMarkup}`);
  }

  function renderPlacePage() {
    const place = getPlaces().find((place) => place.id === String(state.place || ''))
      || findPlaceByName(getPlaces(), state.place);
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
