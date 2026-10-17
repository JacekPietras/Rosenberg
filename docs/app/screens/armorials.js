export function createArmorialScreen({ state, escapeHtml, formatDate, imageMarkup, savePreferences, rerender }) {
  const normalize = (tag) => String(tag || '').trim().toLocaleLowerCase();

  function renderArmorialsPage() {
    const path = state.manifest.armorials;
    const document = path ? state.documents.get(path) : null;
    if (!document) return '<p>No armorials are available.</p>';
    const entries = document.entries || [];
    const selected = new Set(state.imageTags || []);
    const tags = [...new Set(entries.flatMap((entry) => (Array.isArray(entry.tags) ? entry.tags : []).map(String).map((tag) => tag.trim()).filter(Boolean)))].sort((a, b) => a.localeCompare(b));
    const sidebar = tags.length ? `<aside class="seal-sidebar image-tag-sidebar" aria-label="Filter images by tag"><nav>${tags.map((tag) => `<a href="#" class="${selected.has(normalize(tag)) ? 'selected' : ''}" data-image-tag="${escapeHtml(normalize(tag))}">${escapeHtml(tag)}</a>`).join('')}</nav></aside>` : '';
    const cards = entries.map((entry, index) => ({ entry, index })).filter(({ entry }) => !selected.size || (entry.tags || []).some((tag) => selected.has(normalize(tag)))).map(({ entry, index }) => {
      const tagMarkup = (entry.tags || []).map((tag) => `<span class="image-tag">${escapeHtml(tag)}</span>`).join('');
      return `<article class="model-card armorial-card"><div class="model-info"><h2>${escapeHtml(entry.title || document.title)}</h2>${entry.date ? `<p class="entry-date">${escapeHtml(formatDate(entry.date))}</p>` : ''}${tagMarkup ? `<div class="image-tags">${tagMarkup}</div>` : ''}</div>${entry.url ? imageMarkup(entry.url, [], { path, index, title: entry.title || document.title, focus: entry.focus, regions: entry.regions, showRegions: false }) : ''}</article>`;
    }).join('');
    return `<div class="image-tags-layout">${sidebar}<div class="models-grid armorial-grid">${cards || '<p class="status">No images match the selected tags.</p>'}</div></div>`;
  }

  function setupArmorialFilters() {
    document.querySelectorAll('[data-image-tag]').forEach((link) => link.addEventListener('click', (event) => {
      event.preventDefault();
      const tag = link.dataset.imageTag;
      const selected = state.imageTags || (state.imageTags = []);
      const index = selected.indexOf(tag);
      if (index >= 0) selected.splice(index, 1); else selected.push(tag);
      savePreferences();
      rerender();
    }));
  }

  return { renderArmorialsPage, setupArmorialFilters };
}
