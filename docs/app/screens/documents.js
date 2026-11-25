import { personRouteName } from '../data/person-name-recognition.js?v=27';
import { factDate } from '../rendering/facts.js?v=9';
import { dateSortValue } from '../rendering/dates.js';
import { renderFactsView } from '../components/facts_view.js?v=10';

export function createDocumentRenderer({
  state,
  formatDate,
  escapeHtml,
  markdownLinks,
  inlineMarkup,
  urlMarkup,
  languageMarkup,
  treeMarkup,
  imageMarkup,
  diagramMarkup,
  entryAnchor,
  entryHasSource,
  documentTitle,
  documentYear,
  getPeople,
  distinctFamilies,
}) {
  let indexedPlaces;
  let placeKeys = new Map();
  function personMentions(doc) {
    const found = new Map();
    const peopleById = new Map((state.people || []).filter((person) => person.id).map((person) => [person.id, person.name]));
    if (indexedPlaces !== state.places) {
      indexedPlaces = state.places;
      placeKeys = new Map();
      for (const place of state.places || []) {
        const forms = [place.name, ...(place.variations || [])].filter(Boolean);
        for (const form of forms) placeKeys.set(String(form).trim().toLocaleLowerCase(), String(place.id || place.name).toLocaleLowerCase());
      }
    }
    const add = (routeName, titles = []) => {
      const key = routeName.toLocaleLowerCase();
      if (!key) return;
      if (!found.has(key)) found.set(key, { name: routeName, places: new Set() });
      for (const title of Array.isArray(titles) ? titles : []) {
        const place = String(title).match(/(?:^|\s)zu\s+(.+)$/iu)?.[1]?.trim().replace(/\s+/gu, ' ').toLocaleLowerCase();
        if (place) found.get(key).places.add(placeKeys.get(place) || place);
      }
    };
    const addReference = (reference, titles) => {
      if (typeof reference !== 'string') return;
      const name = peopleById.get(reference) || reference;
      add(personRouteName(name, state.personNameTitlesText, state.nameConnectorsText, state.nobiliaryParticlesText, state.personNamesText, state.byNamesText, state.places), titles);
    };
    for (const entry of doc.entries || []) {
      for (const item of [...(entry.facts || []), ...(entry.guesses || [])]) {
        addReference(item?.person, item?.personTitle);
        addReference(item?.of, item?.ofTitle);
      }
      for (const item of entry.mention || []) {
        if (typeof item?.person === 'string') add(item.person, item.personTitle);
      }
    }
    return found;
  }

  let indexedDocuments;
  let mentionsByPath;
  let documentsByMention;
  let indexPromise;
  function documentMentionIndex() {
    if (indexPromise) return indexPromise;
    if (indexedDocuments === state.documents && mentionsByPath && documentsByMention) return Promise.resolve(mentionsByPath);
    indexedDocuments = state.documents;
    mentionsByPath = new Map();
    documentsByMention = new Map();
    const paths = [...(state.documents || [])].filter(([path]) => path.startsWith('data/documents/'));
    let cursor = 0;
    indexPromise = new Promise((resolve) => {
      const schedule = window.requestIdleCallback || ((callback) => window.setTimeout(() => callback({ timeRemaining: () => 8 }), 0));
      const process = (deadline) => {
        let processed = 0;
        while (cursor < paths.length && (processed < 12 || deadline.timeRemaining() > 2)) {
          const [path, doc] = paths[cursor++];
          const mentions = personMentions(doc);
          mentionsByPath.set(path, mentions);
          for (const [key, mention] of mentions) {
            if (!documentsByMention.has(key)) documentsByMention.set(key, []);
            documentsByMention.get(key).push({ path, doc, mention });
          }
          processed++;
        }
        if (cursor < paths.length) schedule(process);
        else resolve(mentionsByPath);
      };
      schedule(process);
    }).finally(() => { indexPromise = null; });
    return indexPromise;
  }

  function labelsForMentionedDocument(doc) {
    if (doc?.deleted) return ['deleted'];
    const values = Array.isArray(doc?.label) ? doc.label : [doc?.label];
    const labels = [...new Set(values.map((label) => String(label || '').trim())
      .filter((label) => label && !['to review', 'important'].includes(label.toLocaleLowerCase())))];
    return labels.length ? labels : values.some((label) => String(label || '').trim()) ? [] : ['Franken'];
  }

  function documentYearBounds(date) {
    const value = String(date || '');
    const bounds = value.split(/\/|--/);
    if (bounds.length === 2) {
      const start = bounds[0].match(/^(\d{4})/)?.[1];
      const end = bounds[1].match(/^(\d{4})/)?.[1];
      return start && end ? [Number(start), Number(end)] : null;
    }
    const yearRange = value.match(/^(\d{4})-(\d{4})$/);
    if (yearRange) return [Number(yearRange[1]), Number(yearRange[2])];
    const year = value.match(/^(\d{4})(?:-\d{2}(?:-\d{2})?)?$/)?.[1];
    return year ? [Number(year), Number(year)] : null;
  }

  async function reviewNameLabels(doc, path) {
    const index = await documentMentionIndex();
    const people = index.get(path) || personMentions(doc);
    const documentYears = documentYearBounds(doc.date);
    if (!people.size) return '';
    const labelsByName = new Map([...people.keys()].map((key) => [key, new Map()]));
    for (const key of people.keys()) {
      for (const { path: otherPath, doc: otherDoc, mention } of documentsByMention.get(key) || []) {
        if (otherPath === path) continue;
        const years = documentYearBounds(otherDoc.date);
        for (const label of labelsForMentionedDocument(otherDoc)) {
          const range = labelsByName.get(key).get(label) || { intervals: [], titleIntervals: new Map(), hasUnknownDate: false };
          if (years) {
            range.intervals.push(years);
            for (const place of people.get(key).places) {
              if (!mention.places.has(place)) continue;
              if (!range.titleIntervals.has(place)) range.titleIntervals.set(place, []);
              range.titleIntervals.get(place).push(years);
            }
          }
          else range.hasUnknownDate = true;
          labelsByName.get(key).set(label, range);
        }
      }
    }
    const mergeIntervals = (values) => values.sort((left, right) => left[0] - right[0] || left[1] - right[1])
      .reduce((merged, interval) => {
        const previous = merged.at(-1);
        if (previous && interval[0] - previous[1] <= 10) previous[1] = Math.max(previous[1], interval[1]);
        else merged.push([...interval]);
        return merged;
      }, []);
    const rows = [...people].map(([key, { name }]) => {
      const labels = [...labelsByName.get(key)]
        .flatMap(([label, range]) => {
          const intervals = mergeIntervals(range.intervals);
          const titleIntervals = [...range.titleIntervals.values()].flatMap(mergeIntervals);
          const visibleIntervals = intervals.filter(([start, end]) => {
            if (!documentYears) return true;
            const distance = end < documentYears[0]
              ? documentYears[0] - end
              : start > documentYears[1] ? start - documentYears[1] : 0;
            return distance <= 50;
          });
          const chips = visibleIntervals.map(([start, end]) => {
            const distance = !documentYears ? 0 : end < documentYears[0]
              ? documentYears[0] - end
              : start > documentYears[1] ? start - documentYears[1] : 0;
            const titleMatch = !!documentYears && distance === 0 && titleIntervals.some(([titleStart, titleEnd]) =>
              titleStart <= end && titleEnd >= start && titleStart <= documentYears[1] && titleEnd >= documentYears[0]);
            return { label, years: start === end ? `${start}` : `${start}-${end}`, outsideDate: distance > 10, titleMatch };
          });
          if (range.hasUnknownDate) chips.push({ label, years: '', outsideDate: false });
          return chips;
        })
        .sort((left, right) => left.label.localeCompare(right.label, undefined, { sensitivity: 'base' })
          || left.years.localeCompare(right.years, undefined, { numeric: true }));
      return labels.length ? `<div class="review-name-label-row"><span class="review-name">${escapeHtml(name)}</span><span class="review-name-labels">${labels.map(({ label, years, outsideDate, titleMatch }) => {
        return `<span class="record-label${outsideDate ? ' is-outside-document-date' : ''}${titleMatch ? ' is-title-match' : ''}">${escapeHtml(label)}${years ? ` [${years}]` : ''}</span>`;
      }).join('')}</span></div>` : '';
    }).filter(Boolean);
    return rows.length ? `<div class="review-name-mentions" tabindex="-1" aria-label="Labels in other documents where names are mentioned">${rows.join('')}</div>` : '';
  }

  function renderEntry(entry, { title = true, subheading = true, date = true, source = true, image = true, deferredDetails = false, path = '', index = null, documentDate = '' } = {}) {
    const entryDate = date && entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : '';
    const anchor = path && index !== null ? ` id="${entryAnchor(path, index)}"` : '';
    const defaultDate = /^data\/(?:books|notes)\//.test(path) ? '' : Object.hasOwn(entry, 'date') ? entry.date : documentDate;
    const items = state.showFacts && !deferredDetails ? [...(entry.facts || []), ...(entry.guesses || []).map((fact) => ({ ...fact, isGuess: true }))]
      .sort((a, b) => dateSortValue(factDate(a, defaultDate)) - dateSortValue(factDate(b, defaultDate))) : [];
    const facts = state.showFacts && !deferredDetails ? renderFactsView(items, {
      people: getPeople(),
      personNames: state.familyGraph?.valid ? state.familyGraph.records.map((person) => person.name) : [],
      inlineMarkup,
      defaultDate,
      mention: entry.mention,
      places: state.places,
    }) : '';
    const listRenderer = treeMarkup;
    const content = `${title && entry.title ? `<p class="entry-title">${markdownLinks(entry.title)}</p>` : ''}${subheading && entry.subheading ? `<h3 class="entry-subheading">${markdownLinks(entry.subheading)}</h3>` : ''}${entryDate}${source && entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.url ? urlMarkup(entry.url) : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry, undefined, listRenderer) : ''}${!deferredDetails && image && entry.img ? imageMarkup(entry.img, [], { path, index, showRegions: false }) : ''}${!deferredDetails && entry.diagram ? diagramMarkup(entry.diagram) : ''}${facts}`;
    if (!content) return '';
    return `<article class="entry"${anchor}>${content}</article>`;
  }

  function bookSections(entries) {
    return entries.reduce((sections, entry) => {
      if (entry.title || !sections.length) sections.push({ title: entry.title || '', label: entry.label || '', titleImage: entry.title ? entry.img : null, entries: [] });
      sections[sections.length - 1].entries.push(entry);
      return sections;
    }, []);
  }

  function renderDocument(doc, path, index, { hydrate = false } = {}) {
    const deferredDetails = !hydrate && state.active === 'documents' && path.startsWith('data/documents/');
    const allEntries = doc.entries || [];
    const entries = state.active === 'documents' && state.recordSource
      ? allEntries.filter((entry) => entryHasSource(entry, state.recordSource))
      : allEntries;
    const title = documentTitle(doc, path);
    const date = doc.date && formatDate(doc.date) !== title ? `<small>${escapeHtml(formatDate(doc.date))}</small>` : '';
    const labels = (Array.isArray(doc.label) ? doc.label : [doc.label]).map((label) => String(label || '').trim()).filter(Boolean);
    const labelKeys = labels.map((label) => label.toLocaleLowerCase());
    const labelEditor = state.canEditDocuments && path.startsWith('data/documents/')
      ? `<button class="record-label-edit" type="button" data-edit-record-labels="${escapeHtml(path)}" aria-label="Edit record labels" title="Edit labels"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z"/></svg></button>`
      : '';
    const years = new Set(allEntries.flatMap((entry) => typeof entry.english === 'string'
      ? [...entry.english.matchAll(/(?<!\d)\d{4}(?!\d)/g)].map((match) => match[0]) : []));
    const splitButton = labelEditor && years.size >= 3 && !labelKeys.includes('split')
      ? `<button class="record-split" type="button" data-split-document="${escapeHtml(path)}">Split</button>`
      : '';
    const deleteButton = labelEditor
      ? `<button class="record-label-edit record-delete" type="button" data-delete-document="${escapeHtml(path)}" aria-label="Delete document" title="Delete document"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2m3 0-1 14H6L5 6m4 4v6m6-6v6"/></svg></button>`
      : '';
    const reviewLabelButton = labelEditor
      ? `<button class="record-label-edit" type="button" data-show-review-labels="${escapeHtml(path)}" aria-label="Show label propositions" title="Show label propositions"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 1 1 4.1 1.9c-1 .8-1.7 1.2-1.7 2.6M12 17h.01"/></svg></button>`
      : '';
    const reviewLabels = Array.isArray(doc?.label) ? doc.label : [doc?.label];
    const hasReviewLabels = reviewLabels.some((label) => String(label || '').trim().toLocaleLowerCase() === 'to review');
    const needsMentionLabels = path.startsWith('data/documents/') && hasReviewLabels;
    const mentionLabels = needsMentionLabels ? `<div class="review-name-mentions" data-review-name-labels="${escapeHtml(path)}" aria-label="Labels in other documents where names are mentioned"></div>` : '';
    const mentionLabelTargets = needsMentionLabels ? ` data-review-label-path="${escapeHtml(path)}"` : '';
    const headingAside = labels.length || date || labelEditor || mentionLabels ? `<div class="document-heading-aside"><div class="record-labels">${labels.map((label) => `<span class="record-label">${escapeHtml(label)}</span>`).join('')}${labelEditor}${reviewLabelButton}${splitButton}${deleteButton}</div>${mentionLabels}<span class="record-delete-status" role="status" aria-live="polite"></span>${date}</div>` : '';
    const url = doc.url ? urlMarkup(doc.url) : '';
    const year = documentYear(doc);
    const anchor = year ? ` id="year-${year}-${index}"` : '';
    if (path.startsWith('data/books/') || path.startsWith('data/notes/')) {
      return bookSections(entries).map((section, sectionIndex) => {
        const sectionTitle = section.title || (sectionIndex === 0 ? title : 'Untitled section');
        const titleImage = section.titleImage ? imageMarkup(section.titleImage, [], { title: sectionTitle, path, showRegions: false, direct: true }) : '';
        const sectionContent = section.entries.map((entry, entryIndex) => renderEntry(entry, { title: false, image: !(entryIndex === 0 && section.titleImage), path, index: entries.indexOf(entry) })).join('');
        const sectionLabels = (Array.isArray(section.label) ? section.label : [section.label])
          .map((label) => String(label || '').trim()).filter(Boolean);
        const label = sectionLabels.map((value) => `<span class="record-label">${escapeHtml(value)}</span>`).join('');
        return `<article class="document book-document"><div class="document-heading"><div><h2>${titleImage}${escapeHtml(sectionTitle)}${label}</h2>${sectionIndex === 0 ? url : ''}</div>${sectionIndex === 0 ? date : ''}</div>${sectionContent}</article>`;
      }).join('');
    }
    const research = !deferredDetails && typeof doc.research === 'string' && doc.research.trim()
      ? `<section class="document-research" aria-label="Research"><h3>Research</h3><div class="document-research-text">${inlineMarkup(doc.research)}</div></section>`
      : '';
    const content = entries.map((entry) => renderEntry(entry, { path, index: allEntries.indexOf(entry), deferredDetails, documentDate: path.startsWith('data/documents/') ? doc.date || '' : '' })).join('');
    const important = labelKeys.includes('important') ? ' important' : '';
    const dimmed = labelKeys.some((label) => distinctFamilies.has(label)) ? ' dimmed' : '';
    const deferredPersonLinks = state.active === 'documents' && path.startsWith('data/documents/')
      ? ` data-person-links-path="${escapeHtml(path)}" data-person-links-index="${index}"`
      : '';
    return `<article class="document${important}${dimmed}"${anchor}${mentionLabelTargets}${deferredPersonLinks}><div class="document-heading"><div><h2>${inlineMarkup(title)}</h2>${url}</div>${headingAside}</div>${research}${content}</article>`;
  }

  function renderDocumentWithPersonLinks(doc, path, index) {
    const previous = state.deferPersonNameRecognition;
    const previousDeferredMarkupLinks = state.deferDocumentMarkupLinks;
    state.deferPersonNameRecognition = false;
    state.deferDocumentMarkupLinks = false;
    try { return renderDocument(doc, path, index, { hydrate: true }); }
    finally {
      state.deferPersonNameRecognition = previous;
      state.deferDocumentMarkupLinks = previousDeferredMarkupLinks;
    }
  }

  return { renderEntry, renderDocument, renderDocumentWithPersonLinks, reviewNameLabels };
}
