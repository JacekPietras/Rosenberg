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
  treeMarkup,
  imageMarkup,
  diagramMarkup,
  entryAnchor,
  entryHasSource,
  documentTitle,
  documentYear,
  getPeople,
}) {
  function renderEntry(entry, { title = true, subheading = true, date = true, source = true, image = true, path = '', index = null, documentDate = '' } = {}) {
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
    const listRenderer = treeMarkup;
    const content = `${title && entry.title ? `<p class="entry-title">${markdownLinks(entry.title)}</p>` : ''}${subheading && entry.subheading ? `<h3 class="entry-subheading">${markdownLinks(entry.subheading)}</h3>` : ''}${entryDate}${source && entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.url ? urlMarkup(entry.url) : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry, undefined, listRenderer) : ''}${image && entry.img ? imageMarkup(entry.img, [], { path, index, showRegions: false }) : ''}${entry.diagram ? diagramMarkup(entry.diagram) : ''}${facts}`;
    if (!content) return '';
    return `<article class="entry"${anchor}>${content}</article>`;
  }

  function bookSections(entries) {
    return entries.reduce((sections, entry) => {
      if (entry.title || !sections.length) sections.push({ title: entry.title || '', titleImage: entry.title ? entry.img : null, entries: [] });
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
    const deleteButton = labelEditor
      ? `<button class="record-label-edit record-delete" type="button" data-delete-document="${escapeHtml(path)}" aria-label="Delete document" title="Delete document"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2m3 0-1 14H6L5 6m4 4v6m6-6v6"/></svg></button>`
      : '';
    const classifyButton = labelEditor ? `<button class="record-label-edit" type="button" data-classify-document="${escapeHtml(path)}" aria-label="Classify document" title="Classify document"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.6 9a2.5 2.5 0 1 1 4.1 1.9c-1 .8-1.7 1.2-1.7 2.6M12 17h.01"/></svg></button>` : '';
    const headingAside = labels.length || date || labelEditor ? `<div class="document-heading-aside"><div class="record-labels">${labels.map((label) => `<span class="record-label">${escapeHtml(label)}</span>`).join('')}${labelEditor}${deleteButton}${classifyButton}</div><span class="record-delete-status" role="status" aria-live="polite"></span><span class="record-classify-status" role="status" aria-live="polite"></span>${date}</div>` : '';
    const url = doc.url ? urlMarkup(doc.url) : '';
    const year = documentYear(doc);
    const anchor = year ? ` id="year-${year}-${index}"` : '';
    if (path.startsWith('data/books/') || path.startsWith('data/notes/')) {
      return bookSections(entries).map((section, sectionIndex) => {
        const sectionTitle = section.title || (sectionIndex === 0 ? title : 'Untitled section');
        const titleImage = section.titleImage ? imageMarkup(section.titleImage, [], { title: sectionTitle, path, showRegions: false, direct: true }) : '';
        const sectionContent = section.entries.map((entry, entryIndex) => renderEntry(entry, { title: false, image: !(entryIndex === 0 && section.titleImage), path, index: entries.indexOf(entry) })).join('');
        return `<article class="document book-document"><div class="document-heading"><div><h2>${titleImage}${escapeHtml(sectionTitle)}</h2>${sectionIndex === 0 ? url : ''}</div>${sectionIndex === 0 ? date : ''}</div>${sectionContent}</article>`;
      }).join('');
    }
    const content = entries.map((entry) => renderEntry(entry, { path, index: allEntries.indexOf(entry), documentDate: path.startsWith('data/documents/') ? doc.date || '' : '' })).join('');
    const important = labelKeys.includes('important') ? ' important' : '';
    const dimmed = labelKeys.some((label) => ['hessen', 'schenk', 'mönch', 'czechia'].includes(label)) ? ' dimmed' : '';
    return `<article class="document${important}${dimmed}"${anchor}><div class="document-heading"><div><h2>${inlineMarkup(title)}</h2>${url}</div>${headingAside}</div>${content}</article>`;
  }

  return { renderEntry, renderDocument };
}
