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
}) {
  function renderEntry(entry, { title = true, date = true, source = true, path = '', index = null } = {}) {
    const entryDate = date && entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : '';
    const anchor = path && index !== null ? ` id="${entryAnchor(path, index)}"` : '';
    return `<article class="entry"${anchor}>${title && entry.title ? `<p class="entry-title">${markdownLinks(entry.title)}</p>` : ''}${entryDate}${source && entry.source ? `<p class="source">${markdownLinks(entry.source)}</p>` : ''}${entry.url ? urlMarkup(entry.url) : ''}${entry.german || entry.latin || entry.english ? languageMarkup(entry) : ''}${entry.img ? imageMarkup(entry.img, [], { path, index }) : ''}${entry.diagram ? diagramMarkup(entry.diagram) : ''}${state.showFacts && entry.facts?.length ? `<ul class="facts">${entry.facts.map((fact) => `<li>${inlineMarkup(fact)}</li>`).join('')}</ul>` : ''}</article>`;
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
    const entries = state.active === 'letters' && state.letterSource
      ? allEntries.filter((entry) => entryHasSource(entry, state.letterSource))
      : allEntries;
    const title = documentTitle(doc, path);
    const date = doc.date && formatDate(doc.date) !== title ? `<small>${escapeHtml(formatDate(doc.date))}</small>` : '';
    const label = String(doc.label || '').trim();
    const headingAside = label || date ? `<div class="document-heading-aside">${label ? `<span class="letter-label">${escapeHtml(label)}</span>` : ''}${date}</div>` : '';
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
    const content = entries.map((entry) => renderEntry(entry, { path, index: allEntries.indexOf(entry) })).join('');
    const important = label.toLocaleLowerCase() === 'important' ? ' important' : '';
    const dimmed = ['hessen', 'schenk', 'mönch'].includes(label.toLocaleLowerCase()) ? ' dimmed' : '';
    return `<article class="document${important}${dimmed}"${anchor}><div class="document-heading"><div><h2>${inlineMarkup(title)}</h2>${url}</div>${headingAside}</div>${content}</article>`;
  }

  return { renderEntry, renderDocument };
}
