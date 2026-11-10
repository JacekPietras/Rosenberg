import { factDate } from '../rendering/facts.js?v=8';
import { dateSortValue } from '../rendering/dates.js';
import { renderFactsView } from '../components/facts_view.js?v=8';

export function createDocumentRenderer({
  state,
  formatDate,
  escapeHtml,
  markdownLinks,
  inlineMarkup,
  urlMarkup,
  languageMarkup,
  imageMarkup,
  diagramMarkup,
  entryAnchor,
  entryHasSource,
  documentTitle,
  documentYear,
  getPeople,
}) {
  // Keep the special-family emphasis local to the documents view. Place spellings
  // come from scripts/list_place_variations.py; title spellings come from names.md.
  const rossenbergSpellings = ['Rosenberg', 'Rosinberg', 'Rosemberg', 'Rossenberg', 'Roßenberg', 'Rosenberch', 'Rosemberch', 'Rosenburgk', 'Rossberg', 'Rosperg', 'Rosenperg', 'Rosenbergk', 'Rosenburg', 'Rosennberg', 'Rosenbach'];
  const targetNames = [
    ...rossenbergSpellings.map((name) => `Schenk\\s+von(?:\\s|<[^>]*>)*${name}`),
    ...rossenbergSpellings.flatMap((name) => [`Mönch\\s+von(?:\\s|<[^>]*>)*${name}`, `Münch\\s+von(?:\\s|<[^>]*>)*${name}`, `Munch\\s+von(?:\\s|<[^>]*>)*${name}`, `Mönich\\s+von(?:\\s|<[^>]*>)*${name}`, `Monich\\s+von(?:\\s|<[^>]*>)*${name}`]),
  ];
  const targetNamePattern = new RegExp(`(${targetNames.sort((a, b) => b.length - a.length).join('|')})`, 'giu');
  const rosenbergVariations = ['Rosenberg', 'Rosinberg', 'Rosemberg', 'Rossenberg', 'Rosenbergs', 'Roßenberg', 'Rosenberch', 'Rosemberch', 'Rosenburgk', 'Rossberg', 'Rusenberg', 'Roßberg', 'Rosperg', 'Rosenperg', 'Rosenbergk', 'Rosenberger', 'Rosenburg', 'Rosenerg', 'Rosennberg', 'Rosenbach'];
  const rosenbergPattern = new RegExp(`(?<![\\p{L}\\p{N}])(${rosenbergVariations.sort((a, b) => b.length - a.length).join('|')})(?![\\p{L}\\p{N}])`, 'giu');
  const highlightRosenberg = (markup) => String(markup).replace(rosenbergPattern, (name) => name
    .split(/(<[^>]*>)/g)
    .map((part) => part.startsWith('<') ? part : `<span class="target-family-name">${part}</span>`)
    .join(''));
  const highlightTargetNames = (markup) => String(markup).replace(targetNamePattern, (name) => name.includes('class="target-family-name"') ? name : name
    .split(/(<[^>]*>)/g)
    .map((part) => part.startsWith('<') ? part : `<span class="target-family-name">${part}</span>`)
    .join(''));
  const documentMarkup = (value) => highlightTargetNames(inlineMarkup(value));

  function renderEntry(entry, { title = true, date = true, source = true, path = '', index = null, documentDate = '' } = {}) {
    const entryDate = date && entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : '';
    const anchor = path && index !== null ? ` id="${entryAnchor(path, index)}"` : '';
    const defaultDate = /^data\/(?:books|notes)\//.test(path) ? '' : Object.hasOwn(entry, 'date') ? entry.date : documentDate;
    const items = [...(entry.facts || []), ...(entry.guesses || []).map((fact) => ({ ...fact, isGuess: true }))]
      .sort((a, b) => dateSortValue(factDate(a, defaultDate)) - dateSortValue(factDate(b, defaultDate)));
    const facts = state.showFacts ? renderFactsView(items, {
      people: getPeople(),
      personNames: state.familyGraph?.valid ? state.familyGraph.records.map((person) => person.name) : [],
      inlineMarkup,
      defaultDate,
    }) : '';
    return highlightTargetNames(`<article class="entry"${anchor}>${title && entry.title ? `<p class="entry-title">${markdownLinks(entry.title)}</p>` : ''}${entryDate}${source && entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.url ? urlMarkup(entry.url) : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry, (markup, language) => language === 'german' ? highlightRosenberg(markup) : markup) : ''}${entry.img ? imageMarkup(entry.img, [], { path, index, showRegions: false }) : ''}${entry.diagram ? diagramMarkup(entry.diagram) : ''}${facts}</article>`);
  }

  function bookSections(entries) {
    return entries.reduce((sections, entry) => {
      if (entry.title || !sections.length) sections.push({ title: entry.title || '', entries: [] });
      sections[sections.length - 1].entries.push(entry);
      return sections;
    }, []);
  }

  function renderDocument(doc, path, index) {
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
    const reviewActions = state.active === 'documents' && state.canEditDocuments && path.startsWith('data/documents/') && labelKeys.includes('to review')
      ? `<div class="record-review-actions"><button type="button" data-review-action="keep" data-review-path="${escapeHtml(path)}">Keep</button><button type="button" data-review-action="delete" data-review-path="${escapeHtml(path)}">Delete</button></div><span class="record-review-status" role="status"></span>` : '';
    const headingAside = labels.length || date || labelEditor ? `<div class="document-heading-aside"><div class="record-labels">${labels.map((label) => `<span class="record-label">${escapeHtml(label)}</span>`).join('')}${labelEditor}</div>${reviewActions}${date}</div>` : '';
    const url = doc.url ? urlMarkup(doc.url) : '';
    const year = documentYear(doc);
    const anchor = year ? ` id="year-${year}-${index}"` : '';
    if (path.startsWith('data/books/') || path.startsWith('data/notes/')) {
      return bookSections(entries).map((section, sectionIndex) => {
        const sectionTitle = section.title || (sectionIndex === 0 ? title : 'Untitled section');
        const sectionContent = section.entries.map((entry) => renderEntry(entry, { title: false, path, index: entries.indexOf(entry) })).join('');
        return `<article class="document book-document"><div class="document-heading"><div><h2>${markdownLinks(sectionTitle)}</h2>${sectionIndex === 0 ? url : ''}</div>${sectionIndex === 0 ? date : ''}</div>${sectionContent}</article>`;
      }).join('');
    }
    const content = entries.map((entry) => renderEntry(entry, { path, index: allEntries.indexOf(entry), documentDate: path.startsWith('data/documents/') ? doc.date || '' : '' })).join('');
    const important = labelKeys.includes('important') ? ' important' : '';
    const dimmed = labelKeys.some((label) => ['hessen', 'schenk', 'mönch', 'czechia'].includes(label)) ? ' dimmed' : '';
    return `<article class="document${important}${dimmed}"${anchor}><div class="document-heading"><div><h2>${documentMarkup(title)}</h2>${url}</div>${headingAside}</div>${content}</article>`;
  }

  return { renderEntry, renderDocument };
}
